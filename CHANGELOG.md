# Changelog

## 2026-06-30

- Initialized SPWIN Atlas repository.
- Started Phase 1: World Cup 2026 backfill.
- Added initial schema and starter CSV files.

## 2026-07-02

- Restored the frozen v2.6.0 ultra-short favourite threshold to `<1.20` in both red-flag and CPI logic.
- Added fail-closed replay settlement normalization and score-derived fallback handling.
- Added explicit v2.6.1 PASS classifications for incomplete data, red flags, and model rejection.
- Added Gold replay integrity validation and regression tests.
- Initial integrity validation confirmed 3 bets, 3 wins, and final bankroll 1006.01 on the then-current 57-record Gold set.
- Updated the shared Gold loader to treat `MATCH_INDEX.json` as authoritative.
- Excluded four immutable superseded correction files from normal engine replays.
- Confirmed the authoritative 82-match v2.6.1 benchmark remains 3 bets, 3 wins, and final bankroll 1006.01.
