# SPWIN v2.6 Capital Preservation

SPWIN v2.6 is a conservative engine designed to preserve capital first.

## Philosophy

PASS is the default. A bet is allowed only when:

- Capital Preservation Index is high enough
- Market consensus is at least 3 of 4
- No red flags are present
- Stake size remains small

## Run command

```bash
python tools/run_spwin_v260_gold_replay.py --gold-dir data/world_cup_2026/gold --bankroll 1000 --out-dir reports/benchmark/spwin_v2_6_gold
```

## Outputs

```text
reports/benchmark/spwin_v2_6_gold/spwin_v2_6_gold_replay_summary.json
reports/benchmark/spwin_v2_6_gold/spwin_v2_6_gold_replay_rows.json
reports/benchmark/spwin_v2_6_gold/spwin_v2_6_gold_replay.csv
```

## Key rules

- CPI 92+ can qualify as Elite
- CPI 88+ can qualify as Strong
- CPI 84+ can qualify as Micro
- Below 84 is PASS
- Any major red flag is PASS
- Consensus below 3 of 4 is PASS
- Maximum stake is 2 percent of bankroll

## Red flags

Examples:

- Favourite drift
- Draw compression
- AH disagreement
- HT draw pressure
- Ultra-short price risk
- Weak favourite price

## Purpose

This engine should be compared against v2.5.2 on the same Gold dataset to confirm whether capital preservation improves final bankroll and reduces drawdown.
