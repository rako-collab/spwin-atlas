#!/usr/bin/env python3
"""
SPWIN Atlas Historical Importer v0.1

Converts curated JSON match source files into SPWIN Atlas CSV files.

This importer intentionally does not scrape websites directly. It normalizes
curated records so every imported value remains reviewable and auditable.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List


MATCH_FIELDS = [
    "match_id",
    "tournament",
    "stage",
    "date_sgt",
    "kickoff_sgt",
    "home_team",
    "away_team",
    "ht_score",
    "ft_score",
    "winner",
    "btts",
    "total_goals",
    "over_2_5",
    "odd_even",
    "data_quality",
    "source_result",
    "source_odds",
    "source_stats",
    "notes",
]

ODDS_FIELDS = [
    "match_id",
    "market",
    "selection",
    "line",
    "opening_odds",
    "current_odds",
    "closing_odds",
    "source",
    "captured_at_sgt",
    "notes",
]

PREDICTION_FIELDS = [
    "match_id",
    "engine_version",
    "pre_match_grade",
    "recommendation",
    "stake_pct",
    "result",
    "profit_loss_units",
    "clv_status",
    "notes",
]

LIVE_FIELDS = [
    "match_id",
    "minute",
    "score",
    "home_xg",
    "away_xg",
    "home_sot",
    "away_sot",
    "home_corners",
    "away_corners",
    "home_possession",
    "away_possession",
    "live_engine_decision",
    "notes",
]


def safe_get(data: Dict[str, Any], key: str, default: Any = "") -> Any:
    value = data.get(key, default)
    return default if value is None else value


def append_rows(path: Path, fieldnames: List[str], rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def load_json_files(input_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for file_path in sorted(input_dir.glob("*.json")):
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            records.extend(payload)
        elif isinstance(payload, dict):
            records.append(payload)
        else:
            raise ValueError(f"Unsupported JSON root type in {file_path}")
    return records


def normalize_match(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "match_id": safe_get(record, "match_id"),
        "tournament": safe_get(record, "tournament"),
        "stage": safe_get(record, "stage"),
        "date_sgt": safe_get(record, "date_sgt"),
        "kickoff_sgt": safe_get(record, "kickoff_sgt"),
        "home_team": safe_get(record, "home_team"),
        "away_team": safe_get(record, "away_team"),
        "ht_score": safe_get(record, "ht_score"),
        "ft_score": safe_get(record, "ft_score"),
        "winner": safe_get(record, "winner"),
        "btts": safe_get(record, "btts", "Unknown"),
        "total_goals": safe_get(record, "total_goals"),
        "over_2_5": safe_get(record, "over_2_5", "Unknown"),
        "odd_even": safe_get(record, "odd_even", "Unknown"),
        "data_quality": safe_get(record, "data_quality", 1),
        "source_result": safe_get(record, "source_result"),
        "source_odds": safe_get(record, "source_odds"),
        "source_stats": safe_get(record, "source_stats"),
        "notes": safe_get(record, "notes"),
    }


def normalize_child_rows(record: Dict[str, Any], key: str, match_id: str) -> List[Dict[str, Any]]:
    rows = record.get(key, []) or []
    output: List[Dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        normalized.setdefault("match_id", match_id)
        output.append(normalized)
    return output


def import_records(input_dir: Path, output_dir: Path) -> None:
    records = load_json_files(input_dir)
    if not records:
        raise SystemExit(f"No JSON files found in {input_dir}")

    match_rows: List[Dict[str, Any]] = []
    odds_rows: List[Dict[str, Any]] = []
    prediction_rows: List[Dict[str, Any]] = []
    live_rows: List[Dict[str, Any]] = []

    for record in records:
        match_id = safe_get(record, "match_id")
        if not match_id:
            raise ValueError("Every record requires match_id")
        match_rows.append(normalize_match(record))
        odds_rows.extend(normalize_child_rows(record, "odds", match_id))
        prediction_rows.extend(normalize_child_rows(record, "spwin_predictions", match_id))
        live_rows.extend(normalize_child_rows(record, "live_snapshots", match_id))

    append_rows(output_dir / "matches.csv", MATCH_FIELDS, match_rows)
    append_rows(output_dir / "odds.csv", ODDS_FIELDS, odds_rows)
    append_rows(output_dir / "spwin_predictions.csv", PREDICTION_FIELDS, prediction_rows)
    append_rows(output_dir / "live_snapshots.csv", LIVE_FIELDS, live_rows)

    print(f"Imported {len(match_rows)} match record(s)")
    print(f"Imported {len(odds_rows)} odds record(s)")
    print(f"Imported {len(prediction_rows)} SPWIN prediction record(s)")
    print(f"Imported {len(live_rows)} live snapshot record(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import curated historical match JSON into SPWIN Atlas CSV files")
    parser.add_argument("--input", required=True, help="Directory containing source JSON files")
    parser.add_argument("--output", required=True, help="Output directory for SPWIN Atlas CSV files")
    args = parser.parse_args()

    import_records(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
