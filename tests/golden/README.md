# The golden set

About 200 sequences, and the full answer DNAbarcode.org gives to each, used to
prove that reorganising the platform changes nothing. The known-answer checks
in `../known-answers/` compare only the answer text of a few hand-picked sequences
on every deploy; the golden set compares everything (the answer, notes,
strand, region and the decision trace, but not timings) for many more.

| File | What |
|---|---|
| `sequences.jsonl` | The sequences, with their stratum and source record |
| `answers.jsonl` | The recorded answers |

The sequences come from the test splits (never used to train or tune the
models), chosen at random but reproducibly by `scripts/golden.py select`:

| Stratum | Count | What it covers |
|---|---|---|
| `mosquito` | 50 | Named mosquito species, one per species |
| `mosquito-novel` | 25 | Mosquito species held out of training |
| `mosquito-unnamed` | 10 | Mosquito records without a species name |
| `other-fly` | 25 | Other flies (Diptera), one per family |
| `other-animal` | 40 | Other organisms (animals, fungi and others), one per order |
| `short`, `reverse`, `window` | 6 each | The first 150 bases, the other strand, and a 300-base window of mosquito sequences |
| `gene-<gene>` | 2 per gene | Other mitochondrial genes, which must be declined |

To compare a bundle's answers with the recorded ones:

```bash
pixi run golden-check                                    # the local bundle
pixi run python scripts/golden.py check --bundle PATH    # another bundle
```

It lists every difference and fails if there are any. After a deliberate
change (new models or references), review the differences, then record the
new answers with `pixi run python scripts/golden.py write --force`.

The sequences are from MIDORI2 (GenBank release 273), licensed under
CC BY 4.0. Cite https://doi.org/10.5281/zenodo.22685701 and Leray et al.
(2022), Environmental DNA 4: 894-907, https://doi.org/10.1002/edn3.303.
