# SPWIN Backtest Engine

The SPWIN Backtest Engine replays historical matches using pre-match data stored in SPWIN Atlas.

## Current Version

`run_backtest.py` v0.1 supports a completed 1X2-only baseline backtest.

This is intentionally separate from the future full Singapore Pools market backtest because Asian Handicap, Over/Under, and BTTS historical markets are not yet complete for every match.

## Usage

```bash
python tools/backtest/run_backtest.py \
  --competition world_cup_2026 \
  --engine v2.5 \
  --markets 1x2
```

## Outputs

The script writes files under:

```text
backtests/world_cup_2026/v2_5_baseline_2026_1/
```

Generated outputs:

- `backtest_match_results.csv`
- `backtest_summary.csv`
- `roi_by_grade.csv`
- `roi_by_odds_band.csv`
- `roi_by_stage.csv`

## Important Limitation

The first pass is a 1X2 baseline only. It is useful for validating market favourite behaviour and PASS filters, but it is not the final full SPWIN v2.5 benchmark.

The full benchmark requires complete archived Singapore Pools markets:

- Asian Handicap
- Total Goals Over/Under
- BTTS
- Half-time markets where applicable
