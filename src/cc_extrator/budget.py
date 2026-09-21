"""Space budget of the script, read from the output of ctinsert.

The cartridge has a fixed amount of room for compressed text, spread over pages.
ctinsert prints the room before and after writing the strings, and an error for
every page that does not fit, so a run of it is a measurement.
"""

import re
from dataclasses import dataclass, field

_SIZES = re.compile(r"Original script size: (\d+) bytes; new script size: (\d+) bytes")
_FREE_LINE = re.compile(r"^Free space: (.*) - total: (\d+) bytes")
_PAGE = re.compile(r"([0-9A-Fa-f]{2}):(\d+)/\d+")
_OVERFLOW = re.compile(r"ERROR: Page ([0-9A-Fa-f]{2}) doesn't have (\d+) bytes of space \(only (\d+) there\)")
_ERROR = re.compile(r"^\s*(ERROR|Error)\b")


@dataclass
class Measurement:
    raw: int = 0
    packed: int = 0
    capacity: dict[str, int] = field(default_factory=dict)
    remaining: dict[str, int] = field(default_factory=dict)
    overflows: dict[str, tuple[int, int]] = field(default_factory=dict)
    other_errors: list[str] = field(default_factory=list)

    @property
    def capacity_total(self) -> int:
        return sum(self.capacity.values())

    @property
    def fits(self) -> bool:
        return not self.overflows

    @property
    def deficit(self) -> int:
        return sum(needed - available for needed, available in self.overflows.values())

    def used(self, page: str) -> int:
        return self.capacity[page] - self.remaining.get(page, 0)


def parse_output(text: str) -> Measurement:
    result = Measurement()
    free_lines: list[dict[str, int]] = []
    for line in re.split(r"[\r\n]+", text):
        sizes = _SIZES.search(line)
        if sizes:
            result.raw, result.packed = int(sizes.group(1)), int(sizes.group(2))
        free = _FREE_LINE.match(line)
        if free:
            free_lines.append({page.upper(): int(size) for page, size in _PAGE.findall(free.group(1))})
        overflow = _OVERFLOW.search(line)
        if overflow:
            page = overflow.group(1).upper()
            result.overflows[page] = (int(overflow.group(2)), int(overflow.group(3)))
        elif _ERROR.match(line) and "Organization to page" not in line:
            result.other_errors.append(line.strip())
    if free_lines:
        result.capacity = free_lines[0]
        result.remaining = free_lines[-1] if len(free_lines) > 1 else {}
    return result


FITS_UP_TO = 9.5      # total raw growth over English that fitted in the growth tests
OVERFLOW_AT = 12.8    # total raw growth over English where pages began to overflow


def format_report(english: Measurement, translation: Measurement | None) -> str:
    current = translation or english
    lines = [f"English      raw {english.raw:>8,} B   packed {english.packed:>8,} B"]
    if translation is not None:
        growth = 100 * (translation.raw / english.raw - 1) if english.raw else 0
        lines.append(f"Translation  raw {translation.raw:>8,} B   packed {translation.packed:>8,} B   ({growth:+.1f}% raw)")
    lines.append(f"Text space   {current.capacity_total:>8,} B on {len(current.capacity)} pages")
    lines += _verdict(english, current)
    if translation is not None:
        lines.append(f"Reference    growth tests fitted up to +{FITS_UP_TO}% and overflowed from +{OVERFLOW_AT}% over the English script")
    lines += _pages(current)
    for error in current.other_errors[:5]:
        lines.append(f"Other ctinsert error: {error}")
    return "\n".join(lines)


def _verdict(english: Measurement, current: Measurement) -> list[str]:
    if not current.fits:
        ratio = current.packed / current.raw if current.raw else 1
        pages = ", ".join(f"{page} (+{needed - available:,} B)" for page, (needed, available) in sorted(current.overflows.items()))
        extra_raw = current.deficit / ratio
        cut = 100 * extra_raw / english.raw if english.raw else 0
        return [
            f"OVERFLOW     {len(current.overflows)} pages do not fit: {pages}",
            f"             cut about {extra_raw:,.0f} B of raw text ({cut:.1f}% of the English script) to fit",
        ]
    free = current.capacity_total - current.packed
    tight = sorted(current.capacity, key=lambda page: -current.used(page) / current.capacity[page])[:3]
    tightest = ", ".join(f"{page} ({100 * current.used(page) / current.capacity[page]:.1f}%)" for page in tight)
    return [
        f"FITS         {current.packed:,} of {current.capacity_total:,} B used ({100 * current.packed / current.capacity_total:.1f}%), {free:,} B free",
        f"             tightest pages: {tightest}",
    ]


def _pages(current: Measurement) -> list[str]:
    lines = ["", "page   capacity     used     free   used%"]
    for page in sorted(current.capacity, key=lambda p: int(p, 16)):
        capacity = current.capacity[page]
        if page in current.overflows:
            needed, available = current.overflows[page]
            lines.append(f"{page:>4} {capacity:>10,} {needed:>8,} {available - needed:>8,} {100 * needed / capacity:>6.1f}%  OVERFLOW")
            continue
        used = current.used(page)
        lines.append(f"{page:>4} {capacity:>10,} {used:>8,} {current.remaining.get(page, 0):>8,} {100 * used / capacity:>6.1f}%")
    return lines
