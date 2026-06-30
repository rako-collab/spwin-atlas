# Historical Importer v2 — SGOdds Enrichment Pipeline

Historical Importer v2 is designed to enrich SPWIN Atlas using SGOdds `results-past-odds` match pages.

## Purpose

The current Atlas has match results and closing 1X2 odds. Importer v2 expands each match into a market-level database suitable for SPWIN v2.5.1 Capital Shield and future SPWIN v3.0 validation.

## Design Principles

- SGOdds is the primary odds source.
- Singapore Pools market codes are preserved.
- One row per market selection.
- No subjective enrichment.
- Every imported row must carry source URL and capture timestamp.
- Derived metrics are separated from raw odds.

## Input Sources

Importer v2 supports two input modes:

### 1. Saved HTML mode

Recommended for reliable backfilling.

```text
sources/sgodds/world_cup_2026/html/
  140174.html
  140179.html
  ...
```

Run:

```bash
python tools/importer_v2/sgodds_importer_v2.py \
  --input sources/sgodds/world_cup_2026/html \
  --output data/world_cup_2026 \
  --mode html
```

### 2. Text export mode

Use this when HTML parsing is blocked or pages are manually copied.

```text
sources/sgodds/world_cup_2026/text/
  140174.txt
```

Run:

```bash
python tools/importer_v2/sgodds_importer_v2.py \
  --input sources/sgodds/world_cup_2026/text \
  --output data/world_cup_2026 \
  --mode text
```

## Outputs

Importer v2 writes:

```text
data/world_cup_2026/markets.csv
data/world_cup_2026/derived_metrics.csv
data/world_cup_2026/import_audit.csv
```

## Supported Singapore Pools Markets

| Code | Market |
|---|---|
| 01 | 1X2 |
| 02 | Asian Handicap |
| 03 | HT/FT |
| 10 | Halftime 1X2 |
| 11 | Halftime Correct Score |
| 12 | Total Goals Over/Under |
| 14 | Halftime Goals Over/Under |
| 46 | Winning Margin |
| 50 | Team to Score Last |
| 53 | Team to Score 4th Goal |
| 82 | Which Half More Goals |
| 91 | Who Will Qualify |
| 95 | Both Teams To Score |
| 97 | HT Team To Score First |
| 98 | HT Odd/Even |
| 99 | HT Total Goals |

## Capital Shield Integration

The enriched market rows let SPWIN test markets other than 1X2. Capital Shield v2.5.1 still applies first:

- If no demonstrated edge, PASS.
- If historical profile is negative ROI, PASS.
- If data quality is incomplete, PASS.
- No subjective override.
