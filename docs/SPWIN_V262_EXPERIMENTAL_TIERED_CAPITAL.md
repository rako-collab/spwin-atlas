# SPWIN v2.6.2 Experimental Tiered Capital Preservation

## Status

Experimental calibration version.

SPWIN v2.6.1 remains the frozen production baseline. SPWIN v2.6.2 is not a new baseline and should not be promoted to v2.7 unless replay results justify it.

## Purpose

SPWIN v2.6.1 preserved capital but produced very low activity:

- 33 Gold matches
- 3 bets
- 3 wins
- 0 losses
- Final bankroll: $1006.01
- ROI: +0.60%
- Max drawdown: 0.00%

v2.6.2 tests whether the engine can safely increase bet count without abandoning the capital-preservation philosophy.

## Design Principles

1. Preserve capital first.
2. Never force a bet.
3. PASS remains acceptable.
4. Do not overwrite or modify v2.6.1.
5. Use only immutable Gold records for replay.
6. Keep the replay blind: recommend first, settle after.

## Key Changes vs v2.6.1

### 1. Tiered staking

v2.6.1 used a hard gate:

- CPI >= 80
- Consensus >= 3/4
- Zero red flags

v2.6.2 introduces tiered exposure:

| Tier | Rule | Stake |
| --- | --- | --- |
| Tier A | CPI >= 88, consensus 4/4, zero minor flags | 1.00% |
| Tier B | CPI >= 80, consensus >=3/4, zero minor flags | 0.75% |
| Tier C | CPI >= 76, consensus >=3/4, zero minor flags | 0.50% |
| Favourite Safe Micro | Odds 1.18–1.45, CPI >=72, consensus >=3/4, max one minor flag | 0.25% |
| PASS | Anything else | 0.00% |

### 2. Major/minor red flag split

Major red flags remain automatic PASS:

- favourite drift
- AH drift/disagreement
- weak favourite price
- no favourite

Minor red flags may reduce the engine to micro stake only:

- draw compression
- HT draw pressure
- ultra-short price risk

### 3. Favourite Safe Micro Zone

This is a controlled short-favourite expansion zone. It only applies when:

- Favourite odds are between 1.18 and 1.45
- CPI >= 72
- Consensus >= 3/4
- No major red flags
- Maximum one minor red flag

Stake is capped at 0.25%.

## Replay Command

```bash
python tools/run_spwin_v262_gold_replay.py --gold-dir data/world_cup_2026/gold --bankroll 1000 --out-dir reports/benchmark/spwin_v2_6_2_gold
```

## Output Files

The replay writes:

- `spwin_v2_6_2_gold_replay_summary.json`
- `spwin_v2_6_2_gold_replay_rows.json`
- `spwin_v2_6_2_gold_replay.csv`

## Promotion Criteria

v2.6.2 should only be considered for v2.7 baseline if it improves activity and bankroll profile without materially increasing risk.

Suggested evaluation targets:

- More bets than v2.6.1
- Positive ROI
- Max drawdown below 2%
- Profit factor above 1.5
- No evidence of obvious overfitting

## Current Baseline Comparison

| Metric | v2.6.1 Baseline | v2.6.2 Target |
| --- | ---: | ---: |
| Bets | 3 | 6–10 preferred |
| ROI | +0.60% | Higher than v2.6.1 |
| Max drawdown | 0.00% | <2.00% |
| Losses | 0 | Acceptable if controlled |
| Philosophy | Capital preservation | Capital preservation |
