# SPWIN Atlas

SPWIN Atlas is the structured football match database powering SPWIN v2.4 Platinum Pro, SPWIN-Live v2.4, SPWIN v2.5 Platinum Pro, and future SPWIN v3.0.

## Purpose

SPWIN Atlas stores international football match data in a structured, auditable format so SPWIN can move from fixed-weight analysis toward evidence-driven calibration.

## Current Phase

Phase 1: World Cup 2026 backfill and live tournament tracking.

## Core Principles

- Evidence over intuition
- Objective scoring only
- No subjective upgrades
- No manual override module
- PASS is a valid decision
- Data provenance matters
- Bankroll protection before profit maximization

## Initial Data Scope

1. FIFA World Cup 2026
2. FIFA World Cup 2022
3. FIFA World Cup 2018
4. UEFA Euro 2024
5. Copa America 2024
6. AFC Asian Cup 2023

## Repository Structure

```text
README.md
CHANGELOG.md
docs/
schema/
data/
analytics/
tools/
```

## Replay integrity validation

Run the integrity checks before accepting any experimental replay:

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_gold_replay_integrity.py
python3 tools/run_spwin_v261_gold_replay.py
```

A staked bet with unresolved settlement now fails closed instead of being silently treated as PASS. See `docs/SPWIN_V261_REPLAY_INTEGRITY_PATCH.md`.
