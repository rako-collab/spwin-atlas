# SPWIN Atlas Historical Importer

The Historical Importer converts curated historical football match records into SPWIN Atlas CSV format.

## Goals

- Normalize historical tournament records into a consistent schema.
- Preserve data provenance for every imported row.
- Support incremental imports without manually editing every CSV.
- Keep SPWIN Atlas auditable and version controlled.

## Current Version

`historical_importer.py` is v0.1 and supports JSON input files.

## Input Format

Place source JSON files under:

```text
sources/<tournament_key>/
```

Example:

```text
sources/world_cup_2026/r32_south_africa_canada.json
```

## Run

```bash
python tools/importer/historical_importer.py \
  --input sources/world_cup_2026 \
  --output data/world_cup_2026
```

## Output Files

- `matches.csv`
- `odds.csv`
- `spwin_predictions.csv`
- `live_snapshots.csv`

## Data Quality

Use the `data_quality` field from 1 to 5.

| Score | Meaning |
|---:|---|
| 5 | Complete record: result, odds, lineups, stats, SPWIN output, provenance |
| 4 | Mostly complete, one secondary area missing |
| 3 | Result, odds, and basic stats |
| 2 | Result and limited statistics |
| 1 | Result only |
