"""Checks a translated script against the English original.

The rules come from notebook/translation-guidelines.md. Limits such as line width
and single line ceilings are measured from the original script itself, so they
cannot drift from what the game accepts. Only strings that differ from the
original are checked in depth, the untouched ones are vanilla.
"""

import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from cc_extrator import glyphs
from cc_extrator.fontwidths import INDENT_WIDTH, SPACE_WIDTH, text_width, visible_length
from cc_extrator.script import Block, Entry, Script

ERROR = "error"
WARNING = "warning"

DIALOG_LINE_LIMIT = 240
DIALOG_PAGE_LINES = 4

ACCENTS = "áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
CHARSET_12PX = set(_LETTERS + "!?/:&()'.,=-+% «»")
CHARSET_8PX_DEFAULT = set(_LETTERS + "!?/#=-+%«»:&()'., _")

_TYPOGRAPHIC = {
    "—": "em dash",
    "–": "en dash",
    "‘": "curly quote",
    "’": "curly quote",
    "“": "curly double quote",
    "”": "curly double quote",
    "…": "ellipsis character (type three dots)",
    " ": "non breaking space",
}

_CODE = re.compile(r"\[[^\]]*\]")
_NEWLINE_AFTER_CODE = re.compile(r"(\[(?:nl|pause|cls)[^\]]*\])\n")
_LINE_BREAK = re.compile(r"\[nl3?\]")
_PAGE_BREAK = re.compile(r"\[(?:pause3?|pausenl3?|cls3?|next)\]")
_SPEAKER = re.compile(r"^\s*(?:\[[^\]]*\])*[A-Z][A-Za-z0-9 .'&-]{0,24}:")
_PAUSE_TAIL = re.compile(r"\[(?:pause3?|cls3?)\](\n {3}|\n| {3}|)")

_PARTY_NAMES = ("Crono", "Marle", "Lucca", "Frog", "Robos", "Ayla", "Magus")
_DECORATED_NAME = re.compile(r"\b(?:Crono|Marle|Lucca|Ayla|Magus|Frog)(?:s|zinh[ao]|inh[ao]|zão)\b")
_ARTICLE_NAME = re.compile(r"\b(?:o|a|os|as) (?:Crono|Marle|Lucca|Ayla|Magus|Frog|Robos)\b", re.IGNORECASE)
_BARE_ROBO = re.compile(r"\bRobo\b")

PROTECTED_LABELS = {"dictionary", "cset", "buttons"}
PROTECTED_KINDS = set("dscehq?")  # everything except z, Z, r, l, i, t, m


@dataclass(frozen=True)
class Issue:
    severity: str
    block: str
    key: str
    code: str
    message: str


@dataclass
class Options:
    allow_accents: bool = False
    translate_screens: bool = False
    glossary: Path | None = None
    config: Path | None = None


@dataclass
class Report:
    issues: list[Issue]
    translated: int
    unchanged: int

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == ERROR]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == WARNING]


def check(source: Script, target: Script, options: Options | None = None, utf8_target: bool = False) -> Report:
    options = options or Options()
    issues: list[Issue] = []
    if utf8_target:
        message = "file is UTF-8, it must be saved as ISO-8859-15 (nothing else was checked)"
        return Report([Issue(ERROR, "", "", "encoding", message)], 0, 0)
    translated = unchanged = 0
    if _structure_differs(source, target, issues):
        return Report(issues, translated, unchanged)

    allowed_12px = CHARSET_12PX | _accents(options, "12")
    allowed_8px = _charset_8px(source) | _accents(options, "8")

    for source_block, target_block in zip(source.blocks, target.blocks):
        limits = _limits(source_block, options)
        for original, entry in zip(source_block.entries, target_block.entries):
            if _protected(source_block, options):
                if entry.text != original.text:
                    issues.append(_issue(target_block, entry, "protected", "this block must not be edited"))
                continue
            if entry.text == original.text:
                if _has_letters(original.text):
                    unchanged += 1
                continue
            translated += 1
            issues += _check_entry(target_block, original, entry, limits, allowed_12px, allowed_8px, options)

    if options.glossary is not None:
        issues += _check_glossary(target, options.glossary)
    return Report(issues, translated, unchanged)


def _structure_differs(source: Script, target: Script, issues: list[Issue]) -> bool:
    if len(source.blocks) != len(target.blocks):
        issues.append(Issue(ERROR, "", "", "structure", f"expected {len(source.blocks)} blocks, found {len(target.blocks)}"))
        return True
    broken = False
    for index, (original, block) in enumerate(zip(source.blocks, target.blocks)):
        if original.line != block.line:
            issues.append(Issue(ERROR, block.label, "", "structure", f"block {index + 1} header changed: {original.line!r} became {block.line!r}"))
            broken = True
            continue
        expected = [entry.key for entry in original.entries]
        found = [entry.key for entry in block.entries]
        if expected != found:
            issues.append(Issue(ERROR, block.label, "", "structure", _key_difference(expected, found)))
            broken = True
    return broken


def _key_difference(expected: list[str], found: list[str]) -> str:
    missing = [key for key in expected if key not in set(found)]
    extra = [key for key in found if key not in set(expected)]
    if missing or extra:
        return f"keys differ, missing {missing[:5]}, extra {extra[:5]}"
    return "keys were reordered"


def _protected(block: Block, options: Options) -> bool:
    if block.kind in PROTECTED_KINDS or block.label in PROTECTED_LABELS:
        return True
    return block.label == "screens" and not options.translate_screens


@dataclass
class _Limits:
    max_px: int = 0
    max_lines: int = 0
    max_visible: int = 0


def _limits(block: Block, options: Options) -> _Limits:
    """Ceilings measured from the original strings of the block."""
    limits = _Limits()
    for entry in block.entries:
        lines = _lines(entry.text)
        limits.max_lines = max(limits.max_lines, len(lines))
        limits.max_px = max([limits.max_px] + [text_width(line) for line in lines])
        limits.max_visible = max([limits.max_visible] + [visible_length(line) for line in lines])
    return limits


def _check_entry(block: Block, original: Entry, entry: Entry, limits: _Limits,
                 allowed_12px: set[str], allowed_8px: set[str], options: Options) -> list[Issue]:
    issues: list[Issue] = []

    def add(severity: str, code: str, message: str) -> None:
        issues.append(Issue(severity, block.label, entry.key, code, message))

    eight_pixel = block.kind in "rlitm"
    if not original.text.strip():
        add(ERROR, "empty", "an unused string must stay as it is")
        return issues
    if not entry.text.strip():
        add(ERROR, "empty", "a used string cannot be emptied")
        return issues

    _check_codes(block, original, entry, add)
    _check_characters(entry.text, allowed_8px if eight_pixel else allowed_12px, eight_pixel, options, add)
    _check_names(original.text, entry.text, add)

    if block.kind in "litm" and block.width is not None:
        length = visible_length(entry.text)
        if length > block.width:
            add(ERROR, "too-long", f"{length} characters, the field holds {block.width} and cuts the rest silently")
    elif block.kind == "r":
        length = visible_length(_flat(entry.text))
        if length > limits.max_visible:
            add(ERROR, "too-long", f"{length} characters, the longest original in this block is {limits.max_visible}")
    elif block.is_dialog:
        _check_dialog(entry.text, add)
    elif block.kind in "zZ":
        _check_single_block(entry.text, limits, add)
    return issues


def _check_codes(block: Block, original: Entry, entry: Entry, add) -> None:
    expected = _codes(original.text, dialog=block.is_dialog)
    found = _codes(entry.text, dialog=block.is_dialog)
    if expected != found:
        add(ERROR, "codes", f"control codes differ, expected {expected}, found {found}")
        return
    if block.is_dialog:
        before, after = _pause_tails(original.text), _pause_tails(entry.text)
        if before != after:
            add(WARNING, "pause-layout", "the whitespace after [pause] or [cls] differs from the original")


def _codes(text: str, dialog: bool) -> list[str]:
    codes = _CODE.findall(text)
    return [code for code in codes if not (dialog and code in ("[nl]", "[nl3]"))]


def _pause_tails(text: str) -> list[str]:
    return [tail for tail in _PAUSE_TAIL.findall(text)]


def _check_characters(text: str, allowed: set[str], eight_pixel: bool, options: Options, add) -> None:
    body = _CODE.sub("", text)
    bad = Counter(char for char in body if char != "\n" and char not in allowed and not (char == "_" and eight_pixel))
    for char, count in bad.items():
        if char in _TYPOGRAPHIC:
            add(ERROR, "characters", f"{_TYPOGRAPHIC[char]} is not in the font, type plain ASCII")
        elif char in ACCENTS:
            add(ERROR, "accents", f"accented letter {char!r} is not in the {'8px' if eight_pixel else '12px'} font, run cc-extrator accents ({count}x)")
        else:
            add(ERROR, "characters", f"character {char!r} is not in the font ({count}x)")
    if not eight_pixel and "_" in body:
        add(ERROR, "characters", "underscore is only valid in the 8px fields")


def _check_names(original: str, text: str, add) -> None:
    if len(_BARE_ROBO.findall(text)) > len(_BARE_ROBO.findall(original)):
        add(ERROR, "names", "use Robos, the rename token, not Robo")
    if _DECORATED_NAME.search(text):
        add(WARNING, "names", "party names must not be inflected or decorated")
    if _ARTICLE_NAME.search(text):
        add(WARNING, "names", "avoid an article before a party name, the player can rename them")


def _check_single_block(text: str, limits: _Limits, add) -> None:
    lines = _lines(text)
    if len(lines) > limits.max_lines:
        add(ERROR, "lines", f"{len(lines)} lines, this block never uses more than {limits.max_lines}")
    for line in lines:
        width = text_width(line)
        if width > limits.max_px:
            add(ERROR, "width", f"line is {width} px, the widest original in this block is {limits.max_px} px: {line.strip()[:40]!r}")


def _check_dialog(text: str, add) -> None:
    for page in _PAGE_BREAK.split(_flat(text)):
        lines, too_long = _estimate_lines(page)
        if lines > DIALOG_PAGE_LINES:
            add(ERROR, "page-lines", f"a page needs about {lines} lines, the limit is {DIALOG_PAGE_LINES}")
        for word in too_long:
            add(ERROR, "long-word", f"word {word!r} does not fit on a line, the wrapper would mangle it")


def _estimate_lines(page: str) -> tuple[int, list[str]]:
    """Greedy word wrap that imitates the wrapper in ctinsert."""
    continuation = INDENT_WIDTH if _SPEAKER.match(page) else 0
    total = 0
    too_long: list[str] = []
    for forced in _LINE_BREAK.split(page):
        leading = len(forced) - len(forced.lstrip(" "))
        indent = leading * SPACE_WIDTH if leading else continuation
        width = leading * SPACE_WIDTH
        total += 1
        started = False
        for word in _words(forced):
            size = text_width(word)
            if size > DIALOG_LINE_LIMIT - indent:
                too_long.append(word)
            needed = size + (SPACE_WIDTH if started else 0)
            if started and width + needed > DIALOG_LINE_LIMIT:
                total += 1
                width = indent + size
            else:
                width += needed
            started = True
    return total, too_long


def _words(line: str) -> list[str]:
    """Split on spaces but keep a control code such as [delay 08] in one piece."""
    guarded = _CODE.sub(lambda match: match.group(0).replace(" ", "\0"), line)
    return [word.replace("\0", " ") for word in guarded.split()]


def _flat(text: str) -> str:
    """The text as the tool reads it: a raw newline after a code is dropped, any other becomes a space."""
    return _NEWLINE_AFTER_CODE.sub(r"\1", text).replace("\n", " ")


def _lines(text: str) -> list[str]:
    return _LINE_BREAK.split(_flat(text))


def _has_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z]", _CODE.sub("", text)))


def _accents(options: Options, font: str) -> set[str]:
    """Accented letters the font can show. Read from ct.cfg when given, so the check follows the real font."""
    if options.config is not None and options.config.is_file():
        return glyphs.mapped_characters(options.config, font) & set(ACCENTS)
    return set(ACCENTS) if options.allow_accents else set()


def _charset_8px(source: Script) -> set[str]:
    for block in source.blocks:
        if block.label == "cset" and block.entries:
            return set(block.entries[0].text) | {"_"}
    return set(CHARSET_8PX_DEFAULT)


def _check_glossary(target: Script, path: Path) -> list[Issue]:
    entries = {entry.key: (block.label, entry) for block in target.blocks for entry in block.entries}
    issues: list[Issue] = []
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file, delimiter="\t"):
            wanted = (row.get("ptbr") or "").strip()
            key = row.get("key") or ""
            if not wanted or not key or key not in entries:
                continue
            label, entry = entries[key]
            if entry.text.rstrip() != wanted:
                issues.append(Issue(ERROR, label, key, "glossary", f"glossary says {wanted!r}, the script has {entry.text.rstrip()!r}"))
    return issues


def _issue(block: Block, entry: Entry, code: str, message: str) -> Issue:
    return Issue(ERROR, block.label, entry.key, code, message)


def format_report(report: Report, limit_per_code: int = 15) -> str:
    lines: list[str] = []
    by_code: dict[str, list[Issue]] = {}
    for issue in report.issues:
        by_code.setdefault(issue.code, []).append(issue)
    for code, group in by_code.items():
        lines.append(f"{code}: {len(group)} ({group[0].severity})")
        for issue in group[:limit_per_code]:
            where = f"{issue.block} ${issue.key}".strip() if issue.block or issue.key else "file"
            lines.append(f"  {where}: {issue.message}")
        if len(group) > limit_per_code:
            lines.append(f"  and {len(group) - limit_per_code} more")
    lines.append(
        f"{len(report.errors)} errors, {len(report.warnings)} warnings. "
        f"{report.translated} strings changed, {report.unchanged} still identical to the original."
    )
    return "\n".join(lines)
