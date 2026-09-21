# cc-extrator

Tooling to extract all text from the Chrono Trigger (US, SNES) ROM, translate it to Brazilian Portuguese, and put it back into the ROM.

The existing pt-BR translation has errors, so this project aims to redo it carefully, with full context about the game.

## Goal

1. Extract every string from the ROM into an editable format.
2. Build a context notebook about the game so translations are consistent and accurate.
3. Translate the strings to pt-BR (an LLM agent does the first pass, using the notebook as context).
4. Reinsert the translated text into the ROM and generate a patch.

## ROM notes

- File: `data/ChronoTrigger.sfc`
- Size: 4 MiB, no copier header, so file offsets match ROM offsets.
- Internal header at `0xFFC0` reads `CHRONO TRIGGER`, map mode `0x31` (HiROM).
- Text uses a custom character table and compression, so a decoder is needed before anything is readable.

## Pipeline

### 1. Extract

Decode text blocks (dialogue, menus, items, techs, names) into JSON. Each entry keeps its ROM offset, the original text and its maximum length.

### 2. Context notebook

Files in `notebook/` that the translation agent reads. Start with `translation-guidelines.md` (hard technical rules, limits, style) and `glossary.tsv` (every name with its length limit). Planned:

- Plot summary by era
- Screenplay and scene context
- Characters, with voice and register for each one (done, see `notebook/characters/`)
- Glossary: tech names, places, items and recurring terms
- Style rules for the pt-BR translation

### 3. Translate

The agent receives the strings plus the notebook context and writes pt-BR into a separate field. The original English stays next to it for review.

### 4. Reinsert

Re-encode the pt-BR text and write it back to the ROM. Portuguese is longer than English, so this step needs:

- A length budget check per string
- Pointer table rewriting
- Moving text to free space when it does not fit in place

### 5. Release

Only patches (IPS) are shared. The ROM and any patched ROM are never committed.

## How it works

Extraction and reinsertion are done by [Chronotools](https://bisqwit.iki.fi/source/chronotools.html) (GPL, by Bisqwit), which already solves the text compression, pointer rewriting and free space management. It only builds on Linux with GNU libstdc++, so it runs inside a Docker container. `cc-extrator` is a thin wrapper around it.

Requirements: Docker (Colima works), Python 3.14 and uv.

## Usage

```
uv sync
uv run cc-extrator build-image   # once, builds the Chronotools image
uv run cc-extrator extract       # ROM to work/ct.txt (script) plus fonts, and an untouched copy in work/ct.en.txt
uv run cc-extrator accents       # once, adds the Portuguese accented letters to the fonts
# edit or translate work/ct.txt
uv run cc-extrator check         # validate work/ct.txt against work/ct.en.txt
uv run cc-extrator budget        # how much of the cartridge's text space the script uses
uv run cc-extrator insert        # runs check, then builds work/ctpatch.ips
uv run cc-extrator apply         # patch applied, writes out/ChronoTrigger-ptbr.sfc
```

Defaults: ROM at `data/ChronoTrigger.sfc`, working directory `work/`, output at `out/ChronoTrigger-ptbr.sfc`. Use `--rom`, `--work` and `--out` to change them.

`extract` never overwrites an existing `work/ct.txt`, `work/ct.en.txt` or `work/ct.cfg`, so translations and config edits are safe. Delete the file to regenerate it.

### The validator

`check` compares the translation with the English original and applies the rules from `notebook/translation-guidelines.md`. It exits with an error status when something would break the game, and `insert` refuses to run until it passes (`--skip-check` overrides).

It reports:

- structure: changed headers, missing, extra or reordered keys, edits to protected blocks (dictionary, charset, buttons, menu screens)
- control codes that were removed, added or reordered
- names that are too long for fixed-width fields (the tool would cut them silently), and lines wider than the original block allows
- dialogue pages that need more than 4 lines, and words too long to wrap
- characters the font cannot show, including accents until the glyphs exist (`--allow-accents` lifts that)
- the rename token `Robos`, and glossary terms that do not match `notebook/glossary.tsv`
- a file saved as UTF-8 instead of ISO-8859-15

Limits such as the widest line of each block are measured from the original script, so they follow the game. The dialogue page estimate is approximate, so `insert` also stops when the real `ctinsert` prints an error and removes any patch it wrote before failing.

### The space budget

`budget` runs `ctinsert` on a throwaway copy of the work directory (nothing is written to it) and reports the English script and your translation side by side: raw and packed size, the growth over English, the space used on each of the 12 text pages, and the tightest pages. It says `FITS` or `OVERFLOW` with the pages and how much text to cut, and exits with an error status on overflow. Run it while translating, not at the end. See the known limitations for why the space is so tight.

### Accented letters

`accents` draws á à â ã é ê í ó ô õ ú ç and their capitals into `work/ct16fn.tga` and `work/ct8fn.tga` and registers them in `work/ct.cfg`. The glyphs are composed from the letters already in the font, so no font data is stored in the repository. `check` reads `ct.cfg` and only accepts the accents the font really has.

### Known limitations

- The variable-width 8px font (VWF8) is disabled in the default config, because its renderer crashes with the current toolchain.
- `dump_events` is disabled in the default config. The sample config from Chronotools recompiles event `$017` (the game reset event). On the US ROM that recompiled event breaks the boot and the screen stays black. Do not enable it. This was found by bisecting the patch hunks and testing in Mesen2.
- Space is the main constraint. The 32 Mbit ROM absorbs only about 10 percent more script than the English one before `ctinsert` runs out of text space. A 48 Mbit ROM (`romsize = 48` and `*Z` headers) removes the limit on paper, but the resulting ExHiROM image showed corrupted graphics and text in the target emulator (RomM with EmulatorJS), so it is not used. Longer dictionary words barely help (0.6 percent).
- The dictionary is rebuilt for the script (`rebuild = true` in the default config). With the original dictionary reapplied, even the untouched English script overflows six text pages and `ctinsert` reports `ERROR:` lines.
- Only the unmodified English script and a short accent test have been tried in an emulator.

## Layout

```
src/cc_extrator/
  chronotools.py   docker wrapper (extract, insert, apply)
  cli.py           command line
  script.py        parser for ct.txt
  validator.py     checks a translation against the original
  fontwidths.py    pixel widths of the dialogue font
  docker/          Dockerfile that builds Chronotools
tests/             unit tests (docker calls are mocked)
data/              the ROM (gitignored)
work/              Chronotools working files (gitignored)
notebook/          translation guidelines, glossary and character notes
  sources/         reference material (script dump, chronology, PDFs)
out/               patched ROM (gitignored)
```

## Status

- [x] Project setup with uv
- [x] CLI and Docker wrapper for Chronotools
- [x] String extraction
- [x] Patch generation on the unmodified script
- [x] Verify the patched ROM in an emulator (boots in Mesen2 with the unmodified script)
- [ ] Context notebook
- [ ] Translation pass
- [x] Portuguese font glyphs (accents), pending a check in the emulator
- [ ] Reinsertion of the translated script

## Legal

This project does not include or distribute the ROM. You need your own legally obtained copy.
