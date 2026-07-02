# Patch Manifest

Source archive: `spwin-atlas-main (4).zip`

Changed:
- `spwin_engine/v260.py`
- `spwin_engine/v261.py`
- `spwin_engine/v262.py`
- `README.md`
- `CHANGELOG.md`

Added:
- `spwin_engine/integrity.py`
- `tools/validate_gold_replay_integrity.py`
- `tests/test_replay_integrity.py`
- `docs/SPWIN_V261_REPLAY_INTEGRITY_PATCH.md`
- `reports/validation/gold_replay_integrity.json`
- `reports/benchmark/spwin_v2_6_1_gold/spwin_v2_6_1_gold_replay_summary.json`

Unchanged:
- all files under `data/world_cup_2026/gold/`
- SPWIN v2.6.1 recommendation and staking thresholds

Validated:
- 6/6 regression tests passed
- 0 unresolved 1X2 settlements
- replay remains 3 bets, 3 wins, final bankroll 1006.01

The detailed replay CSV and row-level JSON are reproducible by running `python3 tools/run_spwin_v261_gold_replay.py` and are not required for the integrity patch commit.
