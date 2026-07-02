#!/usr/bin/env python3
"""Validate the SPWIN v2.6.1-A1 forward-trial ledger."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import csv
import json

ALLOWED_A1_STATUS = {"BET", "PASS"}
ALLOWED_OUTCOMES = {"", "Win", "Loss", "Push", "Void"}
EXPECTED_A1_STAKE_PCT = 0.0025


def _present(value: Any) -> bool:
    return str(value or "").strip() != ""


def _float(value: Any, field: str, row_number: int) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc


def _timestamp(value: Any, field: str, row_number: int) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"row {row_number}: {field} is required")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(
            f"row {row_number}: {field} must be ISO-8601, preferably with +08:00"
        ) from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"row {row_number}: {field} must include a timezone offset")
    return parsed


def validate_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    seen_trial_ids: set[str] = set()
    seen_match_ids: set[str] = set()
    bets = passes = settled = 0

    for row_number, row in enumerate(rows, start=2):
        trial_id = str(row.get("trial_id", "")).strip()
        match_id = str(row.get("match_id", "")).strip()
        match = str(row.get("match", "")).strip()
        a1_status = str(row.get("a1_status", "")).strip()
        locked = str(row.get("locked", "")).strip().upper()
        outcome = str(row.get("outcome", "")).strip()

        if not trial_id:
            errors.append(f"row {row_number}: trial_id is required")
        elif trial_id in seen_trial_ids:
            errors.append(f"row {row_number}: duplicate trial_id {trial_id!r}")
        else:
            seen_trial_ids.add(trial_id)

        if not match_id:
            errors.append(f"row {row_number}: match_id is required")
        elif match_id in seen_match_ids:
            errors.append(f"row {row_number}: duplicate match_id {match_id!r}")
        else:
            seen_match_ids.add(match_id)

        if not match:
            errors.append(f"row {row_number}: match is required")

        if a1_status not in ALLOWED_A1_STATUS:
            errors.append(f"row {row_number}: a1_status must be BET or PASS")
            continue

        if locked != "TRUE":
            errors.append(f"row {row_number}: every recorded decision must be locked=TRUE")
        else:
            try:
                kickoff = _timestamp(row.get("kickoff_sgt"), "kickoff_sgt", row_number)
                snapshot = _timestamp(row.get("snapshot_time_sgt"), "snapshot_time_sgt", row_number)
                locked_time = _timestamp(row.get("locked_time_sgt"), "locked_time_sgt", row_number)
                if snapshot >= kickoff:
                    errors.append(f"row {row_number}: snapshot must be before kickoff")
                if locked_time >= kickoff:
                    errors.append(f"row {row_number}: decision must be locked before kickoff")
            except ValueError as exc:
                errors.append(str(exc))

        if not _present(row.get("data_source")):
            errors.append(f"row {row_number}: data_source is required")
        if not _present(row.get("decision_reasons")):
            errors.append(f"row {row_number}: decision_reasons is required")

        if a1_status == "BET":
            bets += 1
            required = [
                "a1_selection",
                "a1_odds",
                "a1_stake_pct",
                "bankroll_before",
                "stake_amount",
                "one_x_two_opening",
                "one_x_two_final",
                "one_x_two_move_pct",
                "ah_opening",
                "ah_final",
                "ah_move_pct",
            ]
            for field in required:
                if not _present(row.get(field)):
                    errors.append(f"row {row_number}: {field} is required for an A1 BET")

            if str(row.get("coverage_signature", "")).strip() != "1X2+AH":
                errors.append(f"row {row_number}: A1 BET coverage_signature must be 1X2+AH")
            if _present(row.get("red_flags")):
                errors.append(f"row {row_number}: A1 BET cannot contain red_flags")

            try:
                stake_pct = _float(row.get("a1_stake_pct"), "a1_stake_pct", row_number)
                if abs(stake_pct - EXPECTED_A1_STAKE_PCT) > 1e-9:
                    errors.append(
                        f"row {row_number}: a1_stake_pct must be {EXPECTED_A1_STAKE_PCT}"
                    )
                odds = _float(row.get("a1_odds"), "a1_odds", row_number)
                one_x_two_move = _float(
                    row.get("one_x_two_move_pct"), "one_x_two_move_pct", row_number
                )
                ah_move = _float(row.get("ah_move_pct"), "ah_move_pct", row_number)
                if not 1.20 <= odds <= 2.00:
                    errors.append(f"row {row_number}: A1 odds must be within 1.20-2.00")
                if one_x_two_move > -6.0:
                    errors.append(f"row {row_number}: 1X2 movement must be <= -6%")
                if not (-12.0 < ah_move <= 5.0):
                    errors.append(f"row {row_number}: AH movement must be > -12% and <= +5%")
            except ValueError as exc:
                errors.append(str(exc))
        else:
            passes += 1
            if _present(row.get("stake_amount")) and str(row.get("stake_amount", "")).strip() not in {"0", "0.0", "0.00"}:
                errors.append(f"row {row_number}: A1 PASS stake_amount must be blank or zero")

        if outcome not in ALLOWED_OUTCOMES:
            errors.append(f"row {row_number}: unsupported outcome {outcome!r}")
        if outcome:
            settled += 1
            for field in ("final_score", "pnl", "bankroll_after", "settled_time_sgt"):
                if not _present(row.get(field)):
                    errors.append(f"row {row_number}: {field} is required after settlement")
            if _present(row.get("settled_time_sgt")):
                try:
                    settled_time = _timestamp(
                        row.get("settled_time_sgt"), "settled_time_sgt", row_number
                    )
                    kickoff = _timestamp(row.get("kickoff_sgt"), "kickoff_sgt", row_number)
                    if settled_time <= kickoff:
                        errors.append(f"row {row_number}: settlement must be after kickoff")
                except ValueError as exc:
                    errors.append(str(exc))

    return {
        "status": "PASS" if not errors else "FAIL",
        "rows": len(rows),
        "bets": bets,
        "passes": passes,
        "settled": settled,
        "errors": errors,
    }


def validate_ledger(path: Path) -> dict[str, Any]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return validate_rows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        default="data/world_cup_2026/a1_forward_trial/A1_TRIAL_LEDGER.csv",
    )
    args = parser.parse_args()

    result = validate_ledger(Path(args.ledger))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
