#!/usr/bin/env python3
"""Validate timestamped Gold market snapshots and correction activation.

The validator is backward compatible with legacy Gold records. Strict snapshot
checks are enabled only when a record declares ``snapshot_integrity_required``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import json
import sys


COVERAGE_TO_CODES = {
    "full_time_1x2": {"1X2"},
    "asian_handicap": {"AH"},
    "handicap_alt": {"HANDICAP_ALT"},
    "half_time_ah": {"HT_AH"},
    "half_time_1x2": {"HT_1X2"},
    "first_goal": {"FG"},
    "over_under": {"OU"},
    "btts": {"BTTS"},
}

REQUIRED_SNAPSHOT_FIELDS = {
    "source_last_updated_at",
    "captured_at",
    "scheduled_kickoff_at",
    "minutes_before_kickoff",
    "snapshot_role",
    "forward_lock_status",
    "odds_basis",
    "is_true_closing_odds",
}


def _parse_iso(value: Any, field: str, errors: list[str], match_id: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors.append(f"{match_id}: invalid ISO datetime for {field}: {value!r}")
        return None


def _movement(opening: float, current: float) -> float:
    return (current - opening) / opening * 100.0


def _validate_record(record: dict[str, Any], filename: str) -> list[str]:
    errors: list[str] = []
    match_id = str(record.get("match_id", filename))
    markets = record.get("markets", [])
    if not isinstance(markets, list):
        return [f"{match_id}: markets must be a list"]

    codes = {str(row.get("market_code", "")) for row in markets if isinstance(row, dict)}

    for index, row in enumerate(markets):
        if not isinstance(row, dict):
            errors.append(f"{match_id}: market row {index} is not an object")
            continue
        opening = row.get("opening_odds")
        current = row.get("closing_odds")
        stored = row.get("movement_pct")
        if opening is None or current is None or stored is None:
            continue
        try:
            opening_f = float(opening)
            current_f = float(current)
            stored_f = float(stored)
        except (TypeError, ValueError):
            errors.append(f"{match_id}: non-numeric odds or movement in market row {index}")
            continue
        if opening_f <= 0:
            errors.append(f"{match_id}: opening odds must be positive in market row {index}")
            continue
        expected = round(_movement(opening_f, current_f), 1)
        if abs(expected - stored_f) > 0.2:
            errors.append(
                f"{match_id}: movement mismatch for {row.get('market_code')} "
                f"{row.get('selection')}: stored={stored_f}, expected={expected}"
            )

    if not record.get("snapshot_integrity_required"):
        return errors

    snapshot = record.get("market_snapshot")
    if not isinstance(snapshot, dict):
        errors.append(f"{match_id}: market_snapshot is required")
        return errors

    missing_snapshot = sorted(REQUIRED_SNAPSHOT_FIELDS - set(snapshot))
    if missing_snapshot:
        errors.append(f"{match_id}: missing market_snapshot fields: {', '.join(missing_snapshot)}")

    source_at = _parse_iso(snapshot.get("source_last_updated_at"), "source_last_updated_at", errors, match_id)
    captured_at = _parse_iso(snapshot.get("captured_at"), "captured_at", errors, match_id)
    kickoff_at = _parse_iso(snapshot.get("scheduled_kickoff_at"), "scheduled_kickoff_at", errors, match_id)

    if source_at and kickoff_at:
        calculated = round((kickoff_at - source_at).total_seconds() / 60)
        try:
            stored_minutes = int(snapshot.get("minutes_before_kickoff"))
            if abs(calculated - stored_minutes) > 1:
                errors.append(
                    f"{match_id}: minutes_before_kickoff={stored_minutes}, calculated={calculated}"
                )
        except (TypeError, ValueError):
            errors.append(f"{match_id}: minutes_before_kickoff must be an integer")

    if captured_at and source_at and captured_at < source_at:
        errors.append(f"{match_id}: captured_at cannot precede source_last_updated_at")

    coverage = record.get("source_market_coverage")
    if not isinstance(coverage, dict):
        errors.append(f"{match_id}: source_market_coverage is required")
    else:
        valid_statuses = {"FULL", "PARTIAL", "MISSING"}
        for name, expected_codes in COVERAGE_TO_CODES.items():
            status = str(coverage.get(name, "MISSING")).upper()
            if status not in valid_statuses:
                errors.append(f"{match_id}: invalid coverage status {name}={status!r}")
                continue
            if status != "MISSING" and not (codes & expected_codes):
                errors.append(
                    f"{match_id}: coverage says {name}={status} but no rows exist for "
                    f"{sorted(expected_codes)}"
                )

    one_x_two = [row for row in markets if row.get("market_code") == "1X2"]
    if str((coverage or {}).get("full_time_1x2", "")).upper() == "FULL":
        selections = {str(row.get("selection", "")).casefold() for row in one_x_two}
        if len(one_x_two) < 3 or "draw" not in selections:
            errors.append(f"{match_id}: FULL 1X2 coverage requires home/draw/away rows")

    if snapshot.get("forward_lock_status") == "LOCKED":
        try:
            minutes = int(snapshot.get("minutes_before_kickoff"))
            if not 15 <= minutes <= 30:
                errors.append(f"{match_id}: LOCKED snapshot must be T-30 to T-15, got T-{minutes}")
        except (TypeError, ValueError):
            pass

    return errors


def validate(gold_dir: Path) -> dict[str, Any]:
    index_path = gold_dir / "MATCH_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entries = index.get("records", [])
    active_by_match = {str(entry.get("match_id")): str(entry.get("file")) for entry in entries}

    errors: list[str] = []
    validated_records = 0
    strict_records = 0

    for entry in entries:
        filename = str(entry.get("file", ""))
        path = gold_dir / filename
        if not path.exists():
            errors.append(f"MATCH_INDEX: missing active file {filename}")
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        validated_records += 1
        strict_records += bool(record.get("snapshot_integrity_required"))
        errors.extend(_validate_record(record, filename))

    for path in sorted(gold_dir.glob("*_correction.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        match_id = str(record.get("match_id", ""))
        correction_of = str(record.get("correction_of", ""))
        if not match_id or not correction_of:
            continue
        active_file = active_by_match.get(match_id)
        if active_file == correction_of:
            errors.append(
                f"MATCH_INDEX: {match_id} still points to superseded {correction_of}; "
                f"activate {path.name}"
            )

    result = {
        "gold_records": len(entries),
        "validated_records": validated_records,
        "strict_snapshot_records": strict_records,
        "errors": errors,
        "error_count": len(errors),
        "status": "PASS" if not errors else "FAIL",
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--out", default="reports/validation/gold_snapshot_integrity.json")
    args = parser.parse_args()

    result = validate(Path(args.gold_dir))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
