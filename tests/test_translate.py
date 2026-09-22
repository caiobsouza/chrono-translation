from pathlib import Path
from types import SimpleNamespace

import pytest

from cc_extrator import script, translate

ORIGINAL = """*z;dialog (x)
;600ad (castle)
;-----------------
$d1:
LEENE: Cyrus![nl]
   Are you leaving?
$d2:
CYRUS: Yes.[pause]
   I shall return!
$d3:Come on, sleepy head!
*z;prompts
$p1:Enemies will attack even[nl]
if you're not ready!
*z;eps
$e1:   The Millennial Fair
$e2:  The Queen Returns
*z;tres msg
$t1:[nl]
                Got 1 [item]!
*l11;items
$i1:[bladesymbol]Wood_Sword
"""


def usage(fresh=1000, written=0, read=0, output=500):
    return SimpleNamespace(input_tokens=fresh, cache_creation_input_tokens=written, cache_read_input_tokens=read, output_tokens=output)


class FakeClient:
    """Answers with whatever the test function returns for the prompt it is given."""

    def __init__(self, answer, tokens=None):
        self.answer, self.calls, self.tokens = answer, [], tokens or usage()
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.answer(kwargs["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], usage=self.tokens, stop_reason="end_turn")


@pytest.fixture
def work(tmp_path):
    (tmp_path / "ct.en.txt").write_bytes(ORIGINAL.encode("iso-8859-15"))
    (tmp_path / "ct.txt").write_bytes(ORIGINAL.encode("iso-8859-15"))
    (tmp_path / "ct.cfg").write_bytes('nonchar = "¶"\nfont12_100 = "ãáéçóêí¶" "¶¶¶¶¶¶¶¶"\nfont8_80 = "¶¶¶¶¶¶¶¶" "¶¶¶¶¶¶¶¶"\n'.encode("iso-8859-15"))
    notebook = tmp_path / "notebook"
    notebook.mkdir()
    (notebook / "translation-guidelines.md").write_text("GUIDELINES")
    return tmp_path


def options(work, **changes):
    values = dict(notebook=work / "notebook", confirmed=True, batch_size=10, ledger=work / "spend-ledger.json")
    values.update(changes)
    return translate.Options(**values)


def test_encode_replaces_layout_codes_with_single_symbols():
    encoded = translate.encode("LEENE: Cyrus![nl]\n   Are you leaving?[pause]\n   Yes.")

    assert encoded.compact == "LEENE: Cyrus!¶Are you leaving?¦Yes."
    assert encoded.newline_tails == ["\n   "] and encoded.pause_tails == ["\n   "]


def test_decode_restores_the_original_layout_whitespace():
    source = "LEENE: Cyrus![nl]\n   Are you leaving?[pause]\n   Yes."
    encoded = translate.encode(source)

    assert translate.decode(encoded.compact, encoded, source) == source


def test_decode_adds_extra_line_breaks_with_the_same_indent():
    source = "LEENE: Cyrus![nl]\n   Are you leaving?"
    encoded = translate.encode(source)

    result = translate.decode("LEENE: Cyrus!¶Você vai¶embora?", encoded, source)

    assert result == "LEENE: Cyrus![nl]\n   Você vai[nl]\n   embora?"


def test_other_codes_survive_the_round_trip():
    source = "You got 1 [item]![delay 0C] Nice."

    assert translate.decode(translate.encode(source).compact, translate.encode(source), source) == source


def test_normalize_replaces_typographic_characters():
    assert translate.normalize("“Olá” — não…") == "«Olá» - não..."


def test_parse_answer_reads_id_lines_and_ignores_chatter():
    text = "Here you go:\n3|Olá, mundo!\n 4 | Segunda linha  \nnot a line"

    assert translate.parse_answer(text) == {3: "Olá, mundo!", 4: "Segunda linha"}


def test_select_skips_manual_and_non_text_blocks_and_already_translated_strings(work):
    source, _ = script.read(work / "ct.en.txt")
    target, _ = script.read(work / "ct.txt")
    target.blocks[0].entries[0].text = "changed"

    items = translate.select(source, target, translate.Options())

    assert [item.key for item in items] == ["d2", "d3", "p1", "e1", "e2", "i1"]


def test_select_can_filter_by_block_and_limit(work):
    source, _ = script.read(work / "ct.en.txt")

    items = translate.select(source, source, translate.Options(blocks=["dialog"], limit=2))

    assert [item.key for item in items] == ["d1", "d2"]


def test_batches_stay_inside_one_block_and_carry_context(work):
    source, _ = script.read(work / "ct.en.txt")
    items = translate.select(source, source, translate.Options())

    batches = translate.make_batches(items, size=2)

    assert [[i.key for i in b.items] for b in batches] == [["d1", "d2"], ["d3"], ["p1"], ["e1", "e2"], ["i1"]]
    assert batches[1].context == ["LEENE: Cyrus!¶Are you leaving?", "CYRUS: Yes.¦I shall return!"]


def test_cost_counts_cache_reads_at_a_tenth_and_writes_at_a_quarter_more():
    tokens = usage(fresh=1_000_000, written=1_000_000, read=1_000_000, output=1_000_000)

    assert translate.cost_of("claude-sonnet-5", tokens) == pytest.approx(2.0 + 2.5 + 0.2 + 10.0)


def test_ledger_persists_and_sums(tmp_path):
    ledger = translate.Ledger(tmp_path / "ledger.json")
    ledger.add("claude-sonnet-5", usage(), 0.25, "one")
    ledger.add("claude-sonnet-5", usage(), 0.5, "two")

    assert translate.Ledger(tmp_path / "ledger.json").total == pytest.approx(0.75)


def test_nothing_is_sent_without_confirmation(work):
    client = FakeClient(lambda prompt: "")

    summary = translate.run(work, options(work, confirmed=False), client, out=lambda message: None)

    assert client.calls == [] and summary.calls == 0


def test_a_full_batch_is_translated_written_and_paid_for(work):
    def answer(prompt):
        return "0|LEENE: Cyrus!¶Você vai embora?\n1|CYRUS: Sim.¦Eu voltarei!\n2|Vamos, dorminhoco!"

    client = FakeClient(answer)

    summary = translate.run(work, options(work, blocks=["dialog"]), client, out=lambda message: None)

    written, _ = script.read(work / "ct.txt")
    assert [e.text for e in written.blocks[0].entries] == ["LEENE: Cyrus![nl]\n   Você vai embora?", "CYRUS: Sim.[pause]\n   Eu voltarei!", "Vamos, dorminhoco!"]
    assert summary.translated == 3 and summary.failed == [] and summary.calls == 1
    assert (work / "spend-ledger.json").is_file()
    assert client.calls[0]["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "600ad (castle)" in client.calls[0]["messages"][0]["content"]


def test_a_string_that_fails_the_checks_is_repaired_once_and_reverted_if_still_bad(work):
    calls = []

    def answer(prompt):
        calls.append(prompt)
        return "0|LEENE: Cyrus![code]\n1|CYRUS: Sim.¦Eu voltarei!\n2|Vamos!"

    client = FakeClient(answer)

    summary = translate.run(work, options(work, blocks=["dialog"]), client, out=lambda message: None)

    written, _ = script.read(work / "ct.txt")
    assert written.blocks[0].entries[0].text == "LEENE: Cyrus![nl]\n   Are you leaving?"
    assert summary.failed == ["d1"] and summary.calls == 2
    assert "Rewrite only these strings" in calls[1]


def test_the_total_cap_stops_the_run_before_the_call(work):
    client = FakeClient(lambda prompt: "0|x")
    ledger = translate.Ledger(work / "spend-ledger.json")
    ledger.add("claude-sonnet-5", usage(), 9.49, "earlier")

    summary = translate.run(work, options(work, total_cap=9.50), client, out=lambda message: None)

    assert client.calls == [] and "total cap" in summary.stopped


def test_the_run_cap_stops_after_the_batch_that_reaches_it(work):
    client = FakeClient(lambda prompt: "0|LEENE: Cyrus!¶Ok", tokens=usage(fresh=0, output=200_000))

    summary = translate.run(work, options(work, batch_size=1, max_cost=1.0, blocks=["dialog"]), client, out=lambda message: None)

    assert summary.calls == 1 and "this run reached" in summary.stopped


def test_centred_blocks_are_recentred_like_the_originals(work):
    client = FakeClient(lambda prompt: "0|A Feira do Milênio")

    translate.run(work, options(work, blocks=["eps"], limit=1), client, out=lambda message: None)

    written, _ = script.read(work / "ct.txt")
    text = written.blocks[2].entries[0].text
    assert text.lstrip() == "A Feira do Milênio" and text.startswith(" ")


def test_character_notes_are_looked_up_by_speaker_label(tmp_path):
    directory = tmp_path / "characters"
    directory.mkdir()
    (directory / "README.md").write_text("| Character | Labels | File |\n|---|---|---|\n| Ayla | `Ayla` | `ayla.md` |\n")
    (directory / "ayla.md").write_text("# Ayla\n\n## Voice in the English script\n\n- Third person.\n\n## Proposed pt-BR voice\n\n- Short.\n\n## Sample lines\n\n- Me Ayla.\n")

    notes = translate.CharacterNotes(directory).for_labels(["Ayla"])

    assert "Third person" in notes and "Short" in notes and "Me Ayla" not in notes


def test_the_system_prompt_lists_only_glossary_rows_that_have_a_translation(tmp_path):
    glossary = tmp_path / "glossary.tsv"
    glossary.write_text("kind\tkey\tenglish\tvisible_len\tmax_visible\tptbr\nplace name\ta\tTruce\t5\t14\tTruce\nitem name\tb\tTonic\t5\t11\t\n", encoding="utf-8")

    system = translate.build_system("RULES", glossary)

    assert "place name: Truce = Truce" in system and "Tonic" not in system


def test_measured_output_ratio_only_uses_calls_of_the_same_model(tmp_path):
    ledger = translate.Ledger(tmp_path / "ledger.json")
    ledger.add("claude-sonnet-5", usage(output=1000), 0.01, "a", strings_tokens=1000)
    ledger.add("claude-opus-5", usage(output=3000), 0.10, "b", strings_tokens=1000)

    assert ledger.output_per_string_token("claude-sonnet-5") == pytest.approx(1.0)
    assert ledger.output_per_string_token("claude-opus-5") == pytest.approx(3.0)
    assert ledger.output_per_string_token("claude-haiku-4-5") is None


def test_narrow_blocks_get_their_pixel_ceiling_in_the_prompt_and_a_tighter_hint(work):
    source, _ = script.read(work / "ct.en.txt")
    items = translate.select(source, source, translate.Options(blocks=["prompts"]))
    batch = translate.make_batches(items, 10)[0]

    prompt = translate.build_user(batch, translate.CharacterNotes(work / "none"))

    assert "Hard limit for this block: each line at most" in prompt
    assert "at most 2 line(s)" in prompt


def test_dialogue_gets_no_pixel_ceiling_because_the_wrapper_handles_it(work):
    source, _ = script.read(work / "ct.en.txt")
    batch = translate.make_batches(translate.select(source, source, translate.Options(blocks=["dialog"])), 10)[0]

    assert "Hard limit" not in translate.build_user(batch, translate.CharacterNotes(work / "none"))


def test_the_hint_never_passes_the_pixel_ceiling():
    assert translate.budget_hint("A" * 40, ceiling_px=120) == 20
    assert translate.budget_hint("A" * 40) == 44


def test_a_length_hint_echoed_by_the_model_is_stripped_from_the_answer():
    assert translate.parse_answer("3|Rouba do inimigo <=19") == {3: "Rouba do inimigo"}


def test_the_repair_line_format_id_prefix_is_accepted():
    assert translate.parse_answer("id 12|Olá\nID 13 | Oi") == {12: "Olá", 13: "Oi"}


def test_length_limits_are_a_separate_line_so_they_cannot_be_copied_into_a_translation(work):
    source, _ = script.read(work / "ct.en.txt")
    batch = translate.make_batches(translate.select(source, source, translate.Options(blocks=["dialog"])), 10)[0]

    prompt = translate.build_user(batch, translate.CharacterNotes(work / "none"))

    assert "<=" not in prompt.split("Translate:")[1].split("Length limits")[0]
    assert "Length limits (most characters per id): 0=" in prompt


def test_every_answer_is_kept_in_a_log_for_diagnosis(work):
    client = FakeClient(lambda prompt: "0|LEENE: Cyrus!¶Ok")

    translate.run(work, options(work, blocks=["dialog"], limit=1), client, out=lambda message: None)

    lines = (work / "translation-log.jsonl").read_text().splitlines()
    assert lines and "LEENE: Cyrus!" in lines[0]


def test_redo_invalid_selects_translated_strings_that_fail_the_validator(work):
    source, _ = script.read(work / "ct.en.txt")
    target, _ = script.read(work / "ct.txt")
    target.blocks[0].entries[0].text = "LEENE: Cyrus![code]"
    target.blocks[0].entries[2].text = "Vamos, dorminhoco!"
    (work / "ct.txt").write_bytes(ORIGINAL.replace("LEENE: Cyrus![nl]\n   Are you leaving?", "LEENE: Cyrus![code]").replace("Come on, sleepy head!", "Vamos, dorminhoco!").encode("iso-8859-15"))

    invalid = translate._invalid_keys(work, source, script.read(work / "ct.txt")[0])
    items = translate.select(source, script.read(work / "ct.txt")[0], translate.Options(blocks=["dialog"], redo_invalid=True), invalid)

    assert [item.key for item in items] == ["d1", "d2"]


def test_thinking_can_be_turned_off_for_cheaper_runs(work):
    client = FakeClient(lambda prompt: "0|LEENE: Cyrus!¶Ok")

    translate.run(work, options(work, blocks=["dialog"], limit=1, thinking=False), client, out=lambda message: None)

    assert client.calls[0]["thinking"] == {"type": "disabled"}


def test_thinking_stays_at_the_model_default_unless_turned_off(work):
    client = FakeClient(lambda prompt: "0|LEENE: Cyrus!¶Ok")

    translate.run(work, options(work, blocks=["dialog"], limit=1), client, out=lambda message: None)

    assert "thinking" not in client.calls[0]


def test_relayout_restores_the_whitespace_after_cls_and_pause_from_the_english():
    source = "Yes![delay 06]\n[cls]\n   Then go.[pause]\n   Now!"
    translated = "Sim![delay 06] [cls]    Então vá.[pause] Agora!"

    assert translate.relayout(source, translated) == "Sim![delay 06] [cls]\n   Então vá.[pause]\n   Agora!"


def test_relayout_removes_a_space_where_the_english_had_none():
    assert translate.relayout("One[pause]Two", "Um[pause] Dois") == "Um[pause]Dois"


def test_relayout_leaves_text_without_those_codes_alone():
    assert translate.relayout("Hello[nl]\n   there", "Olá[nl]\n   aí") == "Olá[nl]\n   aí"


def test_reflow_joins_lines_that_split_a_sentence():
    text = "Lucca: Você não sabe quanto tempo o[nl]\n   Enertron vai durar."

    assert translate.reflow(text) == "Lucca: Você não sabe quanto tempo o Enertron vai durar."


def test_reflow_keeps_breaks_after_a_sentence_end():
    text = "Não! Ter poder![nl]\n   Lutamos, ganhamos mais poder!"

    assert translate.reflow(text) == text


def test_reflow_keeps_the_break_before_a_new_speaker():
    text = "MUNE: Certo, é agora...[nl]\nMASA: Sim."

    assert translate.reflow(text) == text


def test_reflow_keeps_short_choice_lines_apart():
    text = "Veio buscar a Masamune?[nl]\nSim[nl]\nNão"

    assert translate.reflow(text) == text


def test_reflow_lets_an_orphan_last_line_flow_into_the_paragraph():
    text = "Aqui agradecemos a Fiona e[nl]\nRobos por replantar a floresta há 400[nl]\nanos!"

    assert translate.reflow(text) == "Aqui agradecemos a Fiona e Robos por replantar a floresta há 400 anos!"


def test_a_growth_below_one_asks_for_shorter_text():
    assert translate.budget_hint("A" * 100, growth=0.8) == 80
    assert translate.budget_hint("A" * 100) == 110


def test_keys_select_exactly_those_strings_even_when_already_translated(work):
    source, _ = script.read(work / "ct.en.txt")
    target, _ = script.read(work / "ct.txt")
    target.blocks[0].entries[0].text = "Já traduzido"

    items = translate.select(source, target, translate.Options(keys=["d1", "d3"]))

    assert [item.key for item in items] == ["d1", "d3"]


def _translated(work):
    text = ORIGINAL.replace("Are you leaving?", "Você vai embora?").replace("I shall return!", "Eu voltarei!")
    (work / "ct.txt").write_bytes(text.encode("iso-8859-15"))


def test_review_changes_only_the_lines_it_returns(work):
    _translated(work)
    client = FakeClient(lambda prompt: "1|CYRUS: Sim.¦Eu volto!")

    translate.run(work, options(work, blocks=["dialog"], review=True), client, out=lambda message: None)

    written, _ = script.read(work / "ct.txt")
    texts = [e.text for e in written.blocks[0].entries]
    assert texts[0] == "LEENE: Cyrus![nl]\n   Você vai embora?" and "Eu volto!" in texts[1]
    prompt = client.calls[0]["messages"][0]["content"]
    assert "EN: CYRUS: Yes.¦I shall return!" in prompt and "PT: CYRUS: Yes.¦Eu voltarei!" in prompt
    assert "reviewing an existing" in client.calls[0]["system"][0]["text"]


def test_review_only_looks_at_strings_that_are_already_translated(work):
    _translated(work)
    client = FakeClient(lambda prompt: "none")

    translate.run(work, options(work, blocks=["dialog"], review=True), client, out=lambda message: None)

    prompt = client.calls[0]["messages"][0]["content"]
    assert "EN: Come on, sleepy head!" not in prompt and "EN: LEENE: Cyrus!" in prompt


def test_review_answering_none_changes_nothing_and_costs_one_call(work):
    _translated(work)
    before = (work / "ct.txt").read_bytes()
    client = FakeClient(lambda prompt: "none")

    summary = translate.run(work, options(work, blocks=["dialog"], review=True), client, out=lambda message: None)

    assert (work / "ct.txt").read_bytes() == before and summary.calls == 1 and summary.failed == []


def test_a_review_suggestion_that_fails_the_checks_falls_back_to_the_current_portuguese(work):
    _translated(work)
    client = FakeClient(lambda prompt: "0|LEENE: Cyrus![code]")

    summary = translate.run(work, options(work, blocks=["dialog"], review=True), client, out=lambda message: None)

    written, _ = script.read(work / "ct.txt")
    assert written.blocks[0].entries[0].text == "LEENE: Cyrus![nl]\n   Você vai embora?"
    assert summary.failed == ["d1"]


def test_reflow_keeps_song_lines_apart():
    text = "Me chamam de Gato[musicsymbol][nl]\nTenho juntas de metal[musicsymbol][nl]\nMe derrote[musicsymbol]"

    assert translate.reflow(text) == text


def _block(label, width=11):
    return script.Block("*l%d;%s" % (width, label), "l", width, label, 1)


def test_split_name_separates_symbol_and_blank_tile_prefixes():
    items, mons = _block("items"), _block("mons")

    assert translate.split_name(items, "[bladesymbol]Wood_Sword") == ("[bladesymbol]", "Wood Sword")
    assert translate.split_name(items, "_Tonic     ") == ("_", "Tonic")
    assert translate.split_name(mons, "Red Beast  ") == ("", "Red Beast")


def test_name_limit_leaves_room_for_the_prefix():
    items = _block("items")

    assert translate.name_limit(items, "[bladesymbol]Wood_Sword") == 10
    assert translate.name_limit(_block("techs"), "Cyclone    ") == 11


def test_format_name_restores_prefix_underscores_and_padding():
    items, mons = _block("items"), _block("mons")

    assert translate.format_name(items, "[bladesymbol]Wood_Sword", "Espada Pau") == "[bladesymbol]Espada_Pau"
    assert translate.format_name(items, "_Tonic     ", "Tônico") == "_Tônico    "
    assert translate.format_name(mons, "Nu         ", "Nu") == "Nu         "
    assert translate.format_name(mons, "Red Beast  ", "Fera Rubra") == "Fera Rubra "


def test_format_name_drops_a_symbol_the_model_repeated():
    assert translate.format_name(_block("items"), "[bladesymbol]Wood_Sword", "[bladesymbol]Espada Pau") == "[bladesymbol]Espada_Pau"
