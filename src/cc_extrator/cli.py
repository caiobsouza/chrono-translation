import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cc_extrator import chronotools, glyphs, script, validator

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
        case "check":
            if not run_check(args):
                sys.exit(1)
        case "insert":
            if not args.skip_check and not run_check(args):
                sys.exit("Not inserting, fix the errors above or use --skip-check.")
            print(f"Patch: {chronotools.insert(args.work)}")
        case "apply":
            print(f"ROM: {chronotools.apply_patch(args.work, args.out)}")
