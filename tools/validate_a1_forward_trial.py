#!/usr/bin/env python3
"""Validate the SPWIN v2.6.1-A1 forward-trial ledger."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
import argparse
import csv
import json

from spwin_engine import observation_labels

ALLOWED_A1_STATUS = {"BET", "PASS"}
ALLOWED_OUTCOMES = {"", "Win", "Loss", "Push", "Void"}
EXPECTED_A1_STAKE_PCT = 0.0025
MOVEMENT_TOLERANCE_PCT = 0.20


def _present(value: Any) -> bool:
    return str(value or "").strip() != ""


def _float(value: Any, field: str, row_number: int) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc


def _optional_float(value: Any, field: str, row_number: int) -> float | None:
    if not _present(value):
        return None
    return _float(value, field, row_number)


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


def _validate_move_consistency(
    row: dict[str, str],
    row_number: int,
    *,
    opening_field: str,
    final_field: str,
    move_field: str,
    errors: list[str],
) -> None:
    supplied = [_present(row.get(field)) for field in (opening_field, final_field, move_field)]
    if not any(supplied):
        return
    if not all(supplied):
        errors.append(
            f"row {row_number}: {opening_field}, {final_field}, and {move_field} "
            "must be supplied together"
        )
        return
    try:
        opening = _float(row.get(opening_field), opening_field, row_number)
        final = _float(row.get(final_field), final_field, row_number)
        recorded = _float(row.get(move_field), move_field, row_number)
        if opening <= 0 or final <= 0:
            errors.append(f"row {row_number}: odds must be greater than zero")
            return
        calculated = (final / opening - 1.0) * 100.0
        if abs(calculated - recorded) > MOVEMENT_TOLERANCE_PCT:
            errors.append(
                f"row {row_number}: {move_field}={recorded:.2f}% does not match "
                f"opening/final calculation {calculated:.2f}%"
            )
    except ValueError as exc:
        errors.append(str(exc))


def _validate_observation_labels(
    row: dict[str, str],
    row_number: int,
    errors: list[str],
    counts: dict[str, Counter[str]],
) -> None:
    actual_price = str(row.get("price_zone_label", "")).strip()
    actual_steam = str(row.get("controlled_steam_label", "")).strip()
    actual_draw = str(row.get("draw_structure_label", "")).strip()

    for field, value in (
        ("price_zone_label", actual_price),
        ("controlled_steam_label", actual_steam),
        ("draw_structure_label", actual_draw),
    ):
        if not value:
            errors.append(f"row {row_number}: {field} is required for every match")

    try:
        favourite_odds = _optional_float(
            row.get("one_x_two_final"), "one_x_two_final", row_number
        )
        one_x_two_move = _optional_float(
            row.get("one_x_two_move_pct"), "one_x_two_move_pct", row_number
        )
        ah_move = _optional_float(row.get("ah_move_pct"), "ah_move_pct", row_number)
        draw_move = _optional_float(
            row.get("draw_move_pct"), "draw_move_pct", row_number
        )
    except ValueError as exc:
        errors.append(str(exc))
        return

    expected = observation_labels.derive_from_values(
        favourite_odds=favourite_odds,
        one_x_two_move_pct=one_x_two_move,
        ah_move_pct=ah_move,
        draw_move_pct=draw_move,
    )

    comparisons = (
        ("price_zone_label", actual_price, expected.price_zone),
        ("controlled_steam_label", actual_steam, expected.controlled_steam),
        ("draw_structure_label", actual_draw, expected.draw_structure),
    )
    for field, actual, required in comparisons:
        if actual and actual != required:
            errors.append(
                f"row {row_number}: {field} must be {required!r} for the captured values, "
                f"not {actual!r}"
            )

    if actual_price and actual_price != observation_labels.PRICE_UNAVAILABLE and favourite_odds is None:
        errors.append(f"row {row_number}: a price-zone label requires one_x_two_final")
    if actual_steam and actual_steam != observation_labels.STEAM_UNAVAILABLE:
        if one_x_two_move is None and ah_move is None:
            errors.append(
                f"row {row_number}: a controlled-steam label requires 1X2 or AH movement"
            )
    if actual_draw and actual_draw != observation_labels.DRAW_UNAVAILABLE:
        for field in ("draw_opening", "draw_final", "draw_move_pct"):
            if not _present(row.get(field)):
                errors.append(
                    f"row {row_number}: {field} is required when draw structure is available"
                )

    if actual_price:
        counts["price_zone_label"][actual_price] += 1
    if actual_steam:
        counts["controlled_steam_label"][actual_steam] += 1
    if actual_draw:
        counts["draw_structure_label"][actual_draw] += 1


def validate_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    errors: list[str] = []
    seen_trial_ids: set[str] = set()
    seen_match_ids: set[str] = set()
    bets = passes = settled = 0
    observation_counts: dict[str, Counter[str]] = {
        "price_zone_label": Counter(),
        "controlled_steam_label": Counter(),
        "draw_structure_label": Counter(),
    }

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

        _validate_move_consistency(
            row,
            row_number,
            opening_field="one_x_two_opening",
            final_field="one_x_two_final",
            move_field="one_x_two_move_pct",
            errors=errors,
        )
        _validate_move_consistency(
            row,
            row_number,
            opening_field="ah_opening",
            final_field="ah_final",
            move_field="ah_move_pct",
            errors=errors,
        )
        _validate_move_consistency(
            row,
            row_number,
            opening_field="draw_opening",
            final_field="draw_final",
            move_field="draw_move_pct",
            errors=errors,
        )
        _validate_observation_labels(row, row_number, errors, observation_counts)

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
        "observation_label_counts": {
            field: dict(counter) for field, counter in observation_counts.items()
        },
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
