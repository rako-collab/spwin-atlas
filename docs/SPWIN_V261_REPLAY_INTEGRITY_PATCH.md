# SPWIN v2.6.1 Replay Integrity Patch

Date: 2026-07-02

## Purpose

Repair replay reproducibility and reporting without changing SPWIN v2.6.1 admission or staking rules.

## Changes

1. Restored the frozen v2.6.0 dependency:
   - ultra-short red flag: favourite closing odds `< 1.20`
   - CPI too-short band: favourite closing odds `< 1.20`

2. Added `spwin_engine/integrity.py`:
   - normalizes `Win`, `Loss`, `Lose`, `Push`, `Void`, and refund labels;
   - derives deterministic settlement from stored scores when records use `Archived` or missing labels;
   - raises an error when a staked bet cannot be settled, instead of silently counting it as PASS.

3. Added replay audit classifications to v2.6.1 output:
   - `BET`
   - `PASS_INCOMPLETE_DATA`
   - `PASS_RED_FLAG`
   - `PASS_MODEL`

4. Added market coverage fields:
   - `data_status`
   - `available_consensus_channels`
   - `missing_channels`
   - `decision_reasons`

5. Added integrity validation and regression tests:
   - `tools/validate_gold_replay_integrity.py`
   - `tests/test_replay_integrity.py`

## Validation result on uploaded repository

- Gold records: 57
- Complete market coverage: 24
- Partial market coverage: 33
- Unresolved 1X2 rows: 0
- Regression tests: 6 passed

### SPWIN v2.6.1 replay

| Metric | Result |
|---|---:|
| Records | 57 |
| Bets | 3 |
| Wins | 3 |
| Losses | 0 |
| Passes | 54 |
| Final bankroll | 1006.01 |
| ROI | 0.60% |
| Maximum drawdown | 0.00% |

The headline replay result is unchanged. No Gold records were edited.

## Commands

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_gold_replay_integrity.py
python3 tools/run_spwin_v261_gold_replay.py
```
