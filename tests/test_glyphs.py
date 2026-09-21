import struct
from pathlib import Path

from cc_extrator import glyphs, tga

T, K, W, O = glyphs.TRANSPARENT, glyphs.SHADOW, glyphs.WHITE, glyphs.OUTSIDE


def letter_12px(width: int = 7, top: int = 2) -> glyphs.Glyph:
    """A plain block letter: white body, black shadow column, olive beyond the width."""
    cell = [[T if x < width else O for x in range(12)] for _ in range(12)]
    for y in range(top, 8):
        for x in range(width - 1):
            cell[y][x] = W
        cell[y][width - 1] = K
    cell[8] = [K if x < width else O for x in range(12)]
    return cell


def test_lowercase_accent_goes_in_the_two_rows_above_the_letter():
    result = glyphs.build_glyph(letter_12px(), "acute", capital=False, sheet=glyphs.SHEET_12PX)

    assert any(value == W for value in result[0]) and any(value == W for value in result[1])
    assert result[2:] == letter_12px()[2:]


def test_the_width_marker_survives_an_accent():
    result = glyphs.build_glyph(letter_12px(width=7), "tilde", capital=False, sheet=glyphs.SHEET_12PX)

    assert glyphs.glyph_width(result, glyphs.SHEET_12PX) == 7
    assert all(row[7:] == [O] * 5 for row in result)


def test_narrow_letters_are_not_written_past_their_width():
    result = glyphs.build_glyph(letter_12px(width=5), "circumflex", capital=False, sheet=glyphs.SHEET_12PX)

    assert all(row[5:] == [O] * 7 for row in result)


def test_capital_is_shortened_but_keeps_its_baseline():
    capital = letter_12px(top=0)
    result = glyphs.build_glyph(capital, "acute", capital=True, sheet=glyphs.SHEET_12PX)

    assert result[8] == capital[8]
    body_rows = [y for y in range(2, 9) if W in result[y] or K in result[y]]
    assert body_rows == list(range(2, 9))


def test_dotless_i_loses_its_dot():
    letter = letter_12px(width=3, top=0)
    result = glyphs.build_glyph(letter, "acute", capital=False, sheet=glyphs.SHEET_12PX, dotless=True)

    assert W in result[0]  # only the accent is left up there
    assert result[2:] == letter[2:]


def test_cedilla_uses_the_free_rows_below_the_letter_in_the_12px_font():
    result = glyphs.build_glyph(letter_12px(), "cedilla", capital=False, sheet=glyphs.SHEET_12PX)

    assert any(value == W for value in result[9])
    assert result[:9] == letter_12px()[:9]


def test_8px_cedilla_replaces_the_bottom_shadow_row():
    base = [[T] * 8 for _ in range(8)]
    for y in range(2, 7):
        base[y] = [W, W, W, W, W, W, K, T]
    base[7] = [T, K, K, K, K, K, K, T]

    result = glyphs.build_glyph(base, "cedilla", capital=False, sheet=glyphs.SHEET_8PX)

    assert result[7] != base[7]
    assert result[:7] == base[:7]


def make_fonts(work: Path) -> None:
    def image(path: Path, width: int, height: int, sheet: glyphs.Sheet, base: glyphs.Glyph) -> None:
        header = struct.pack("<BBBHHBHHHHBB", 0, 1, 1, 0, 6, 24, 0, 0, width, height, 8, 0)
        rows = [[T] * width for _ in range(height)]
        img = tga.Image(width, height, rows, header + bytes(18), bottom_left_origin=True)
        font = glyphs.FontImage(img, sheet)
        for slot in range((width - 1) // sheet.pitch * ((height - 1) // sheet.pitch)):
            font.put(slot, base)
        img.save(path)

    image(work / "ct16fn.tga", 417, 313, glyphs.SHEET_12PX, letter_12px())
    eight = [[W] * 7 + [T] for _ in range(8)]
    image(work / "ct8fn.tga", 289, 73, glyphs.SHEET_8PX, eight)


def make_config(work: Path) -> None:
    lines = ['nonchar = "¶"']
    blank = '"¶¶¶¶¶¶¶¶" "¶¶¶¶¶¶¶¶"'
    lines += [f"font12_A0 = \"aeioucAE\" \"IOUC¶¶¶¶\""]
    lines += [f"font12_{start:X} = {blank}" for start in (0x100, 0x110)]
    lines += [f"font8_80 = {blank}", f"font8_90 = {blank}", "font8_A0 = \"aeioucAE\" \"IOUC¶¶¶¶\""]
    (work / "ct.cfg").write_bytes("\n".join(lines).encode(glyphs.CFG_ENCODING))


def test_add_accents_registers_every_letter_in_both_fonts(tmp_path: Path):
    make_fonts(tmp_path)
    make_config(tmp_path)

    result = glyphs.add_accents(tmp_path)

    assert "".join(result.font12) == glyphs.ACCENTED
    assert "".join(result.font8) == glyphs.ACCENTED
    config = tmp_path / "ct.cfg"
    assert set(glyphs.ACCENTED) <= glyphs.mapped_characters(config, "12")
    assert set(glyphs.ACCENTED) <= glyphs.mapped_characters(config, "8")


def test_add_accents_draws_the_glyphs_into_the_images(tmp_path: Path):
    make_fonts(tmp_path)
    make_config(tmp_path)

    glyphs.add_accents(tmp_path)

    font = glyphs.FontImage(tga.read(tmp_path / "ct16fn.tga"), glyphs.SHEET_12PX)
    assert any(value == W for value in font.get(0x100)[0])  # the first accented letter has a mark on top
    assert font.get(0x100)[7:] == letter_12px()[7:]


def test_add_accents_can_run_twice(tmp_path: Path):
    make_fonts(tmp_path)
    make_config(tmp_path)

    glyphs.add_accents(tmp_path)
    first = (tmp_path / "ct16fn.tga").read_bytes(), (tmp_path / "ct.cfg").read_bytes()
    glyphs.add_accents(tmp_path)

    assert ((tmp_path / "ct16fn.tga").read_bytes(), (tmp_path / "ct.cfg").read_bytes()) == first


def test_add_accents_refuses_to_overwrite_a_used_slot(tmp_path: Path):
    make_fonts(tmp_path)
    make_config(tmp_path)
    config = tmp_path / "ct.cfg"
    config.write_bytes(config.read_bytes().replace('font12_100 = "¶'.encode(glyphs.CFG_ENCODING), 'font12_100 = "Z'.encode(glyphs.CFG_ENCODING)))

    try:
        glyphs.add_accents(tmp_path)
    except ValueError as error:
        assert "already holds" in str(error)
    else:
        raise AssertionError("expected a ValueError")
