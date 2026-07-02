# SPWIN v2.6.1 Calibrated Capital Preservation

SPWIN v2.6.1 keeps the v2.6 capital-preservation philosophy but calibrates the final betting gate so that clean, high-consensus opportunities are not over-filtered.

## Rule change from v2.6.0

v2.6.0 placed zero bets on the 33-match Gold benchmark.

v2.6.1 allows a bet only when all are true:

- CPI is at least 80
- Consensus is at least 3 of 4
- Red flags are zero

## Stake sizing

- CPI 85+ = 1.25 percent of bankroll
- CPI 80-84 = 0.75 percent of bankroll
- Anything else = PASS

## Run command

```bash
python tools/run_spwin_v261_gold_replay.py --gold-dir data/world_cup_2026/gold --bankroll 1000 --out-dir reports/benchmark/spwin_v2_6_1_gold
```

## Calibration benchmark result

On the 33 Gold records:

- Starting bankroll: 1000
- Final bankroll: 1006.01
- Bets: 3
- Wins: 3
- Losses: 0
- Passes: 30
- Max drawdown: 0.00 percent
- ROI: 0.60 percent

## Bet profile

The engine selected only three clean no-red-flag bets during calibration:

- Scotland vs Brazil: Brazil
- Norway vs France: France
- USA vs Bosnia and Herzegovina: USA

This version remains conservative and should be validated on future Gold records before further stake increases.
