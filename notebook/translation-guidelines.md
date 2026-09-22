# Translation guidelines: Chrono Trigger (US SNES) to pt-BR

These rules are for the translator agent and for whoever reviews its output. They exist because a
single wrong character in the wrong place can corrupt the ROM, and because Portuguese is longer than
English while the game has hard size limits.

How each rule is backed:

- (M) measured on this ROM and this toolchain
- (D) taken from the Chronotools documentation or source code
- (P) a proposal, needs your confirmation before the agent relies on it

Sections 1 to 5 are technical. Breaking them breaks the build or the game. Sections 6 to 9 are style.
When they conflict, the technical rules win.

## 1. The file and what you may edit

The file being translated is `work/ct.txt` (encoding ISO-8859-15, do not save it as UTF-8).
`extract` also saves an untouched copy as `work/ct.en.txt`, the validator compares against it and
it must never be edited.

Structure:

```
*z;dialog (change this to *Z to allow free relocation)   <- block header
;600ad (castle, masa+mune, naga-ette)                     <- comment, context only
$6p1c:                                                    <- string key
LEENE: Cyrus![nl]                                         <- the text you translate
   Are you leaving?
```

Hard rules:

1. Change only the text after a `$key:`. Never change, add, remove or reorder keys, block headers
   (`*...`) or comment lines (`;...`). (D)
2. One source string gives exactly one translated string under the same key. Empty strings stay empty
   (many item descriptions are empty on purpose). (M)
3. Strings may be reordered inside a block but never moved to another block. Do not do it anyway. (D)
4. A raw newline in the middle of a sentence becomes a space. A newline directly after `[nl]`,
   `[pause]` or `[cls]` is ignored. So never put a raw newline inside a sentence, and keep the
   newline plus indent that follows a code exactly as in the source. (M)
5. Trailing and leading spaces can be meaningful (see section 4.6). Preserve the pattern, do not trim.

## 2. Blocks: what to translate and what to leave alone

The count is the number of strings. "px" is the widest line found in the original text of that block,
computed from the game's own font width table. Use it as a ceiling (rule 4.3).

| Block | Count | Font | Limit | Action |
|---|---|---|---|---|
| `*d dictionary` | 127 | | | NEVER touch. It is the compression dictionary. |
| `*l80 cset` | 1 | | | NEVER touch. It is the character set string, it ends with a space that must stay. |
| `*l1 buttons` | 7 | | | NEVER touch (A, X, L, R, B, Y, S). |
| `*s.. free space` | 12 blocks | | | NEVER touch. Not text. |
| `*l11 items` | 242 | 8px | 11 visible chars | Translate. See 4.4. |
| `*z item descs` | 242 | 12px | single line, 211 px | Translate. Many are empty, keep them empty. |
| `*r item types` | 242 | 8px | 10 chars | Translate. Only 5 distinct values (ACCESSORY, ARMOR, HELMET, ITEM, WEAPON) repeat across all items. Use one translation for each. |
| `*l10 item classes` | 4 | 8px | 10 chars | Translate. Uses `_` as padding, e.g. `__Weapon__`. |
| `*l11 techs` | 117 | 8px | 11 visible chars | Translate. See 4.4. |
| `*z tech descs` | 117 | 12px | single line, 199 px | Translate. |
| `*z bat misc` | 4 | 12px | single line, 89 px | Translate (Can't run away, Single Tech, Dual Tech, Triple Tech). |
| `*z tres msg` | 3 | 12px | 2 lines, 139 px | Translate. Keep the leading `[nl]` and the centering spaces. |
| `*l16 bat` | 2 | 8px | 16 chars | Translate (Double Technique, Triple Technique). |
| `*l7 bat` | 12 | 8px | 7 chars | Translate. Each menu label is 2 strings (blank line plus label). `_` is a blank. |
| `*l11 mons` | 252 | 8px | 11 chars | Translate. Names are padded with spaces. |
| `*z places` | 112 | 12px | 14 chars, 87 px | Translate. |
| `*z eraes` | 8 | 12px | 12 chars, 77 px | Translate. Centered with leading spaces. |
| `*z eps` | 27 | 12px | 22 chars, 120 px | Translate. Centered with leading spaces. |
| `*z bat` | 241 | 12px | single line, 233 px | Translate. Contains value codes like `[num32]`. |
| `*z prompts` | 7 | 12px | 2 lines, 172 px | Translate. The box is narrower than dialogue, see 4.3. |
| `*z cfg` | 50 | 12px | single line, 136 px | Translate. |
| `*z dialog` | 4485 in 26 blocks | 12px | 4 lines per page, 235 px per line | Translate. This is the bulk of the game. |
| `*r screens` | 62 | 8px | fixed layout | DEFER. Menu and status screens built from `[goto]`, `[func1]`, `[stat]` and column codes. Translate later, by hand, one screen at a time. |

The block comments carry useful context: the dialogue blocks are tagged by era and location (for
example `2300ad (factory, sewer, belthasar)`, `end of time (gaspar's stories, Spekkio etc)`,
`1999ad Lavos scenes`). Pass that tag to the agent with every batch.

## 3. Control codes

Codes are written in square brackets. Rule for every code: copy it verbatim, keep the same count,
keep the same order, and keep it at the equivalent position in the sentence. Never translate,
retype or "fix" anything inside brackets. (D, M)

Counts are from the whole English script.

| Code | Count | Meaning | Rule |
|---|---|---|---|
| `[nl]` | 5142 | Line break. Followed by 3 spaces it is stored as one byte, that indent is intentional. | Keep the 3 spaces after it when the source has them. See 4.5 for when to add or remove. |
| `[pause]` | 838 | Wait for a button press, then continue. | Keep exactly, and keep whatever follows it in the source. That is a newline plus 3 spaces 467 times and a plain newline 371 times. Copy the same pattern. |
| `[cls]` | 18 | Clear the text box. | Keep. Text after it starts a new page. |
| `[next]` | 133 | Jump to the next column (menu screens only). | Only in `*r screens`. |
| `[delay NN]` | about 160 | Pause inside a line, in ticks, for dramatic timing. | Keep the code and keep it right after the same punctuation mark it follows in the source. Do not change the number. |
| `[crononick]` | 94 | Ayla's nickname for Crono, filled in by the game. | Keep. It replaces a name, so build the sentence around it like a name. |
| `[item]`, `[tech]`, `[monster]` | 88, 3, 2 | The game inserts an item, technique or monster name here. | Keep. Do not add an article or an adjective that must agree with it (see 8.4). |
| `[member1]`, `[member2]`, `[member3]`, `[member]`, `[member,XXXX]` | 30, 4, 4, 3, 13 | Inserts a party member name. | Keep. Do not add gender-marked words about that person (see 8.4). |
| `[num8]`, `[num16]`, `[num32]` | 13, 7, 3 | Inserts a number (gold, XP, counts). | Keep. Write the surrounding words so both singular and plural read correctly, for example `ponto(s)`. |
| `[musicsymbol]`, `[heartsymbol]` | 49, 8 | Music note, heart glyphs. | Keep at the same place, they are single glyphs. |
| `[bladesymbol]`, `[bowsymbol]`, `[gunsymbol]`, `[armsymbol]`, `[swordsymbol]`, `[fistsymbol]`, `[scythesymbol]`, `[helmsymbol]`, `[armorsymbol]`, `[ringsymbol]`, `[shieldsymbol]`, `[starsymbol]` | 12 to 39 each | Equipment type icons in item and tech names. | Keep as the first character of the name. Each counts as 1 character of the length limit. |
| `[attr,..]`, `[attrs,..]`, `[stat,..]`, `[func1,..]`, `[func2,..]`, `[gfx,..]`, `[goto,..]`, `[spc,..]`, `[len,..]`, `[out,..]`, `[substr,..]` | dozens | Layout, numbers, graphics and addresses for menu screens. | Opaque. Never edit. They only appear in `*r screens` and a few status strings. |

Special case, the party names. The script uses these eight tokens for the seven playable characters
and the Epoch: `Crono`, `Marle`, `Lucca`, `Frog`, `Robos`, `Ayla`, `Magus`, `Epoch`. The
game swaps them when the player renames a character. (D, M)

- Keep them spelled exactly like this, in every occurrence. Note `Robos`, not `Robo`. The header of
  the script says explicitly not to change it. It appears 316 times.
- Do not inflect or decorate them: no `Cronos`, no `Marlezinha`, no `Lucquinha`.
- Do not put an article in front of them when the sentence can avoid it (`a espada de Crono`, not
  `a espada do Crono`), because the article would have to agree with a name the player can change.

## 4. Layout: pages, lines, pixels, characters

### 4.1 Pages and lines

A page is the text between two of `[pause]`, `[cls]`, `[next]` or the start and end of the string.

- A page holds at most 4 lines. A fifth line makes `ctinsert` print `Error: Too long text` and the
  build is unsafe. (M)
- In the original, pages have 1 to 4 lines: 1 line 1852 times, 2 lines 2181, 3 lines 972,
  4 lines 336. Aim for the same number of pages as the source, and no more lines than the source
  page unless you need it.

### 4.2 Line width

- Standard dialogue lines are limited to about 235 to 240 px, counting the 3 space indent (12 px).
  Some original lines reach 236 px. The validator estimates the wrap with 240. (M)
- Width is the sum of the glyph widths in Appendix A. Do not estimate by counting characters.
- The wrapper treats text after `[pause]` as continuing the same line. Keep the exact pattern the
  source uses after each `[pause]` (newline plus 3 spaces, or a plain newline) so the layout does not
  change. (M)

### 4.3 Narrow boxes and single-line fields

The automatic wrapper does not know the size of each box. It wraps everything at 240 px. For a
narrower box this overflows, which is exactly the "Enemies will attack even if you're no / t" bug
that appeared on the Battle Mode screen. (M)

So for every block other than plain dialogue, the ceiling is the widest line the English version of
that block uses (column "Limit" in section 2). Single-line blocks must stay on one line. Two-line
blocks (`prompts`, `tres msg`) must break with `[nl]` by hand, and each line must fit the ceiling.

### 4.4 Fixed-width names (items, techs, monsters, item classes, battle labels)

These fields have a fixed byte width. The tool truncates a name that is too long silently, with no
warning (the warning exists in the source but is compiled out). This is the most dangerous rule in
the project. (D, M)

- Length counts visible characters, and each `[...symbol]` counts as 1.
- Items and techs: 11 in total. A name with a symbol therefore has 10 characters for the name
  itself, for example `[bladesymbol]Wood_Sword` is 1 + 10.
- Monsters: 11. Item classes: 10. Battle menu labels: 7. Double and Triple Technique labels: 16.
- Word gaps: items and techs use `_` for a space between words (`Wood_Sword`, `Flame_Toss`),
  monsters use a normal space (`Blue Imp`). Copy the convention of the block you are in.
- Pad names with spaces to the full width, like the source does (`Cyclone    `). Do not trim.
- If the natural name does not fit, shorten in this order: drop articles and prepositions
  (`Espada de Madeira` becomes `EspMadeira`), then use a standard abbreviation from the glossary,
  then pick a shorter synonym. Record every abbreviation in the glossary so it stays consistent.
- These fields use the fixed 8px font. The variable-width font that would allow longer names is
  disabled because it crashes the tool on this toolchain. Names longer than 10 or 11 characters are
  not possible until that is solved.

### 4.5 Manual line breaks in dialogue

The source uses `[nl]` for every line break, both real ones and wrapping ones. The automatic
wrapper can flow a paragraph by itself and it produced correct breaks in every test. (M)

- If a `[nl]` in the source splits a sentence in the middle, it is only a wrapping artifact. Remove
  it in the translation and let the wrapper break the line.
- If a `[nl]` in the source comes after `.`, `!`, `?` or `:` and starts a new sentence or a new
  speaker line, it is deliberate. Keep a `[nl]` at the equivalent place.
- After a `[nl]` keep the 3 space indent when the source has it.
- Lists, signs and titles keep their manual breaks.

Words longer than a line (about 25 characters) must never appear. The wrapper splits them badly and
loses characters: in a test `Pneumoultramicroscopicossilicovulcanoconiose` came out as
`neumoultramicroscopicossilicovulcano` plus `oniose`. (M)

### 4.6 Centering with spaces

Episode names, era names and the treasure box messages are centered by leading spaces, not by the
engine:

```
$HXws:   The Millennial Fair      (22 wide, 3 leading spaces)
$HYAg:     ???
$8WRs:[nl]
                Got 1 [item]!
```

When you translate, recompute the leading spaces so the text is centered in the same total width.
Do not copy the English padding.

### 4.7 Characters that exist

Dialogue (12px font) can show only these characters (M):

```
A-Z  a-z  0-9  !  ?  /  :  &  (  )  '  .  ,  =  -  +  %  space  «  »
plus the single glyphs [musicsymbol], [heartsymbol] and the ellipsis
```

Type the ellipsis as three dots `...`, the tool turns it into one glyph. Never type the single
ellipsis character, the em dash or the en dash.

Not available: `"` (double quote), `;`, `*`, `@`, `~`, `_` (except in the 8px fields as described),
`¿`, `¡`, and every accented letter. Also avoid `#` and the degree sign, they share slots with the
music and heart glyphs. Quotation marks in the source are `'` inside dialogue and `« »` in battle
quotes and descriptions. Keep that convention.

Accented letters are added to both fonts by `cc-extrator accents`, which draws them from the
existing letters and registers them in `work/ct.cfg`. Run it once after `extract`. The set is:

```
á à â ã é ê í ó ô õ ú ç      Á À Â Ã É Ê Í Ó Ô Õ Ú Ç
```

`ü` and `Ü` are not included, they left Brazilian Portuguese with the 2009 spelling reform.

- The 12px dialogue font has all 24. Accent marks sit in the two free rows above lowercase letters.
  Capitals fill the cell, so accented capitals are drawn a little shorter than plain ones. Tilde,
  acute, grave, circumflex and cedilla are all drawn in the game's own stroke style.
- The 8px font (item, tech and monster names) also has all 24. The accented capitals there are
  squeezed to 6 rows, so prefer names that do not start with an accented capital when a good
  alternative exists.
- `check` reads `work/ct.cfg`, so it accepts exactly the accents the font really has, and points
  to `cc-extrator accents` when one is missing. Without them `ctinsert` rejects each accent with
  `Error: Irrepresentible character`. (M)
- The glyphs use free slots and `ctinsert` promotes the most frequent ones into single byte slots,
  so the common accents (`ã`, `ç`, `é`, `á`) cost no extra space in the script.

## 5. Things the tool does not warn about

Learn these, they were all reproduced. (M)

- A fixed-width name that is too long is cut off silently.
- `ctinsert` writes a patch file even when it printed `ERROR:` lines. A patch produced after an
  error is broken. Any line starting with `ERROR` or `Error` means stop.
- `Error: Too long text` means a page has more than 4 lines.
- `Error: Irrepresentible character` means a character outside section 4.7.
- `ctinsert` prints its errors in upper case (`ERROR: Page 18 doesn't have ...`). A case sensitive
  filter such as `grep rror` hides them. `insert` catches them for you.
- `ERROR: Page NN doesn't have X bytes of space` means the script grew too much. It cascades from
  other errors, so fix the first error first.
- Unicode punctuation copied from a chat or a word processor (curly quotes, en dash, non breaking
  space) will fail. Type plain ASCII punctuation.

## 6. Names and terminology

The glossary `notebook/glossary.tsv` is authoritative. It lists every item, tech, monster, place,
era and episode name with its length limit and an empty `ptbr` column, plus the 88 speaker labels.
Fill it first, review it, and only then translate the running text. If a term is in the glossary, use
that exact form everywhere, with no variation for style.

The glossary also holds 83 `term` rows with the agreed translation of the recurring story terms
(Masamune, Portal, Concha Arco-Íris, Palácio do Oceano and so on). A mark such as (m) or (f) is the
grammatical gender, for agreement only.

Policy for proper nouns (P):

- Keep unchanged: character names, and invented place, group and creature names that are not
  descriptive words (Guardia, Zeal, Lavos, Truce, Porre, Medina, Ozzie, Spekkio, Gaspar, Kajar,
  Enhasa, Dorino, Choras, Zenan, Denadoro, Reptites, Nu, Gato, Mystics).
- Translate: descriptive names (`Northern Ruins`, `Truce Canyon`, `Black Omen`, `End of Time`,
  `Dark Ages`, `Middle Ages`, `The Millennial Fair`, `Snail Stop`).
- Item and tech names: translate by meaning when it fits the limit, otherwise keep a short
  established English form. Attack names of the party (`Cyclone`, `Slash`) may stay if they are
  already understood as names. Record each decision in the glossary.
- Speaker labels: names stay (`CYRUS`, `LEENE`, `DALTON`), roles are translated (`SOLDIER` to
  `SOLDADO`, `MOM` to `MÃE`, `OLD MAN` to `VELHO`, `CHANCELLOR` to `CHANCELER`). Labels are
  upper case followed by a colon and one space, keep that shape.
- Alternate names in the source (`Nadia` for Marle, `Glenn` for Frog, `Janus` for Magus) are the
  same characters. Keep them as they are and do not merge them.

Consistency checks the reviewer must run: every glossary term appears translated the same way in
all blocks, and no English left-overs in the translated file except the kept proper nouns.

## 7. Voice and register

The English text is Ted Woolsey's 1995 localization: colloquial, jokey, with strong character
voices. A flat, literal translation loses the game. Before translating a character's lines, the
agent reads at least 10 existing lines of that character. (P)

Per-character notes (who they are, measured voice statistics, real sample lines, proposed pt-BR voice)
are in `notebook/characters/`. Load the files of the speakers in the batch. Speaker labels are
shared in some places (`KING`, `QUEEN`, `CHANCELLOR`, `OLD MAN`), the era comment of the block tells
which person speaks. See `notebook/characters/README.md`.

General:

- Standard Brazilian Portuguese, neutral, no regional slang tied to one state. No European
  Portuguese forms.
- Address: `você` for everyone by default. No `tu` in casual speech.
- Informal spoken forms are fine where the English is casual: `pra`, `pro`, `tá`, `né`. Keep them
  consistent per character.
- The game is family friendly. Keep the level of the original: no stronger profanity than the
  source.
- Keep the humor. If a pun cannot survive, replace it with an equivalent joke of similar length,
  never with an explanatory sentence.

Per character (P, confirm or correct these against the lines in the script):

| Character | Voice | pt-BR device |
|---|---|---|
| Crono | Silent. Only a few choices and `...` lines. | Keep `...` and short replies. |
| Marle | Bubbly, warm, impulsive, a princess who hides it. | Informal, exclamations, `pra`/`né`. |
| Lucca | Sharp, technical, confident, a little bossy. | Precise words, quick sentences. |
| Frog | Knightly and archaic. | `você` with a few old-fashioned words (`deveras`, `outrora`, `mui`, `ó`, `cavaleiro`), full sentences, no slang. No `vós` forms (`passai`, `vossa`) except the title `Vossa Majestade`. |
| Robo (`Robos`) | Polite, precise, a bit stiff, literal. | Formal `você`, complete sentences, no slang. |
| Ayla | Cavewoman, primitive grammar, third person. | Short sentences, infinitive verbs, `Ayla` for herself, occasional capitals for shouting. |
| Magus | Cold, formal, sarcastic. | Short, controlled sentences, no exclamation marks unless the source has them. |
| Narration and signs | Neutral. | Plain and short. |

Ayla's `[crononick]` is a name she uses for Crono, treat it as a name in her sentences.

## 8. Portuguese rules

### 8.1 Length

**Space budget (M).** The ROM stays at 32 Mbit because the target is RomM with EmulatorJS. The text
areas of the cartridge hold about 192 KB of compressed script and the English one already uses
160 KB. Measured with real `ctinsert` runs on a proxy for longer text:

| Total script growth over English | Result |
|---|---|
| up to about +9.5 percent | fits |
| +12.8 percent | 5 pages overflow, 1.9 KB short |
| +15.8 percent | 6 pages overflow, 5.9 KB short |

So the whole translation has to stay within roughly 10 percent of the English length, counting all
strings. Portuguese naturally runs 20 to 30 percent longer, so this is a hard constraint on style:
condense, cut filler, prefer short words. A 48 Mbit ROM would remove the limit but it corrupted
the graphics and text when tried (see the README), so it is not an option.

Run `cc-extrator budget` after every batch. It reports the growth over English, the space used on each
page and the tightest pages, and says which pages overflow and by how many bytes. Pages fill
unevenly: near the limit the dialogue pages 36, 37 and 38 fill up first.

Portuguese runs longer than English. Measured examples in this project: `Lucca: Man, that fool
sleeps a lot.` is 193 px and a natural translation is 222 px. Budget for it before writing.

Ways to fit, in this order:

1. Cut what the English says twice, drop filler and subject pronouns where Portuguese allows.
2. Prefer the shorter of two natural options (`quer` over `deseja`, `casa` over `residência`).
3. Merge or split sentences across the pages the source already has.
4. Use a contraction or an informal form if it matches the character.
5. Only then abbreviate, and never in dialogue for the sake of length alone.

### 8.2 Punctuation and typography

- Keep the source's `!`, `?`, `!?` and `...` habits. Do not add `!` for emphasis the English does
  not have.
- Sound effects: adapt short ones to Portuguese (`Whoosh` becomes `Fiuu`, `Grribit` becomes
  `Crroac`) and keep cries that have no Portuguese form, such as `GRAAAACK`.
- No `¿` or `¡`. Portuguese does not use them.
- Numbers: use `.` as the thousands separator (`65.000.000`), which is a `.` glyph (3 px). Dates
  such as `1000AD` become `1000 d.C.` only if it fits, otherwise keep the source form.
- Percent, plus, minus and equals signs exist. Use them as the source does.

### 8.3 Capitalization

- Speaker labels are upper case.
- Item, tech and place names follow the source: mostly initial capitals per word for names, sentence
  case for descriptions. Do not switch styles inside a block.
- Portuguese does not capitalize weekdays, months or adjectives of origin. Only the source's
  capitalization for proper nouns is kept.

### 8.4 Placeholders and agreement

The game fills `[item]`, `[tech]`, `[monster]`, `[member1]` and `[num..]` at runtime. Nothing can be
adjusted for the value, so the sentence must work for every value.

- Do not put a gendered article, adjective or participle next to a placeholder.
  `You got 1 [item]!` becomes `Você obteve 1 [item]!`, not `Você obteve o [item]!`.
- Rephrase to a form that needs no agreement: `Item obtido: [item]`, `Aqui está: [item]`.
- For numbers, prefer a form that works for 1 and for many: `[num32] ponto(s) de experiência`.
- Party members can be any character. Avoid words like `cansado` or `cansada` about
  `[member1]`. Use `sem energia`, `no limite`, or turn it into a verb (`Você precisa descansar`).

## 9. Examples, checked against the real widths

Widths use Appendix A. An accented letter is assumed to have the width of its base letter.

Narrow box (prompts, ceiling 172 px):

```
EN  Enemies will attack even[nl]if you're not ready!        144 px / 114 px
PT  Inimigos atacam mesmo[nl]se você não estiver pronto!    142 px / 160 px   fits
```

Single-line description (tech descs, ceiling 199 px):

```
EN  Attack enemy w/ Confuse 4 times          199 px
PT  Ataca o inimigo com Confusão 4 vezes     224 px   TOO LONG
PT  Ataca 4 vezes com Confusão               168 px   fits, shorter and just as clear
```

Fixed-width name (items, 11 total with the symbol):

```
EN  [bladesymbol]Wood_Sword       1 + 10
PT  [bladesymbol]EspMadeira       1 + 10   fits
PT  [bladesymbol]Espada_Madeira   1 + 14   TRUNCATED SILENTLY, never do this
```

Dialogue keeping a deliberate break and dropping a wrapping one:

```
EN  LEENE: Cyrus![nl]
       Are you leaving?
PT  LEENE: Cyrus![nl]
       Você está indo embora?
```

Placeholder:

```
EN  You got 1 [item]!
PT  Você obteve 1 [item]!
```

## 10. Open decisions

These need your answer before the agent runs at scale. My recommendation is in bold.

1. **Accent budget. Done.** 24 glyphs in both fonts, placed in free slots. The dictionary is not
   shrunk, `ctinsert` moves the frequent accents into single byte slots by itself.
2. **Variable width 8px font.** It would raise the name limits from 10 or 11 to about 16 characters
   but it crashes the tool here and works only in emulators. **Recommendation: skip it for now,
   design names for 11 characters, revisit if too many names suffer.**
3. **Frog's address form. Done.** `você` with a few archaic touches for Frog, Cyrus, Glenn, Slash and
   the other knights and Mystics, no `vós` forms.
4. **Item and tech names.** Translate everything, or keep English names for attacks? **Recommendation:
   translate items and monsters, keep the party's attack names when they already work as names.**
5. **`*r screens`.** **Recommendation: leave in English for the first playable version, translate
   after the dialogue is stable.**
6. **A validator. Done.** `cc-extrator check` compares `work/ct.txt` with `work/ct.en.txt` and fails
   on altered or missing control codes, names over their fixed width, lines over their block ceiling,
   pages over 4 lines, unknown characters and accents, and structure changes. `insert` runs it first
   and also stops when `ctinsert` prints an error.

7. **English versus the Japanese original.** The Chrono Compendium documents places where the English
   localization changed the characters or the story: Frog's formal tone, Robo having no emotions,
   Spekkio's cynicism, Crono's Mom, some hints and lines. A fan Retranslation also exists.
   **Recommendation: translate the English script that is in the ROM, and use the Retranslation
   only to resolve lines whose meaning is ambiguous or clearly wrong. Log each deviation.**

## 11. Workflow

1. Run `extract`, then `accents`. `extract` keeps the English script as `work/ct.en.txt`.
2. Fill the glossary (`notebook/glossary.tsv`), get it reviewed, then freeze it.
3. Translate block by block in this order: item classes, item types, items, techs, monsters, places,
   eras, episodes, battle strings, prompts and config, descriptions, then dialogue by era.
4. Run `cc-extrator check` and `cc-extrator budget` after every batch, then `insert`. All stop on problems.
5. Test the ROM in Mesen2 after every block, not after the whole game. Check the screens where the
   text appears: item and tech menus, battle, shops, the era and episode lists, and a few dialogues
   of the longest kind.
6. Keep a decision log for every glossary term and style choice that was not obvious.

## Appendix A: pixel widths of the 12px font

Measured from the game's font width table. Sum the widths of a line to get its pixel width.
Control codes have no width. The 3 space indent adds 12 px.

| Width | Characters |
|---|---|
| 3 px | `i` `l` `!` `:` `'` `.` `,` |
| 4 px | `(` `)` space `1` `_` |
| 5 px | `I` `t` `/` |
| 6 px | `E` `F` `L` `S` `c` `f` `j` `r` `s` `»` |
| 7 px | `A` `B` `C` `D` `G` `H` `J` `O` `P` `Q` `R` `T` `U` `V` `X` `Y` `Z` `a` `b` `d` `e` `g` `h` `k` `n` `o` `p` `q` `u` `v` `x` `y` `z` `0` `2` `3` `5` `6` `7` `8` `9` `?` |
| 8 px | `K` `N` `4` `«` `=` `-` `+` |
| 9 px | `M` `&` `%` and the ellipsis glyph |
| 11 px | `W` `m` `w` and the music and heart glyphs |

## Appendix B: limits at a glance

| Field | Limit |
|---|---|
| Dialogue line | 235 px including indent |
| Dialogue page | 4 lines |
| Item and tech name | 11 visible characters, symbol counts 1 |
| Monster name | 11 |
| Item class | 10 |
| Item type | 10 |
| Battle menu label | 7 |
| Double and Triple Technique labels | 16 |
| Place name | 14 characters, 87 px |
| Era name | 12 characters, 77 px |
| Episode name | 22 characters, 120 px |
| Item description | 1 line, 211 px |
| Tech description | 1 line, 199 px |
| Battle message | 1 line, 233 px |
| Prompt | 2 lines, 172 px each |
| Config option | 1 line, 136 px |
