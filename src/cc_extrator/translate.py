"""Translates the script with the Claude API under a hard spend cap.

Strings are sent in small batches in a compact form (numeric ids, one symbol for
line breaks and pauses) because the raw keys and control codes cost about a fifth
more tokens. Every answer is decoded, written into ct.txt and run through the
validator. Strings that fail get one repair round, the rest stay in English.

Money is guarded three ways: every call is recorded in a ledger file, a call is
refused when the ledger total plus its worst case would pass the cap, and nothing
paid runs without an explicit confirmation.
"""

import csv
import json
import re
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cc_extrator import script, validator
from cc_extrator.fontwidths import text_width

NEWLINE = "¶"
PAUSE = "¦"

# USD per million tokens (input, output), from Anthropic's price list cached on 2026-06-24.
PRICES = {"claude-sonnet-5": (2.0, 10.0), "claude-opus-5": (5.0, 25.0), "claude-haiku-4-5": (1.0, 5.0)}
CACHE_WRITE = 1.25
CACHE_READ = 0.10
EFFORT_MODELS = {"claude-sonnet-5", "claude-opus-5"}

MANUAL_BLOCKS = {"tres msg"}
NAME_BLOCKS = {"items", "techs", "mons"}
CENTERED_BLOCKS = {"eps", "eraes"}
DEFAULT_TOTAL_CAP = 9.50
CHARS_PER_TOKEN = 2.0
GROWTH_TARGET = 1.10
MAX_TOKENS = 16000

_NEWLINE_CODE = re.compile(r"\[nl\]([ \n]*)")
_PAUSE_CODE = re.compile(r"\[pause\]([ \n]*)")
_SPEAKER = re.compile(r"^\s*(?:\[[^\]]*\])*([A-Za-z][A-Za-z0-9 .'&-]{0,24}):")
_ANSWER_LINE = re.compile(r"^\s*(?:id\s*)?(\d+)\s*\|\s?(.*)$", re.IGNORECASE)
_ECHOED_HINT = re.compile(r"\s*<=\s*\d+\s*$")
_SYMBOL_PREFIX = re.compile(r"^(\[[a-z]+symbol\])")
_TYPOGRAPHIC = {"’": "'", "‘": "'", "“": "«", "”": "»", "…": "...", "—": "-", "–": "-", " ": " "}


class SpendLimit(RuntimeError):
    pass


@dataclass
class Item:
    id: int
    key: str
    block: script.Block
    text: str
    current: str = ""


@dataclass
class Batch:
    block: script.Block
    items: list[Item]
    context: list[str]


@dataclass
class Encoded:
    compact: str
    newline_tails: list[str] = field(default_factory=list)
    pause_tails: list[str] = field(default_factory=list)


@dataclass
class Options:
    model: str = "claude-sonnet-5"
    effort: str = "medium"
    blocks: list[str] = field(default_factory=list)
    limit: int | None = None
    batch_size: int = 40
    max_cost: float = 1.0
    total_cap: float = DEFAULT_TOTAL_CAP
    confirmed: bool = False
    redo: bool = False
    redo_invalid: bool = False
    thinking: bool = True
    growth: float = GROWTH_TARGET
    keys: list[str] = field(default_factory=list)
    review: bool = False
    notebook: Path = Path("notebook")
    ledger: Path = Path("work/spend-ledger.json")


@dataclass
class Summary:
    translated: int = 0
    failed: list[str] = field(default_factory=list)
    calls: int = 0
    cost: float = 0.0
    stopped: str = ""


# ---------------------------------------------------------------- compact form

def encode(text: str) -> Encoded:
    result = Encoded("")

    def keep(tails: list[str], symbol: str):
        def replace(match: re.Match) -> str:
            tails.append(match.group(1))
            return symbol
        return replace

    compact = _NEWLINE_CODE.sub(keep(result.newline_tails, NEWLINE), text)
    compact = _PAUSE_CODE.sub(keep(result.pause_tails, PAUSE), compact)
    result.compact = re.sub(r"\n+", " ", compact)
    return result


def decode(compact: str, source: Encoded, source_text: str) -> str:
    """Turn the compact answer back into script text, reusing the layout whitespace of the original."""
    default_newline = "\n   " if _SPEAKER.match(source_text) else "\n"

    def restore(tails: list[str], symbol: str, code: str, default: str) -> Callable[[str], str]:
        def run(text: str) -> str:
            parts = text.split(symbol)
            out = [parts[0]]
            for index, part in enumerate(parts[1:]):
                tail = tails[index] if index < len(tails) else (tails[-1] if tails else default)
                out.append(code + tail + part)
            return "".join(out)
        return run

    text = restore(source.newline_tails, NEWLINE, "[nl]", default_newline)(compact)
    return restore(source.pause_tails, PAUSE, "[pause]", "\n")(text)


_BREAK = re.compile(r"\[nl\][ \n]*")
_SENTENCE_END = ".!?:\u00bb"


def reflow(text: str) -> str:
    """Drop the line breaks that split a sentence and let the game's wrapper flow the paragraph.

    Kept: breaks after a sentence end or a code such as a music note (song lines), before a new speaker,
    after a very short line (a choice such as Sim or Nao). The wrapper knows the true widths, including the worst case of a name
    the player can rename, so it breaks lines better than a translation copying English breaks.
    """
    lines = _BREAK.split(text)
    seps = _BREAK.findall(text)
    out = lines[0]
    for line, sep, before in zip(lines[1:], seps, lines[:-1]):
        tail = before.rstrip()
        keep = (
            not tail
            or tail[-1] in _SENTENCE_END
            or tail.endswith("]")
            or bool(_SPEAKER.match(line))
            or len(before.split()) <= 2
        )
        out += (sep if keep else " ") + line
    return out


_LAYOUT_CODE = re.compile(r"\[(pause|cls)\]([ \n]*)")


def relayout(source_text: str, text: str) -> str:
    """Give every [pause] and [cls] the whitespace that followed the same code in the English.

    The tool ignores a newline after these codes but keeps the spaces, so a stray space would shift a page.
    """
    tails: dict[str, list[str]] = {"pause": [], "cls": []}
    for match in _LAYOUT_CODE.finditer(source_text):
        tails[match.group(1)].append(match.group(2))
    seen = {"pause": 0, "cls": 0}

    def restore(match: re.Match) -> str:
        name = match.group(1)
        index = seen[name]
        seen[name] += 1
        wanted = tails[name]
        tail = wanted[index] if index < len(wanted) else (wanted[-1] if wanted else match.group(2))
        return f"[{name}]{tail}"

    return _LAYOUT_CODE.sub(restore, text)


def normalize(text: str) -> str:
    """Replace typographic characters the font and the script encoding cannot take."""
    for bad, good in _TYPOGRAPHIC.items():
        text = text.replace(bad, good)
    return text


def parse_answer(text: str) -> dict[int, str]:
    answers: dict[int, str] = {}
    for line in text.splitlines():
        match = _ANSWER_LINE.match(line)
        if match:
            answers[int(match.group(1))] = _ECHOED_HINT.sub("", match.group(2)).rstrip()
    return answers


# ------------------------------------------------------------------------ names

def split_name(block: script.Block, text: str) -> tuple[str, str]:
    """Split a fixed width name into its prefix (a symbol code, or the blank tile of an item) and the plain name."""
    match = _SYMBOL_PREFIX.match(text)
    prefix = match.group(1) if match else ""
    if not prefix and block.label == "items" and text.startswith("_"):
        prefix = "_"
    body = text[len(prefix):].rstrip(" ")
    if block.label != "mons":
        body = body.replace("_", " ")
    return prefix, body.strip()


def name_limit(block: script.Block, text: str) -> int:
    prefix, _ = split_name(block, text)
    return (block.width or 11) - (1 if prefix else 0)


def format_name(block: script.Block, source_text: str, answer: str) -> str:
    """Put a translated name back in the layout of the field: prefix, words joined by the blank tile, padding."""
    prefix, _ = split_name(block, source_text)
    body = re.sub(r"\[[a-z]+symbol\]", "", answer).strip().lstrip("_")
    if block.label != "mons":
        body = body.replace(" ", "_")
    text = prefix + body
    return text + " " * max(0, (block.width or 11) - validator.visible_length(text))


# ------------------------------------------------------------------- selection

def select(source: script.Script, target: script.Script, options: Options, invalid: set[str] | None = None) -> list[Item]:
    items: list[Item] = []
    counter = 0
    for original, current in zip(source.blocks, target.blocks):
        is_name = original.kind == "l" and original.label in NAME_BLOCKS and not options.review
        if not (original.kind in "zZ" or is_name) or original.label in MANUAL_BLOCKS or original.label == "screens":
            continue
        if options.blocks and original.label not in options.blocks:
            continue
        for entry, now in zip(original.entries, current.entries):
            if not re.search(r"[A-Za-z]", re.sub(r"\[[^\]]*\]", "", entry.text)):
                continue
            if is_name and not split_name(original, entry.text)[1]:
                continue
            forced = entry.key in options.keys
            if options.review:
                if now.text == entry.text or (options.keys and not forced):
                    continue
            else:
                if now.text != entry.text and not options.redo and not forced and entry.key not in (invalid or set()):
                    continue
                if options.keys and not forced:
                    continue
            items.append(Item(counter, entry.key, original, entry.text, now.text))
            counter += 1
    return items[:options.limit] if options.limit else items


def make_batches(items: list[Item], size: int, context_lines: int = 3) -> list[Batch]:
    batches: list[Batch] = []
    by_block: dict[int, list[Item]] = {}
    for item in items:
        by_block.setdefault(id(item.block), []).append(item)
    for group in by_block.values():
        block = group[0].block
        everything = [entry.text for entry in block.entries]
        for start in range(0, len(group), len(group) if block.label in NAME_BLOCKS else size):
            chunk = group[start:start + (len(group) if block.label in NAME_BLOCKS else size)]
            first = next(i for i, entry in enumerate(block.entries) if entry.key == chunk[0].key)
            before = [encode(text).compact for text in everything[max(0, first - context_lines):first] if text.strip()]
            batches.append(Batch(block, chunk, before))
    return batches


# --------------------------------------------------------------------- prompts

TASK = """You are translating the text of the SNES game Chrono Trigger (US version) from English to Brazilian Portuguese, following the guidelines above exactly.

Input format: one string per line as `id|text`. In the text, `¶` marks a line break and `¦` marks a pause. Keep every `¶` and `¦` marker, in the same number and order as the English, except that in ordinary dialogue you may add or remove `¶` line breaks to make the lines fit. Never write [nl] or [pause]. Keep every other [code] exactly as it is.

After the strings, a line starting with `Length limits` gives the most characters to use for each id. Never copy it into your answer. The whole translation must stay within about 10 percent of the English length, so condense hard: cut filler, prefer short words. A shorter string is always better than a longer one.

Use real Portuguese accents (á à â ã é ê í ó ô õ ú ç and capitals). Type only plain ASCII punctuation, three dots for an ellipsis, and the « » marks only where the English uses them.

Party names stay exactly as they are and are never translated: Crono, Marle, Lucca, Frog, Robos, Ayla, Magus (Frog is never Sapo, Robos is never Robo).

Glossary terms: a mark such as (m) or (f) after a translation is only its grammatical gender, use it to agree articles and adjectives and never write it.

Register: Frog, Cyrus, Glenn, Slash, Ozzie and the other knights and Mystics speak with `você` plus a few archaic touches (deveras, outrora, mui, ó). Never use vós forms (passai, vossa) except the title Vossa Majestade.

Sound effects: adapt short ones to Portuguese (Whoosh becomes Fiuu, Grribit becomes Crroac) and keep cries that have no Portuguese form, such as GRAAAACK.

Answer with one line per input string, `id|translation`, and nothing else."""


REVIEW_TASK = """You are reviewing an existing Brazilian Portuguese translation of the SNES game Chrono Trigger, following the guidelines above exactly.

Each string is shown as the English (EN) and the current Portuguese (PT), in the same compact form as a translation: `¶` marks a line break and `¦` a pause, and every other [code] is kept.

Decide for each string whether the Portuguese should change. Change it when it has one of these problems:
- a mistranslation, or a dropped noun or meaning (for example `Estamos tendo demais.` lost the word earthquake, it should be `Tem terremoto demais acontecendo.`);
- stiff, literal or overly formal phrasing that a Brazilian would not say in that character's mouth, such as formal imperatives in casual family or village speech (`Levante-se!` should be `Levanta!`), English word order, or a calque;
- lost humor, irony or attitude of the speaker;
- a broken choice label: an option the player selects must read like an action, not like a question (`Deseja se registrar?` should be `Hospedar-se.`).

Keep the character's voice from the notes. If the Portuguese is natural and correct, do not return it, and do not rewrite lines that are merely different from what you would write.

Return only the strings you change, one line each as `id|improved Portuguese`, with the same rules as a translation: same codes, glossary terms, party names, length limits and accents. If you change nothing, answer `none`. Never copy the Length limits line."""


NAME_TASK = """You are translating the names of items, techniques and monsters of the SNES game Chrono Trigger from English to Brazilian Portuguese, following the guidelines above.

Names are shown one per line as `id|English name`, with words separated by spaces. They are shown in a fixed 8 by 8 pixel font in fields with a hard length limit, given for every id on the last line (spaces count). A name over its limit is rejected, so shorten it, but never by cutting a word in the middle: `EspMadeira`, `LâminFerro`, `Aguieta Our` and `Filho do So` are wrong. Shorten by dropping articles and prepositions (de, do, da), by choosing a shorter whole word (Espada, Lâmina, Gume, Malha, Traje, Colete, Elmo, Arco, Braço, Mão), or by inventing a short natural name with the same feel (`Wood Sword` can be `Espada Pau`, `Flame Kick` can be `Chute Fogo`). An abbreviation with a period is a last resort. Keep the meaning and the flavor of the name; the player must be able to read it as Portuguese.

Keep the whole list consistent: the same English word must become the same Portuguese word in every name it appears in (all the Tonics, all the Ethers, every Sword), and the glossary above wins. Party names stay as they are (Frog is never Sapo, Robo stays Robo in Robo Tackle). Do not add symbols or underscores, write spaces between words. Use real Portuguese accents where the word needs them.

Answer with one line per input name, `id|translation`, and nothing else."""


def build_system(guidelines: str, glossary: Path | None, review: bool = False, names: bool = False) -> str:
    parts = [guidelines.strip(), "", NAME_TASK if names else (REVIEW_TASK if review else TASK)]
    if glossary is not None and glossary.is_file():
        rows = []
        with glossary.open(encoding="utf-8", newline="") as file:
            for row in csv.DictReader(file, delimiter="\t"):
                if (row.get("ptbr") or "").strip():
                    rows.append(f"{row['kind']}: {row['english'].strip()} = {row['ptbr'].strip()}")
        if rows:
            parts += ["", "Glossary, always use these exact translations:", *rows]
    return "\n".join(parts)


class CharacterNotes:
    """The voice notes of the characters, looked up by the speaker labels used in the script."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.files: dict[str, str] = {}
        index = directory / "README.md"
        if index.is_file():
            for row in index.read_text(encoding="utf-8").splitlines():
                cells = [cell.strip() for cell in row.strip("|").split("|")]
                if len(cells) == 3 and cells[2].startswith("`") and cells[2].endswith(".md`"):
                    for label in re.findall(r"`([^`]+)`", cells[1]):
                        self.files[label.upper()] = cells[2].strip("`")

    def for_labels(self, labels: list[str]) -> str:
        chosen: list[str] = []
        for label in labels:
            name = self.files.get(label.upper())
            if name and name not in chosen:
                chosen.append(name)
        return "\n\n".join(self._voice(name) for name in chosen)

    def _voice(self, name: str) -> str:
        text = (self.directory / name).read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ")
        sections = re.findall(r"## (Voice in the English script|Proposed pt-BR voice)\n(.*?)(?=\n## |\Z)", text, flags=re.S)
        body = "\n".join(f"{heading}:\n{content.strip()}" for heading, content in sections)
        return f"{title}\n{body}"


AVERAGE_GLYPH_PX = 6.0


def budget_hint(text: str, ceiling_px: int | None = None, growth: float = GROWTH_TARGET) -> int:
    """Most characters a translation should use: 10 percent over the English, and inside the block's pixel ceiling."""
    length = len(encode(text).compact)
    hint = max(6, int(length * growth)) if growth < 1 else max(length + 3, int(length * growth))
    if ceiling_px is not None:
        hint = min(hint, int(ceiling_px / AVERAGE_GLYPH_PX))
    return hint


def build_names_user(batch: Batch) -> str:
    lines = [f"Block: {batch.block.label}", "Names to translate, the whole list so you can keep it consistent:", ""]
    lines += [f"{item.id}|{split_name(batch.block, item.text)[1]}" for item in batch.items]
    limits = ", ".join(f"{item.id}={name_limit(batch.block, item.text)}" for item in batch.items)
    lines += ["", f"Length limits (most characters per id, spaces count): {limits}"]
    return "\n".join(lines)


def build_review_user(batch: Batch, notes: CharacterNotes, growth: float = GROWTH_TARGET) -> str:
    header = build_user(Batch(batch.block, [], batch.context), notes, growth).split("Translate:")[0]
    rows = []
    for item in batch.items:
        rows += [str(item.id), f"EN: {encode(item.text).compact}", f"PT: {encode(item.current).compact}"]
    limits = ", ".join(f"{item.id}={budget_hint(item.text, None, growth)}" for item in batch.items)
    return header + "Review:\n" + "\n".join(rows) + f"\n\nLength limits (most characters per id): {limits}"


def build_user(batch: Batch, notes: CharacterNotes, growth: float = GROWTH_TARGET) -> str:
    labels = [match.group(1) for item in batch.items if (match := _SPEAKER.match(item.text))]
    lines = [f"Block: {batch.block.label}"]
    ceiling = None
    if not batch.block.is_dialog:
        ceiling, max_lines = validator.block_limits(batch.block)
        lines.append(f"Hard limit for this block: each line at most {ceiling} pixels wide (about {int(ceiling / AVERAGE_GLYPH_PX)} characters), at most {max_lines} line(s). Longer text is rejected.")
    if batch.block.comments:
        lines.append("Scene: " + "; ".join(batch.block.comments))
    voices = notes.for_labels(labels) if labels else ""
    if voices:
        lines += ["", "Voices of the speakers in this batch:", voices]
    if batch.context:
        lines += ["", "Previous lines for context, do not translate:", *batch.context]
    lines += ["", "Translate:"]
    lines += [f"{item.id}|{encode(item.text).compact}" for item in batch.items]
    limits = ", ".join(f"{item.id}={budget_hint(item.text, ceiling, growth)}" for item in batch.items)
    lines += ["", f"Length limits (most characters per id): {limits}"]
    return "\n".join(lines)


def build_repair(problems: list[tuple[Item, str, list[str]]]) -> str:
    lines = ["These translations failed the automatic checks. Rewrite only these strings, fixing every problem, and answer with one line per string as `id|translation`, for example `12|Olá`.", ""]
    for item, translation, errors in problems:
        lines += [f"Number {item.id}", f"English: {encode(item.text).compact}", f"Your version: {translation}", "Problems: " + "; ".join(errors), ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------- money

def cost_of(model: str, usage: Any) -> float:
    price_in, price_out = PRICES[model]
    fresh = getattr(usage, "input_tokens", 0) or 0
    written = getattr(usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(usage, "cache_read_input_tokens", 0) or 0
    output = getattr(usage, "output_tokens", 0) or 0
    return (fresh * price_in + written * price_in * CACHE_WRITE + read * price_in * CACHE_READ + output * price_out) / 1_000_000


def worst_case(model: str, prompt_chars: int) -> float:
    price_in, price_out = PRICES[model]
    return (prompt_chars / CHARS_PER_TOKEN * price_in + MAX_TOKENS * price_out) / 1_000_000


class Ledger:
    """Every paid call, kept on disk so the cap holds across runs."""

    def __init__(self, path: Path):
        self.path = path
        self.calls: list[dict] = json.loads(path.read_text()) if path.is_file() else []

    @property
    def total(self) -> float:
        return sum(call["cost"] for call in self.calls)

    def add(self, model: str, usage: Any, cost: float, note: str, strings_tokens: float = 0) -> None:
        self.calls.append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"), "model": model, "note": note, "cost": round(cost, 6),
            "strings_tokens": round(strings_tokens),
            "input": getattr(usage, "input_tokens", 0), "cache_write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0, "output": getattr(usage, "output_tokens", 0),
        })
        self.path.write_text(json.dumps(self.calls, indent=1))

    def output_per_string_token(self, model: str) -> float | None:
        """Measured output tokens per token of string text, from earlier calls of the same model."""
        rows = [call for call in self.calls if call.get("strings_tokens") and call["model"] == model]
        return statistics.median(call["output"] / call["strings_tokens"] for call in rows) if rows else None


def strings_tokens(items: list[Item]) -> float:
    """Estimated tokens of just the strings to translate, the part the output scales with."""
    return sum(len(encode(item.text).compact) + len(str(item.id)) + 8 for item in items) / CHARS_PER_TOKEN


# ---------------------------------------------------------------- the pipeline

def dry_run_report(batches: list[Batch], system: str, options: Options, ledger: Ledger, notes: CharacterNotes) -> str:
    user_tokens = sum(len(build_user(batch, notes)) for batch in batches) / CHARS_PER_TOKEN
    text_tokens = sum(strings_tokens(batch.items) for batch in batches)
    strings = sum(len(batch.items) for batch in batches)
    price_in, price_out = PRICES[options.model]
    prefix_tokens = len(system) / CHARS_PER_TOKEN
    fixed = (user_tokens * price_in + len(batches) * prefix_tokens * price_in * CACHE_READ) / 1e6
    measured = ledger.output_per_string_token(options.model)
    low_out, high_out = (measured * 0.8, measured * 1.2) if measured else (1.5, 4.0)
    low = fixed + text_tokens * low_out * price_out / 1e6
    high = fixed + text_tokens * high_out * price_out / 1e6
    basis = "measured from earlier calls" if measured else "assumed, no calls measured yet"
    return "\n".join([
        f"{strings} strings in {len(batches)} batches, model {options.model}, effort {options.effort}",
        f"prompt prefix about {prefix_tokens:,.0f} tokens (cached after the first call), all batch prompts {user_tokens:,.0f} tokens, of which strings {text_tokens:,.0f}",
        f"projected cost ${low:.2f} to ${high:.2f} (output per string token {low_out:.1f} to {high_out:.1f}, {basis})",
        f"ledger so far ${ledger.total:.2f}, total cap ${options.total_cap:.2f}, this run cap ${options.max_cost:.2f}",
    ])


def _request(client: Any, options: Options, system: str, user: str) -> Any:
    kwargs: dict[str, Any] = {
        "model": options.model, "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
    }
    if options.model in EFFORT_MODELS:
        kwargs["output_config"] = {"effort": options.effort}
        if not options.thinking:
            kwargs["thinking"] = {"type": "disabled"}
    return client.messages.create(**kwargs)


def _log(work_dir: Path, note: str, response: Any) -> None:
    """Keep the raw answer of every call so a bad batch can be diagnosed without paying again."""
    record = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "note": note, "stop_reason": getattr(response, "stop_reason", ""), "answer": _answer_text(response)}
    with (work_dir / "translation-log.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _answer_text(response: Any) -> str:
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


def _centre(block: script.Block) -> float:
    def middle(text: str) -> float:
        return (len(text) - len(text.lstrip(" "))) * 4 + text_width(text.strip()) / 2
    return statistics.median(middle(entry.text) for entry in block.entries if entry.text.strip())


def recentre(block: script.Block, text: str) -> str:
    stripped = text.strip()
    return " " * max(0, round((_centre(block) - text_width(stripped) / 2) / 4)) + stripped


def write_translations(path: Path, texts: dict[str, str]) -> None:
    """Replace the text of the given keys in ct.txt, keeping the file's encoding."""
    raw = path.read_bytes().decode(script.ENCODING)
    for key, text in texts.items():
        pattern = re.compile(r"(?ms)^(\$" + re.escape(key) + r":).*?(?=^\$|^\*)")
        if not pattern.search(raw):
            raise KeyError(key)
        raw = pattern.sub(lambda match: match.group(1) + text + "\n", raw, count=1)
    path.write_bytes(raw.encode(script.ENCODING))


def _invalid_keys(work_dir: Path, source: script.Script, target: script.Script) -> set[str]:
    """Keys of translated strings that currently fail the validator."""
    report = validator.check(source, target, validator.Options(config=work_dir / "ct.cfg"))
    return {issue.key for issue in report.errors if issue.key}


def run(work_dir: Path, options: Options, client: Any = None, guidelines: Path | None = None, out: Callable[[str], None] = print) -> Summary:
    source, _ = script.read(work_dir / "ct.en.txt")
    target_path = work_dir / "ct.txt"
    target, _ = script.read(target_path)
    invalid = _invalid_keys(work_dir, source, target) if options.redo_invalid else set()
    items = select(source, target, options, invalid)
    batches = make_batches(items, options.batch_size)
    notes = CharacterNotes(options.notebook / "characters")
    glossary = options.notebook / "glossary.tsv"
    only_names = bool(items) and all(item.block.label in NAME_BLOCKS for item in items)
    system = build_system((guidelines or options.notebook / "translation-guidelines.md").read_text(encoding="utf-8"), glossary, options.review, only_names)
    ledger = Ledger(options.ledger)
    summary = Summary()
    out(dry_run_report(batches, system, options, ledger, notes))
    if not options.confirmed:
        out("Nothing was sent. Add --yes to run it.")
        return summary

    check_options = validator.Options(config=work_dir / "ct.cfg", glossary=glossary if glossary.is_file() else None)
    by_key = {item.key: item for item in items}
    for number, batch in enumerate(batches, 1):
        user = build_names_user(batch) if batch.block.label in NAME_BLOCKS else (build_review_user if options.review else build_user)(batch, notes, options.growth)
        if ledger.total + worst_case(options.model, len(system) + len(user)) > options.total_cap:
            summary.stopped = f"the total cap of ${options.total_cap:.2f} would be passed"
            break
        if summary.cost >= options.max_cost:
            summary.stopped = f"this run reached its cap of ${options.max_cost:.2f}"
            break
        response = _request(client, options, system, user)
        cost = cost_of(options.model, response.usage)
        ledger.add(options.model, response.usage, cost, f"{batch.block.label} batch {number}", strings_tokens(batch.items))
        summary.calls += 1
        summary.cost += cost
        _log(work_dir, f"{batch.block.label} batch {number}", response)
        if getattr(response, "stop_reason", "") == "max_tokens":
            summary.failed += [item.key for item in batch.items]
            out(f"batch {number}: the answer was cut off, smaller batches are needed")
            continue
        answers = parse_answer(_answer_text(response))
        problems = _apply(batch, answers, work_dir, target_path, source, check_options, options.review)
        if problems:
            repair = build_repair([(by_key[key], text, errors) for key, text, errors in problems])
            if ledger.total + worst_case(options.model, len(system) + len(repair)) <= options.total_cap:
                response = _request(client, options, system, repair)
                cost = cost_of(options.model, response.usage)
                ledger.add(options.model, response.usage, cost, f"{batch.block.label} batch {number} repair", strings_tokens([by_key[key] for key, _, _ in problems]))
                summary.calls += 1
                summary.cost += cost
                _log(work_dir, f"{batch.block.label} batch {number} repair", response)
                retried = Batch(batch.block, [by_key[key] for key, _, _ in problems], [])
                problems = _apply(retried, parse_answer(_answer_text(response)), work_dir, target_path, source, check_options, options.review)
            summary.failed += [key for key, _, _ in problems]
            for key, _, errors in problems[:2]:
                out(f"  still failing {key}: {errors[0][:100]}")
        summary.translated += len(batch.items) - len([1 for key, _, _ in problems])
        out(f"batch {number}/{len(batches)} {batch.block.label}: ${cost:.3f}, run total ${summary.cost:.2f}, ledger ${ledger.total:.2f}")
    return summary


def _apply(batch: Batch, answers: dict[int, str], work_dir: Path, target_path: Path, source: script.Script,
           check_options: validator.Options, review: bool = False) -> list[tuple[str, str, list[str]]]:
    """Write the answers into ct.txt, check them, and put back the English of any that fail."""
    texts: dict[str, str] = {}
    for item in batch.items:
        answer = answers.get(item.id)
        if answer is None:
            continue
        if item.block.label in NAME_BLOCKS:
            texts[item.key] = format_name(item.block, item.text, normalize(answer))
            continue
        encoded = encode(item.text)
        text = relayout(item.text, normalize(decode(answer, encoded, item.text)))
        if item.block.is_dialog:
            text = reflow(text)
        if item.block.label in CENTERED_BLOCKS:
            text = recentre(item.block, text)
        texts[item.key] = text
    try:
        write_translations(target_path, texts)
    except UnicodeEncodeError:
        return [(item.key, answers.get(item.id, ""), ["contains a character the script encoding cannot hold"]) for item in batch.items]
    target, _ = script.read(target_path)
    report = validator.check(source, target, check_options)
    errors: dict[str, list[str]] = {}
    for issue in report.errors:
        errors.setdefault(issue.key, []).append(f"{issue.code}: {issue.message}")
    problems: list[tuple[str, str, list[str]]] = []
    revert: dict[str, str] = {}
    for item in batch.items:
        if item.key not in texts:
            if not review:
                problems.append((item.key, "", ["no answer was returned for this id"]))
        elif item.key in errors:
            problems.append((item.key, encode(texts[item.key]).compact, errors[item.key]))
            revert[item.key] = item.current if review else item.text
    if revert:
        write_translations(target_path, revert)
    return problems
