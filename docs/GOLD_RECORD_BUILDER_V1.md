# SPWIN Atlas Gold Record Builder v1.0

## Purpose

Gold Record Builder v1.0 speeds up the SPWIN Atlas workflow by converting raw SGOdds-style pasted match text into draft Gold JSON records.

It is designed around the validated 25–26 Jun 2026 reference batch, including match types such as:

- False favourite trap
- Balanced draw
- Elite favourite steam
- Low-scoring false favourite
- High-event favourite with resistance
- Stable favourite execution

## Repository source of truth

For SPWIN Atlas, the GitHub repository is the authoritative source for historical data:

```text
rako-collab/spwin-atlas
```

Gold records are stored under:

```text
data/world_cup_2026/gold/
```

Historical Gold records are immutable under Rule 7. Corrections must be committed as new versions, not as destructive overwrites.

## Input format

Each raw input file should contain one full match block in this format:

```text
Ecuador vs Germany (26 Jun 2026)
All past odds movement before match closed. Result HT: 1-1 FT: 2-1

Asian Handicap (Account Only)
Ecuador +0.75
1.80
1.92
+6.7%
Germany -0.75
2.00
1.85
-7.5%
...
```

Save each raw match as a `.txt` file.

Example:

```text
raw_batch/ecuador_vs_germany.txt
raw_batch/japan_vs_sweden.txt
raw_batch/czech_republic_vs_mexico.txt
```

## Single-match build

```bash
python tools/gold_record_builder.py \
  --input raw_batch/ecuador_vs_germany.txt \
  --out data/world_cup_2026/gold
```

## Batch build

```bash
python tools/gold_record_builder.py \
  --input-dir raw_batch \
  --out data/world_cup_2026/gold
```

## Batch build with index update

```bash
python tools/gold_record_builder.py \
  --input-dir raw_batch \
  --out data/world_cup_2026/gold \
  --index data/world_cup_2026/gold/MATCH_INDEX.json
```

## Output

For each match, the builder creates:

```text
WC2026-GRP-XXX-YYY_v1.0.json
```

The generated record contains:

- Match metadata
- HT/FT result
- Parsed markets
- Opening odds
- Closing odds
- Odds movement percentage
- Best-effort market result labels
- Derived SPWIN pattern tag
- Rule 7 provenance

## Review requirement

The builder is intentionally conservative. It produces draft Gold records that should be reviewed before committing.

Check especially:

- Team abbreviations in the filename
- Asian Handicap settlement
- First-goal markets, if the exact first scorer/team is not present
- Market rows with unusual formatting
- Correct score markets with duplicate team labels

## Recommended commit workflow

1. Paste or save 5–10 raw matches into `raw_batch/`.
2. Run the builder with `--input-dir`.
3. Review generated JSON files.
4. Run repository integrity checks.
5. Commit generated JSONs and `MATCH_INDEX.json` together.

Suggested commit message:

```text
SPWIN Atlas: Add validated Gold batch

- Added N validated World Cup 2026 Gold records
- Generated with Gold Record Builder v1.0
- Included archived closing odds and odds movement
- Updated MATCH_INDEX.json
- Preserved immutable historical records
```

## SPWIN replay rule

During blind replay, SPWIN must use only archived pre-match fields. The result fields exist for validation only and must not be read until after the recommendation is locked.
