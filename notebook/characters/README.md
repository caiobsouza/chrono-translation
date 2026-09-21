# Characters

Notes for the translator agent, one file per character. Load only the files for the speakers in the batch being translated.

Each file has a summary of the character (paraphrased from the Chrono Compendium, with the page linked), the voice observed in the English script with statistics and sample lines taken from `work/ct.txt`, and a proposed pt-BR voice. The proposals are not decisions yet.

The Compendium says little about how characters speak, so the voice sections are based on the script itself, not on the wiki. Where the wiki documents that the English localization differs from the Japanese original, it is recorded under `English versus original`.

The sample lines are game text, so keep this repository private.

| Character | Speaker labels in the script | File |
|---|---|---|
| Crono | `Crono` | `crono.md` |
| Marle | `Marle` | `marle.md` |
| Lucca | `Lucca` | `lucca.md` |
| Frog | `Frog`, `GLENN` | `frog.md` |
| Robo | `Robos` | `robo.md` |
| Ayla | `Ayla` | `ayla.md` |
| Magus | `Magus`, `JANUS`, `PROPHET` | `magus.md` |
| Belthasar | `BELTHASAR` | `belthasar.md` |
| Chancellor | `CHANCELLOR`, `REAL CHANCELLOR` | `chancellor.md` |
| Crono's Mom | `MOM` | `cronos-mom.md` |
| Cyrus | `CYRUS` | `cyrus.md` |
| Doan | `DOAN` | `doan.md` |
| The Entity | none | `entity.md` |
| Fiona | `FIONA` | `fiona.md` |
| Gaspar | `GASPAR`, `OLD MAN` | `gaspar.md` |
| Janus | `JANUS` | `janus.md` |
| Johnny | `JOHNNY` | `johnny.md` |
| King Guardia XXI | `KING` | `king-guardia-xxi.md` |
| King Guardia XXXIII | `KING`, `KING GUARDIA` | `king-guardia-xxxiii.md` |
| Kino | `KINO` | `kino.md` |
| Mammon Machine | none | `mammon-machine.md` |
| Masa and Mune | `MASA`, `MUNE` | `masa-and-mune.md` |
| Melchior | `MELCHIOR` | `melchior.md` |
| Norstein Bekkler | none | `norstein-bekkler.md` |
| Nu | none | `nu.md` |
| Poyozo Dolls | none | `poyozo-dolls.md` |
| The Prophet | `PROPHET` | `the-prophet.md` |
| Queen Leene | `LEENE`, `QUEEN` | `queen-leene.md` |
| Schala | `SCHALA` | `schala.md` |
| Spekkio | `SPEKKIO` | `spekkio.md` |
| Tata | `TATA` | `tata.md` |
| Toma | `TOMA` | `toma.md` |
| Ozzie | `OZZIE` | `ozzie.md` |
| Dalton | `DALTON` | `dalton.md` |
| Azala | `AZALA` | `azala.md` |
| Flea | `FLEA` | `flea.md` |
| Slash | `SLASH` | `slash.md` |
| Nizbel | `NIZBEL` | `nizbel.md` |
| Queen Zeal | `QUEEN` | `queen-zeal.md` |
| Yakra and Yakra XIII | none | `yakra.md` |
| Lavos | none | `lavos.md` |
| Mother Brain | none | `mother-brain.md` |
| Atropos XR | `ATROPOS` | `atropos-xr.md` |
| Taban | `TABAN` | `taban.md` |
| Lara | `LARA` | `lara.md` |
| Fritz and Elaine | `FRITZ`, `ELAINE` | `fritz-and-elaine.md` |
| Pierre | `PIERRE` | `pierre.md` |
| Judge | `JUDGE` | `judge.md` |
| Knight Captain | `KNIGHT CAPTAIN` | `knight-captain.md` |
| Chef | `CHEF` | `chef.md` |
| RX-XR | `RX-XR` | `rx-xr.md` |
| Marco | `MARCO` | `marco.md` |

## Labels shared by several people

- `KING` is King Guardia XXI (600 AD) and XXXIII (1000 AD). Use the era comment on the block.
- `QUEEN` is Queen Leene, Queen Zeal and possibly Queen Aliza. Use the era comment.
- `CHANCELLOR` is the real chancellor and the Yakra impersonating him. Use the era comment.
- `OLD MAN` is a generic label used by many elders, including Gaspar at the End of Time.
- `Magus`, `JANUS` and `PROPHET` are the same person in different situations.
- `Frog` and `GLENN` are the same person before and after the transformation.

## Generic role labels without a file

These labels stand for many different anonymous people, so they get no character note. Translate them by role and by the era comment: `SOLDIER` (25), `ELDER` (24), `ROBOT` (14), `GIRL` (10), `STRANGE CREATURE` (9), `UNDERLING` (9), `BOSS` (9), `SUPERVISOR` (8), `DIRECTOR` (4), `GUARD` (8).

## Grouped notes

- `enemies-and-bosses.md`: bosses and monsters that have no dialogue label.
- `minor-npcs.md`: unnamed and background characters, animals, and reference names.

## Decisions that come from these pages

1. The Compendium documents places where the English localization differs from the Japanese original (Frog's tone, Robo's emotions, Spekkio's cynicism, Crono's Mom, some hints). **Recommendation: follow the English script that is in the ROM, and only restore the original intent where the English is clearly a mistake that hurts the story.** Record each exception in the decision log.
2. The fan Retranslation exists and clarifies some lines (for example Belthasar's Death Peak speech). **Recommendation: use it as a reference for meaning when an English line is ambiguous, not as text to copy.**
