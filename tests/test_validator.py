from pathlib import Path

from cc_extrator import script, validator

ORIGINAL = """*d;dictionary
$21:the;
*l11;items
$i1:[bladesymbol]Wood_Sword
$i2:           
*r;item types
$t1:WEAPON
*z;prompts
$p1:Enemies will attack even[nl]
if you're not ready!
*z;dialog (x)
$d1:
LEENE: Cyrus![nl]
   Are you leaving?
$d2:
CYRUS: Yes.[pause]
   I shall return!
$d3:Robos: I am Robo.
*r;screens
$s1:Buy__Sell[next]Gold
*l80;cset
$c1:ABCDEFGHIJKLMNOPQRSTUVWXYZ!?/#abcdefghijklmnopqrstuvwxyz=-+%0123456789«»:&()'., 
"""


def run(**changes):
    """Check the original with the given entries replaced. Keys are entry keys."""
    target = ORIGINAL
    for key, (old, new) in changes.items():
        assert old in target, key
        target = target.replace(old, new, 1)
    return validator.check(script.parse(ORIGINAL), script.parse(target))


def codes(report):
    return {issue.code for issue in report.issues}


def test_an_untouched_script_has_no_issues():
    report = run()

    assert report.issues == []
    assert report.translated == 0


def test_translated_strings_are_counted():
    report = run(a=("$t1:WEAPON", "$t1:ARMA"))

    assert report.translated == 1
    assert report.errors == []


def test_fixed_width_name_that_is_too_long_is_an_error():
    report = run(a=("$i1:[bladesymbol]Wood_Sword", "$i1:[bladesymbol]Espada_Madeira"))

    assert codes(report) == {"too-long"}


def test_fixed_width_name_within_the_limit_passes():
    report = run(a=("$i1:[bladesymbol]Wood_Sword", "$i1:[bladesymbol]EspMadeira"))

    assert report.errors == []


def test_an_unused_string_cannot_be_filled():
    report = run(a=("$i2:           ", "$i2:Algo"))

    assert codes(report) == {"empty"}


def test_a_used_string_cannot_be_emptied():
    report = run(a=("$t1:WEAPON", "$t1:"))

    assert codes(report) == {"empty"}


def test_item_type_longer_than_the_original_block_is_an_error():
    report = run(a=("$t1:WEAPON", "$t1:ARMAMENTO"))

    assert codes(report) == {"too-long"}


def test_missing_control_code_is_an_error():
    report = run(a=("CYRUS: Yes.[pause]", "CYRUS: Sim."))

    assert codes(report) == {"codes"}


def test_line_breaks_may_change_in_dialogue_but_not_elsewhere():
    dialogue = run(a=("LEENE: Cyrus![nl]\n   Are you leaving?", "LEENE: Cyrus! Você vai embora?"))
    prompt = run(a=("$p1:Enemies will attack even[nl]\nif you're not ready!", "$p1:Inimigos atacam mesmo se voce nao estiver pronto!"))

    assert "codes" not in codes(dialogue)
    assert "codes" in codes(prompt)


def test_changed_whitespace_after_a_pause_is_a_warning():
    report = run(a=("CYRUS: Yes.[pause]\n   I shall return!", "CYRUS: Sim.[pause]\nEu voltarei!"))

    assert [i.code for i in report.warnings] == ["pause-layout"]
    assert report.errors == []


def test_accents_are_rejected_until_allowed():
    text = ("$t1:WEAPON", "$t1:ARMA")
    blocked = run(a=("LEENE: Cyrus![nl]\n   Are you leaving?", "LEENE: Ação!"))
    allowed = validator.check(
        script.parse(ORIGINAL),
        script.parse(ORIGINAL.replace("LEENE: Cyrus![nl]\n   Are you leaving?", "LEENE: Ação!")),
        validator.Options(allow_accents=True),
    )

    assert codes(blocked) == {"accents"}
    assert allowed.errors == []
    assert text


def test_characters_outside_the_font_are_errors():
    report = run(a=("$d3:Robos: I am Robo.", '$d3:Robos: "oi"; Eu sou Robo.'))

    assert codes(report) == {"characters"}


def test_typographic_characters_get_a_specific_message():
    report = run(a=("$d3:Robos: I am Robo.", "$d3:Robos: Eu sou Robo…"))

    assert "ellipsis" in report.errors[0].message


def test_underscore_is_only_valid_in_eight_pixel_fields():
    dialogue = run(a=("$d3:Robos: I am Robo.", "$d3:Robos: eu_sou Robo."))
    item = run(a=("$i1:[bladesymbol]Wood_Sword", "$i1:[bladesymbol]Esp_Pau"))

    assert codes(dialogue) == {"characters"}
    assert item.errors == []


def test_robo_must_stay_the_rename_token():
    report = run(a=("$d3:Robos: I am Robo.", "$d3:Robos: Eu sou Robo. Robo aqui."))

    assert "names" in codes(report)


def test_page_with_more_than_four_lines_is_an_error():
    lines = "[nl]".join(["linha curta"] * 5)
    report = run(a=("$d3:Robos: I am Robo.", f"$d3:Robos: {lines}"))

    assert codes(report) == {"page-lines"}


def test_long_paragraph_that_wraps_into_four_lines_passes():
    text = " ".join(["palavra"] * 12)
    report = run(a=("$d3:Robos: I am Robo.", f"$d3:Robos: {text}"))

    assert report.errors == []


def test_word_longer_than_a_line_is_an_error():
    report = run(a=("$d3:Robos: I am Robo.", "$d3:Robos: Pneumoultramicroscopicossilicovulcanoconiose"))

    assert codes(report) == {"long-word"}


def test_a_control_code_with_a_space_is_not_split_by_the_wrapper_estimate():
    original = ORIGINAL.replace("$d3:Robos: I am Robo.", "$d3:Robos: One[nl]\ntwo[nl]\nthree[nl]\nfour ...[delay 08] ...end")
    report = validator.check(script.parse(original), script.parse(original.replace("Robos: One", "Robos: Um")))

    assert report.errors == []


def test_single_line_block_ceiling_is_measured_from_the_original():
    report = run(a=("$p1:Enemies will attack even[nl]\nif you're not ready!", "$p1:Inimigos atacam mesmo[nl]\nse voce nao estiver pronto em nenhuma hipotese!"))

    assert "width" in codes(report)


def test_protected_blocks_cannot_be_edited():
    dictionary = run(a=("$21:the;", "$21:o;"))
    screens = run(a=("$s1:Buy__Sell[next]Gold", "$s1:Comprar[next]Ouro"))
    allowed = validator.check(
        script.parse(ORIGINAL),
        script.parse(ORIGINAL.replace("$s1:Buy__Sell[next]Gold", "$s1:Comprar[next]Ouro")),
        validator.Options(translate_screens=True),
    )

    assert codes(dictionary) == {"protected"}
    assert codes(screens) == {"protected"}
    assert allowed.errors == []


def test_deleted_or_renamed_keys_are_a_structure_error():
    report = run(a=("$t1:WEAPON", "$t9:WEAPON"))

    assert codes(report) == {"structure"}


def test_changed_block_header_is_a_structure_error():
    report = run(a=("*z;prompts", "*z;prompt"))

    assert codes(report) == {"structure"}


def test_utf8_file_reports_only_the_encoding():
    report = validator.check(script.parse(ORIGINAL), script.parse(ORIGINAL), utf8_target=True)

    assert codes(report) == {"encoding"}


def test_glossary_entries_must_match_the_script(tmp_path: Path):
    glossary = tmp_path / "glossary.tsv"
    glossary.write_text("kind\tkey\tenglish\tvisible_len\tmax_visible\tptbr\nitem type\tt1\tWEAPON\t6\t10\tARMA\n", encoding="utf-8")
    target = ORIGINAL.replace("$t1:WEAPON", "$t1:ARMAS")

    report = validator.check(script.parse(ORIGINAL), script.parse(target), validator.Options(glossary=glossary))

    assert codes(report) == {"glossary"}


def test_glossary_rows_without_a_translation_are_ignored(tmp_path: Path):
    glossary = tmp_path / "glossary.tsv"
    glossary.write_text("kind\tkey\tenglish\tvisible_len\tmax_visible\tptbr\nitem type\tt1\tWEAPON\t6\t10\t\n", encoding="utf-8")

    report = validator.check(script.parse(ORIGINAL), script.parse(ORIGINAL), validator.Options(glossary=glossary))

    assert report.issues == []


def test_report_lists_each_code_with_counts():
    text = validator.format_report(run(a=("$t1:WEAPON", "$t1:ARMAMENTO")))

    assert "too-long: 1" in text
    assert "1 errors" in text


def test_accents_follow_the_font_listed_in_ct_cfg(tmp_path: Path):
    config = tmp_path / "ct.cfg"
    config.write_bytes('nonchar = "¶"\nfont12_100 = "ã¶¶¶¶¶¶¶" "¶¶¶¶¶¶¶¶"\nfont8_80 = "ã¶¶¶¶¶¶¶" "¶¶¶¶¶¶¶¶"\n'.encode("iso-8859-15"))
    options = validator.Options(config=config)
    mapped = ORIGINAL.replace("$d3:Robos: I am Robo.", "$d3:Robos: não sei")
    missing = ORIGINAL.replace("$d3:Robos: I am Robo.", "$d3:Robos: não é")

    accepted = validator.check(script.parse(ORIGINAL), script.parse(mapped), options)
    rejected = validator.check(script.parse(ORIGINAL), script.parse(missing), options)

    assert accepted.errors == []
    assert codes(rejected) == {"accents"}
    assert "cc-extrator accents" in rejected.errors[0].message
