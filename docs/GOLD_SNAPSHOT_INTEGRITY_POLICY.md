# Gold Snapshot Integrity Policy

## Purpose

Gold records must preserve the exact market state used by SPWIN. A result is not reproducible when the record stores odds without their source timestamp, silently omits production channels, or labels an intermediate price as a true closing price.

## Immutable correction rule

1. Never overwrite or delete an existing Gold record.
2. Create a versioned correction such as `*_v1.1_correction.json`.
3. Set `correction_of` and provide a specific `correction_reason`.
4. Repoint `MATCH_INDEX.json` to the correction while retaining the superseded file.
5. Re-run integrity validation and the frozen-engine replay.

## Required metadata for new timestamped snapshots

Records that set `snapshot_integrity_required: true` must include:

- `source_last_updated_at`
- `captured_at`
- `scheduled_kickoff_at`
- `minutes_before_kickoff`
- `snapshot_role`
- `forward_lock_status`
- `odds_basis`
- `is_true_closing_odds`
- `source_market_coverage`

Use `PRELIMINARY_NOT_LOCKED` when the snapshot is outside the approved T-30 to T-15 forward-lock window. A historical replay may use the best timestamped source snapshot available, but that must not be represented as an official forward-trial bet.

## Market coding

- `1X2`: full-time home/draw/away
- `AH`: main Asian Handicap market
- `HANDICAP_ALT`: fixed alternative handicap, such as the 1/2 Goal market
- `HT_AH`: halftime Asian Handicap
- `HT_1X2`: halftime 1X2
- `FG`: team to score first
- `OU`: total-goals over/under
- `BTTS`: both teams to score

SPWIN v2.6.1 may search both `AH` and `HANDICAP_ALT` for the strongest favourite-aligned handicap row. The database must preserve which family each line came from.

## Validation

Run:

```bash
python3 tools/validate_gold_snapshot_integrity.py
python3 tools/validate_gold_replay_integrity.py
python3 tools/run_spwin_v261_gold_replay.py
```

The snapshot validator checks:

- movement percentages against opening and snapshot odds;
- required timestamp and lock metadata;
- declared market coverage against stored rows;
- full home/draw/away coverage when 1X2 is declared `FULL`;
- correction files that exist but have not been activated in `MATCH_INDEX.json`;
- locked snapshots that fall outside T-30 to T-15.

## Colombia vs Ghana precedent

`WC2026-R32-COL-GHA_v1.1_correction.json` replaces an incomplete v1.0 snapshot with the complete SGOdds state last updated at 07:50 SGT on 4 July 2026. The corrected snapshot produces a historical SPWIN v2.6.1 recommendation of Colombia 1X2 at 1.33, CPI 86, consensus 4/4 and a 1.25% stake. It remains marked `PRELIMINARY_NOT_LOCKED` because it was captured around T-100.
