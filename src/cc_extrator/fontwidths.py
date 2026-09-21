"""Pixel widths of the 12px dialogue font, read from the game's own width table.

An accented letter is assumed to be as wide as its base letter. Placeholders that
the game fills in at runtime (names, numbers) use estimates.
"""

import re
import unicodedata

_GROUPS = {
    3: "il!:'.,",
    4: "1() _",
    5: "It/",
    6: "EFLScfjrs»",
    7: "ABCDGHJOPQRTUVXYZabdeghknopquvxyz02356789?",
    8: "KN4=-+«",
    9: "M&%",
    11: "Wmw",
}
WIDTHS = {char: width for width, chars in _GROUPS.items() for char in chars}

DEFAULT_WIDTH = 7
SPACE_WIDTH = WIDTHS[" "]
INDENT_WIDTH = 3 * SPACE_WIDTH

_CODE = re.compile(r"\[([^\]]*)\]")
_CODE_WIDTHS = {
    "musicsymbol": 11,
    "heartsymbol": 11,
    "item": 77,
    "tech": 77,
    "monster": 77,
    "crononick": 42,
    "num8": 21,
    "num16": 35,
    "num32": 70,
}


def glyph_width(char: str) -> int:
    base = unicodedata.normalize("NFD", char)[0]
    return WIDTHS.get(base, DEFAULT_WIDTH)


def code_width(code: str) -> int:
    if code.startswith("member"):
        return 42
    return _CODE_WIDTHS.get(code, 0)


def text_width(text: str) -> int:
    """Width in pixels of a single line. Control codes count only if they print something."""
    total = 0
    position = 0
    for match in _CODE.finditer(text):
        total += sum(glyph_width(c) for c in text[position:match.start()])
        total += code_width(match.group(1))
        position = match.end()
    return total + sum(glyph_width(c) for c in text[position:])


def visible_length(text: str) -> int:
    """Length in characters where every control code counts as one character."""
    return len(_CODE.sub("X", text))
