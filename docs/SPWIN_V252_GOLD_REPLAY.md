# SPWIN v2.5.2 Gold Replay

Run from repository root:

```bash
python tools/run_spwin_v252_gold_replay.py --gold-dir data/world_cup_2026/gold --bankroll 1000 --out-dir reports/benchmark/spwin_v2_5_2_gold
```

Outputs:

```text
reports/benchmark/spwin_v2_5_2_gold/spwin_v2_5_2_gold_replay_summary.json
reports/benchmark/spwin_v2_5_2_gold/spwin_v2_5_2_gold_replay_rows.json
reports/benchmark/spwin_v2_5_2_gold/spwin_v2_5_2_gold_replay.csv
```

The engine reads pre-match market data first, locks the recommendation, then settles against the stored Gold result.

Default bankroll is 1000 dollars.
