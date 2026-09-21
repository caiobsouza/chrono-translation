from cc_extrator import budget

FITTING = """Loading dialog...
> Original script size: 241508 bytes; new script size: 30000 bytes
> Saved: 81208 bytes (33.6% off); dictionary size: 395 bytes
Free space: 02:96/1 06:854/1 18:11459/2 3F:28965/12 - total: 41374 bytes
Writing strings...
Free space: 02:15/1 06:2/1 18:1419/1 3F:11343/4 - total: 12779 bytes
"""

OVERFLOWING = """> Original script size: 260000 bytes; new script size: 175000 bytes
Free space: 02:96/1 18:11459/2 36:9747/2 - total: 21302 bytes
ERROR: Page 18 doesn't have 11602 bytes of space (only 11459 there)!
ERROR: Organization to page 18 failed
ERROR: Page 36 doesn't have 9867 bytes of space (only 9747 there)!
ERROR: Organization to page 36 failed
Error: Too long text
Free space: 02:15/1 - total: 15 bytes
"""


def test_parse_reads_sizes_and_the_room_before_and_after_writing():
    result = budget.parse_output(FITTING)

    assert (result.raw, result.packed) == (241508, 30000)
    assert result.capacity == {"02": 96, "06": 854, "18": 11459, "3F": 28965}
    assert result.remaining == {"02": 15, "06": 2, "18": 1419, "3F": 11343}
    assert result.capacity_total == 41374
    assert result.fits


def test_used_space_is_capacity_minus_what_is_left():
    result = budget.parse_output(FITTING)

    assert result.used("18") == 11459 - 1419
    assert result.used("3F") == 28965 - 11343


def test_overflowing_pages_are_collected_with_their_shortfall():
    result = budget.parse_output(OVERFLOWING)

    assert not result.fits
    assert result.overflows == {"18": (11602, 11459), "36": (9867, 9747)}
    assert result.deficit == 143 + 120


def test_other_errors_are_kept_but_page_organization_noise_is_not():
    result = budget.parse_output(OVERFLOWING)

    assert result.other_errors == ["Error: Too long text"]


def test_output_without_any_report_gives_an_empty_measurement():
    result = budget.parse_output("nothing useful")

    assert result.capacity_total == 0 and result.packed == 0


def test_report_for_a_fitting_script_lists_the_tightest_pages():
    english = budget.parse_output(FITTING)

    text = budget.format_report(english, None)

    assert "FITS" in text
    assert "tightest pages: 06 (99.8%), 18 (87.6%), 02 (84.4%)" in text
    assert "English" in text and "Translation" not in text


def test_report_shows_growth_over_english_for_a_translation():
    english = budget.parse_output(FITTING)
    translation = budget.parse_output(FITTING.replace("241508", "260000"))

    text = budget.format_report(english, translation)

    assert "+7.7% raw" in text
    assert "growth tests fitted up to" in text


def test_report_for_an_overflow_says_how_much_to_cut():
    english = budget.parse_output(FITTING)
    translation = budget.parse_output(OVERFLOWING)

    text = budget.format_report(english, translation)

    assert "OVERFLOW     2 pages do not fit: 18 (+143 B), 36 (+120 B)" in text
    assert "cut about" in text
    assert "OVERFLOW" in text.splitlines()[-1] or "  OVERFLOW" in text
