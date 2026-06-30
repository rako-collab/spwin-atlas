#!/usr/bin/env python3
"""
SPWIN Atlas CSV Header Validator v0.1

Checks that core CSV files contain the expected headers.
"""

from __future__ import annotations

import csv
from pathlib import Path

EXPECTED_HEADERS = {
    "matches.csv": [
        "match_id", "tournament", "stage", "date_sgt", "kickoff_sgt", "home_team", "away_team",
        "ht_score", "ft_score", "winner", "btts", "total_goals", "over_2_5", "odd_even",
        "data_quality", "source_result", "source_odds", "source_stats", "notes"
    ],
    "odds.csv": [
        "match_id", "market", "selection", "line", "opening_odds", "current_odds", "closing_odds",
        "source", "captured_at_sgt", "notes"
    ],
    "spwin_predictions.csv": [
        "match_id", "engine_version", "pre_match_grade", "recommendation", "stake_pct", "result",
        "profit_loss_units", "clv_status", "notes"
    ],
    "live_snapshots.csv": [
        "match_id", "minute", "score", "home_xg", "away_xg", "home_sot", "away_sot", "home_corners",
        "away_corners", "home_possession", "away_possession", "live_engine_decision", "notes"
    ],
}


def validate_file(path: Path) -> bool:
    expected = EXPECTED_HEADERS[path.name]
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        actual = next(reader, [])
    if actual != expected:
        print(f"FAIL {path}: header mismatch")
        print(f"Expected: {expected}")
        print(f"Actual:   {actual}")
        return False
    print(f"OK   {path}")
    return True


def main() -> None:
    root = Path("data")
    files = [p for p in root.glob("**/*.csv") if p.name in EXPECTED_HEADERS]
    if not files:
        raise SystemExit("No SPWIN CSV files found under data/")
    valid = all(validate_file(path) for path in files)
    if not valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
