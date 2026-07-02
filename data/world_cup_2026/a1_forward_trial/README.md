# A1 Forward Trial

This directory stores the append-only forward-trial ledger for SPWIN v2.6.1-A1.

## Files

- `A1_TRIAL_LEDGER.csv` — one row for every remaining World Cup match reviewed.

## Required discipline

- Log every match, including A1 PASS decisions.
- Complete all pre-match fields before kickoff.
- Set `locked=TRUE` no later than 15 minutes before kickoff.
- Do not edit locked decision or observation fields after kickoff.
- Complete settlement fields only after the match ends.
- Use Singapore time for all timestamps.
- Leave unavailable raw values blank; use the explicit unavailable observation label.

## Observation-only fields

Every match must include:

- `price_zone_label`
- `controlled_steam_label`
- `draw_structure_label`

The corresponding draw opening, final, and movement fields are also stored. These labels are descriptive and must never create or alter a v2.6.1 or A1 bet.

The operating rules are defined in `docs/SPWIN_V261_A1_FORWARD_TRIAL_PROTOCOL.md`.
