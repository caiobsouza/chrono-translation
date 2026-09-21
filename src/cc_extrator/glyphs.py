"""Adds the Portuguese accented letters to the game fonts.

The glyphs are composed from the letters already in the font, so nothing from the
ROM is stored in the repository. Accent marks are small bitmaps drawn in the same
style as the game (white strokes with a black shadow on the right and below).

Both fonts are grids of cells. The 12px dialogue font has 32 by 24 cells of 12 by
12 pixels and marks each glyph's width with olive pixels to its right. The 8px
font has 32 by 8 cells of 8 by 8 pixels and is fixed width.

The glyphs go into unused slots. ctinsert rearranges the characters by how often the
script uses them and moves the most frequent ones into free single byte slots, so the
common accents end up cheap without shrinking the compression dictionary.

Lowercase letters leave two free rows above them, so the accent goes there.
Capitals fill the cell, so they are squeezed by dropping their most redundant
rows to make room, which makes accented capitals a little shorter than plain ones.
"""

import math
import re
from dataclasses import dataclass
from pathlib import Path

from cc_extrator import tga

CFG_ENCODING = "iso-8859-15"

TRANSPARENT, SHADOW, CORNER, WHITE, OUTSIDE = 1, 2, 3, 4, 5
_PIXELS = {".": TRANSPARENT, "W": WHITE, "k": SHADOW, "g": CORNER}

MARKS = {
    "acute": ["....Wk.", "...Wkg."],
    "grave": ["..Wk...", "...Wkg."],
    "circumflex": ["..WWk..", ".Wk.Wk."],
    "tilde": [".WWkWk.", "Wk.Wk.."],
}
CEDILLA_12 = ["..Wk...", "...Wk..", "..Wkg.."]
CEDILLA_8 = ["...Wk..."]

LOWERCASE = [("á", "a", "acute"), ("à", "a", "grave"), ("â", "a", "circumflex"), ("ã", "a", "tilde"),
             ("é", "e", "acute"), ("ê", "e", "circumflex"), ("í", "i", "acute"), ("ó", "o", "acute"),
             ("ô", "o", "circumflex"), ("õ", "o", "tilde"), ("ú", "u", "acute"), ("ç", "c", "cedilla")]
UPPERCASE = [(a.upper(), b.upper(), m) for a, b, m in LOWERCASE]
ACCENTED = "".join(char for char, _, _ in LOWERCASE + UPPERCASE)

FIRST_EXTRA_SLOT_12PX = 0x100
FIRST_SLOT_8PX = 0x80
_FONT_LINE = re.compile(r'^(font(?P<font>12|8)_(?P<start>[0-9A-Fa-f]+))\s*=\s*"(?P<a>[^"]*)"\s*"(?P<b>[^"]*)"\s*$')

Glyph = list[list[int]]


@dataclass(frozen=True)
class Sheet:
    """The geometry of one font image."""

    cell: int
    marks_width: bool
    cap_rows: int
    cap_target: int
    cedilla: list[str]
    cedilla_top: int

    @property
    def pitch(self) -> int:
        return self.cell + 1


SHEET_12PX = Sheet(cell=12, marks_width=True, cap_rows=9, cap_target=7, cedilla=CEDILLA_12, cedilla_top=9)
SHEET_8PX = Sheet(cell=8, marks_width=False, cap_rows=8, cap_target=6, cedilla=CEDILLA_8, cedilla_top=7)


class FontImage:
    def __init__(self, image: tga.Image, sheet: Sheet):
        self.image = image
        self.sheet = sheet

    def get(self, slot: int) -> Glyph:
        x, y = self._origin(slot)
        return [self.image.rows[y + row][x:x + self.sheet.cell] for row in range(self.sheet.cell)]

    def put(self, slot: int, glyph: Glyph) -> None:
        x, y = self._origin(slot)
        for row in range(self.sheet.cell):
            self.image.rows[y + row][x:x + self.sheet.cell] = glyph[row]

    def _origin(self, slot: int) -> tuple[int, int]:
        pitch = self.sheet.pitch
        return 1 + (slot % 32) * pitch, 1 + (slot // 32) * pitch


def glyph_width(glyph: Glyph, sheet: Sheet) -> int:
    if not sheet.marks_width:
        return sheet.cell
    return next((x for x, value in enumerate(glyph[0]) if value == OUTSIDE), sheet.cell)


def build_glyph(base: Glyph, mark: str, capital: bool, sheet: Sheet, dotless: bool = False) -> Glyph:
    glyph = [row[:] for row in base]
    width = glyph_width(glyph, sheet)
    if dotless:
        glyph = _remove_dot(glyph, sheet)
    if mark == "cedilla":
        return _add_cedilla(glyph, width, sheet)
    if capital:
        glyph = _squeeze(glyph, sheet, width)
    _stamp(glyph, MARKS[mark], top=0, width=width, shift=_shift(glyph, MARKS[mark], width))
    return glyph


def _remove_dot(glyph: Glyph, sheet: Sheet) -> Glyph:
    """Turn the letter i into a dotless one, ready to carry an accent."""
    blank = _blank_row(glyph, sheet)
    if sheet.marks_width:
        for row in (0, 1):
            glyph[row] = blank[:]
        return glyph
    stem = glyph[4][:]
    for row in (1, 2):
        glyph[row] = blank[:]
    for row in (2, 3):
        glyph[row] = stem[:]
    return glyph


def _blank_row(glyph: Glyph, sheet: Sheet) -> list[int]:
    width = glyph_width(glyph, sheet)
    return [TRANSPARENT if x < width else OUTSIDE for x in range(sheet.cell)]


def _squeeze(glyph: Glyph, sheet: Sheet, width: int) -> Glyph:
    """Drop the most redundant rows of a capital so it ends at the same baseline but is shorter."""
    rows = [row[:] for row in glyph[:sheet.cap_rows]]
    while len(rows) > sheet.cap_target:
        index = max(range(1, len(rows) - 1), key=lambda i: _droppable(rows, i))
        del rows[index]
    result = [_blank_row(glyph, sheet) for _ in range(sheet.cell)]
    top = sheet.cap_rows - len(rows)
    for offset, row in enumerate(rows):
        result[top + offset] = row
    return result


def _similarity(first: list[int], second: list[int]) -> int:
    return sum(1 for a, b in zip(first, second) if a == b)


def _droppable(rows: list[list[int]], index: int) -> int:
    """How little is lost by dropping a row. Rows much heavier than their neighbours are horizontal
    strokes such as the bar of an A or an E, so they are protected."""
    previous, following = rows[index - 1], rows[index + 1]
    score = _similarity(rows[index], previous) + _similarity(rows[index], following)
    weight = rows[index].count(WHITE)
    heavier = weight - max(previous.count(WHITE), following.count(WHITE))
    return score - 4 * max(0, heavier)


def _add_cedilla(glyph: Glyph, width: int, sheet: Sheet) -> Glyph:
    if not sheet.marks_width:
        # the 8px cell has no free row below, so the bottom shadow row becomes the cedilla
        glyph[sheet.cedilla_top] = _blank_row(glyph, sheet)
    _stamp(glyph, sheet.cedilla, top=sheet.cedilla_top, width=width, shift=_shift(glyph, sheet.cedilla, width))
    return glyph


def _stamp(glyph: Glyph, template: list[str], top: int, width: int, shift: int) -> None:
    for dy, line in enumerate(template):
        for x, char in enumerate(line):
            column = x + shift
            if char != "." and 0 <= column < width:
                glyph[top + dy][column] = _PIXELS[char]


def _shift(glyph: Glyph, template: list[str], width: int) -> int:
    """Horizontal shift that centres the template over the ink of the glyph."""
    ink = [x for row in glyph for x, value in enumerate(row) if x < width and value not in (TRANSPARENT, OUTSIDE)]
    marked = [x for line in template for x, char in enumerate(line) if char != "."]
    if not ink:
        return 0
    return math.floor((min(ink) + max(ink) - min(marked) - max(marked)) / 2 + 0.5)


@dataclass
class Result:
    font12: list[str]
    font8: list[str]


def add_accents(work_dir: Path) -> Result:
    """Draw the accented letters into ct16fn.tga and ct8fn.tga and register them in ct.cfg."""
    config_path = work_dir / "ct.cfg"
    lines = config_path.read_text(encoding=CFG_ENCODING).split("\n")
    slots = {"12": _read_slots(lines, "12"), "8": _read_slots(lines, "8")}
    nonchar = _nonchar(lines)

    font12 = FontImage(tga.read(work_dir / "ct16fn.tga"), SHEET_12PX)
    font8 = FontImage(tga.read(work_dir / "ct8fn.tga"), SHEET_8PX)
    plans = {
        "12": (font12, _slot_plan(FIRST_EXTRA_SLOT_12PX)),
        "8": (font8, _slot_plan(FIRST_SLOT_8PX)),
    }
    added: dict[str, list[str]] = {}
    for name, (image, plan) in plans.items():
        added[name] = []
        for (char, base, mark, capital), slot in plan:
            _require_free(slots[name], slot, char, nonchar, name)
            source = image.get(_slot_of(slots[name], base, name))
            glyph = build_glyph(source, mark, capital, image.sheet, dotless=(base == "i"))
            image.put(slot, glyph)
            slots[name][slot] = char
            added[name].append(char)
        _write_slots(lines, name, slots[name])
    font12.image.save(work_dir / "ct16fn.tga")
    font8.image.save(work_dir / "ct8fn.tga")
    config_path.write_text("\n".join(lines), encoding=CFG_ENCODING)
    return Result(added["12"], added["8"])


def _slot_plan(first_slot: int):
    specs = [(char, base, mark, False) for char, base, mark in LOWERCASE] + [(char, base, mark, True) for char, base, mark in UPPERCASE]
    return [(spec, first_slot + offset) for offset, spec in enumerate(specs)]


def _read_slots(lines: list[str], font: str) -> dict[int, str]:
    slots: dict[int, str] = {}
    for line in lines:
        match = _FONT_LINE.match(line)
        if match and match.group("font") == font:
            start = int(match.group("start"), 16)
            for offset, char in enumerate(match.group("a") + match.group("b")):
                slots[start + offset] = char
    return slots


def _write_slots(lines: list[str], font: str, slots: dict[int, str]) -> None:
    for index, line in enumerate(lines):
        match = _FONT_LINE.match(line)
        if match and match.group("font") == font:
            start = int(match.group("start"), 16)
            chars = "".join(slots[start + offset] for offset in range(16))
            lines[index] = f'{match.group(1)} = "{chars[:8]}" "{chars[8:]}"'


def _nonchar(lines: list[str]) -> str:
    for line in lines:
        match = re.match(r'^nonchar\s*=\s*"(.)"', line)
        if match:
            return match.group(1)
    raise ValueError("ct.cfg has no nonchar setting")


def _slot_of(slots: dict[int, str], char: str, font: str) -> int:
    for slot in sorted(slots):
        if slots[slot] == char:
            return slot
    raise ValueError(f"the {font}px font has no glyph for {char!r}")


def _require_free(slots: dict[int, str], slot: int, char: str, nonchar: str, font: str) -> None:
    current = slots.get(slot)
    if current is None:
        raise ValueError(f"ct.cfg does not define {font}px slot {slot:#x}")
    if current not in (nonchar, char):
        raise ValueError(f"{font}px slot {slot:#x} already holds {current!r}, cannot place {char!r} there")


def mapped_characters(config: Path, font: str) -> set[str]:
    """Characters the font can show according to ct.cfg, without the unused slots."""
    lines = config.read_text(encoding=CFG_ENCODING).split("\n")
    nonchar = _nonchar(lines)
    return {char for char in _read_slots(lines, font).values() if char != nonchar}
