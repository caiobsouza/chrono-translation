import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cc_extrator import budget, chronotools, glyphs, script, translate, validator

DEFAULT_ROM = Path("data/ChronoTrigger.sfc")
DEFAULT_WORK_DIR = Path("work")
DEFAULT_OUT = Path("out/ChronoTrigger-ptbr.sfc")
DEFAULT_GLOSSARY = Path("notebook/glossary.tsv")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cc-extrator", description="Extract, translate and reinsert Chrono Trigger text.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("build-image", help="build the Chronotools docker image")

    extract = commands.add_parser("extract", help="dump the script and fonts from the ROM")
    extract.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    extract.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)

    accents = commands.add_parser("accents", help="add the Portuguese accented letters to the fonts in the work directory")
    accents.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)

    check = commands.add_parser("check", help="validate the translated script against the original")
    _add_check_options(check)

    space = commands.add_parser("budget", help="report how much of the text space the script uses")
    space.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)

    ask = commands.add_parser("translate", help="translate strings with the Claude API (dry run unless --yes)")
    ask.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)
    ask.add_argument("--model", default=translate.Options.model, choices=sorted(translate.PRICES))
    ask.add_argument("--effort", default=translate.Options.effort, choices=["low", "medium", "high"])
    ask.add_argument("--blocks", default="", help="comma separated block labels, for example 'dialog,item descs'")
    ask.add_argument("--limit", type=int, help="translate only the first N untranslated strings")
    ask.add_argument("--batch-size", type=int, default=translate.Options.batch_size)
    ask.add_argument("--max-cost", type=float, default=translate.Options.max_cost, help="USD this run may spend")
    ask.add_argument("--total-cap", type=float, default=translate.DEFAULT_TOTAL_CAP, help="USD the ledger may reach over all runs")
    ask.add_argument("--ledger", type=Path, default=translate.Options.ledger, help="spend ledger shared by every work directory")
    ask.add_argument("--yes", action="store_true", help="really call the API and spend money")
    ask.add_argument("--redo", action="store_true", help="translate strings that already differ from the English")
    ask.add_argument("--growth", type=float, default=translate.GROWTH_TARGET, help="length target relative to the English, below 1 asks for shorter text")
    ask.add_argument("--keys", default="", help="comma separated string keys to translate again")
    ask.add_argument("--review", action="store_true", help="review the existing translation and change only the lines with a real problem")
    ask.add_argument("--no-thinking", action="store_true", help="turn thinking off, much cheaper")
    ask.add_argument("--redo-invalid", action="store_true", help="translate again the strings that currently fail the validator")

    insert = commands.add_parser("insert", help="check the script, then compile it into an IPS patch")
    _add_check_options(insert)
    insert.add_argument("--skip-check", action="store_true", help="do not validate before inserting")

    apply = commands.add_parser("apply", help="apply the patch to the ROM")
    apply.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)
    apply.add_argument("--out", type=Path, default=DEFAULT_OUT)

    return parser


def _add_check_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--work", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--allow-accents", action="store_true", help="accept accented letters, use once the font has them")
    parser.add_argument("--translate-screens", action="store_true", help="allow editing the menu and status screens")


def run_check(args: argparse.Namespace) -> bool:
    """Print the report and return True when there are no errors."""
    original_path = args.work / chronotools.ORIGINAL_SCRIPT_NAME
    target_path = args.work / chronotools.SCRIPT_NAME
    for path in (original_path, target_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Run extract first, it saves the original script as {chronotools.ORIGINAL_SCRIPT_NAME}.")
    original, _ = script.read(original_path)
    target, utf8 = script.read(target_path)
    options = validator.Options(
        allow_accents=args.allow_accents,
        translate_screens=args.translate_screens,
        glossary=args.glossary if args.glossary.is_file() else None,
        config=args.work / chronotools.CONFIG_NAME,
    )
    report = validator.check(original, target, options, utf8_target=utf8)
    print(validator.format_report(report))
    return not report.errors


def run_translate(args: argparse.Namespace) -> None:
    options = translate.Options(
        model=args.model, effort=args.effort, blocks=[b.strip() for b in args.blocks.split(",") if b.strip()],
        limit=args.limit, batch_size=args.batch_size, max_cost=args.max_cost, total_cap=args.total_cap,
        confirmed=args.yes, redo=args.redo, redo_invalid=args.redo_invalid, thinking=not args.no_thinking, growth=args.growth, review=args.review, keys=[k.strip() for k in args.keys.split(",") if k.strip()], ledger=args.ledger,
    )
    client = None
    if args.yes:
        import anthropic
        client = anthropic.Anthropic(timeout=180.0, max_retries=2)
    summary = translate.run(args.work, options, client)
    print(f"translated {summary.translated}, failed {len(summary.failed)}, calls {summary.calls}, spent ${summary.cost:.3f}")
    if summary.stopped:
        print(f"stopped: {summary.stopped}")


def run_budget(work: Path) -> bool:
    """Print the space report and return True when the script fits."""
    original_path = work / chronotools.ORIGINAL_SCRIPT_NAME
    target_path = work / chronotools.SCRIPT_NAME
    for path in (original_path, target_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing {path}. Run extract first.")
    english = chronotools.measure(work, original_path)
    translation = None if target_path.read_bytes() == original_path.read_bytes() else chronotools.measure(work, target_path)
    print(budget.format_report(english, translation))
    return (translation or english).fits


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        _run(args)
    except (chronotools.ChronotoolsError, FileNotFoundError) as error:
        sys.exit(f"Error: {error}")


def _run(args: argparse.Namespace) -> None:
    match args.command:
        case "build-image":
            chronotools.build_image()
        case "extract":
            print(f"Script: {chronotools.extract(args.rom, args.work)}")
        case "accents":
            result = glyphs.add_accents(args.work)
            print(f"12px font: {''.join(result.font12)}")
            print(f"8px font:  {''.join(result.font8)}")
        case "translate":
            run_translate(args)
        case "budget":
            if not run_budget(args.work):
                sys.exit(1)
        case "check":
            if not run_check(args):
                sys.exit(1)
        case "insert":
            if not args.skip_check and not run_check(args):
                sys.exit("Not inserting, fix the errors above or use --skip-check.")
            print(f"Patch: {chronotools.insert(args.work)}")
        case "apply":
            print(f"ROM: {chronotools.apply_patch(args.work, args.out)}")
