from cc_extrator.fontwidths import text_width, visible_length


def test_width_is_the_sum_of_glyph_widths():
    assert text_width("Marle") == 9 + 7 + 6 + 3 + 7


def test_spaces_and_narrow_letters():
    assert text_width("i l") == 3 + 4 + 3


def test_accented_letter_has_the_width_of_its_base():
    assert text_width("ç") == text_width("c")
    assert text_width("Ã") == text_width("A")


def test_codes_have_no_width_unless_they_print_something():
    assert text_width("a[nl]b") == 14
    assert text_width("[delay 0C]a") == 7
    assert text_width("[heartsymbol]") == 11
    assert text_width("[member1]") > 0


def test_visible_length_counts_each_code_as_one_character():
    assert visible_length("[bladesymbol]Wood_Sword") == 11
    assert visible_length("Cyclone    ") == 11
