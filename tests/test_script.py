from pathlib import Path

from cc_extrator import script

SAMPLE = """; comment line
*l11;items
;242 items
$aaa:[bladesymbol]Wood_Sword
$aab:           
*z;dialog (change this to *Z)
$bbb:
LEENE: Cyrus![nl]
   Are you leaving?
$bbc:Hello

*z:^0drF:!0dr9;places
$ccc:Truce
"""


def test_parse_reads_blocks_kinds_and_widths():
    parsed = script.parse(SAMPLE)

    assert [b.kind for b in parsed.blocks] == ["l", "z", "z"]
    assert parsed.blocks[0].width == 11
    assert parsed.blocks[1].label == "dialog"
    assert parsed.blocks[1].is_dialog
    assert parsed.blocks[2].label == "places"
    assert not parsed.blocks[2].is_dialog


def test_parse_joins_multiline_text_and_drops_the_formatting_newline_after_the_key():
    entry = script.parse(SAMPLE).blocks[1].entries[0]

    assert entry.key == "bbb"
    assert entry.text == "LEENE: Cyrus![nl]\n   Are you leaving?"


def test_parse_keeps_trailing_spaces_of_padded_names():
    assert script.parse(SAMPLE).blocks[0].entries[1].text == "           "


def test_parse_skips_comments_and_trailing_blank_lines():
    entries = script.parse(SAMPLE).blocks[1].entries

    assert [e.key for e in entries] == ["bbb", "bbc"]
    assert entries[1].text == "Hello"


def test_read_flags_a_utf8_file(tmp_path: Path):
    path = tmp_path / "ct.txt"
    path.write_bytes("*z;x\n$a:ação\n".encode("utf-8"))

    _, looks_utf8 = script.read(path)

    assert looks_utf8


def test_read_accepts_iso_8859_15(tmp_path: Path):
    path = tmp_path / "ct.txt"
    path.write_bytes("*z;x\n$a:ação\n".encode("iso-8859-15"))

    parsed, looks_utf8 = script.read(path)

    assert not looks_utf8
    assert parsed.blocks[0].entries[0].text == "ação"
