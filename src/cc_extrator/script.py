"""Parser for the Chronotools script file (ct.txt)."""

import re
from dataclasses import dataclass, field
from pathlib import Path

ENCODING = "iso-8859-15"

_BLOCK = re.compile(r"^\*([A-Za-z])(\d*)")
_ENTRY = re.compile(r"^\$([^:]*):(.*)$")


@dataclass
class Entry:
    key: str
    text: str


@dataclass
class Block:
    header: str
    kind: str
    width: int | None
    label: str
    line: str
    entries: list[Entry] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)

    @property
    def is_dialog(self) -> bool:
        return self.kind in "zZ" and self.label.startswith("dialog")


@dataclass
class Script:
    blocks: list[Block]


def parse(text: str) -> Script:
    blocks: list[Block] = []
    block: Block | None = None
    entry: Entry | None = None
    for line in text.split("\n"):
        if line.startswith(";"):
            note = line[1:].strip()
            if block is not None and entry is None and note and set(note) != {"-"}:
                block.comments.append(note)
            continue
        if line.startswith("*"):
            block = _new_block(line)
            blocks.append(block)
            entry = None
            continue
        match = _ENTRY.match(line)
        if match and block is not None:
            entry = Entry(match.group(1), match.group(2))
            block.entries.append(entry)
        elif entry is not None:
            entry.text += "\n" + line
    for parsed in blocks:
        for item in parsed.entries:
            item.text = item.text.removeprefix("\n").rstrip("\n")
    return Script(blocks)


def read(path: Path) -> tuple[Script, bool]:
    """Read a script file. The flag is True when the file looks like UTF-8 instead of ISO-8859-15."""
    raw = path.read_bytes()
    looks_utf8 = False
    if any(byte > 127 for byte in raw):
        try:
            raw.decode("utf-8")
            looks_utf8 = True
        except UnicodeDecodeError:
            pass
    return parse(raw.decode(ENCODING)), looks_utf8


def _new_block(line: str) -> Block:
    head, _, label = line.partition(";")
    match = _BLOCK.match(head)
    kind = match.group(1) if match else "?"
    width = int(match.group(2)) if match and match.group(2) else None
    return Block(head, kind, width, label.split("(")[0].strip(), line)
