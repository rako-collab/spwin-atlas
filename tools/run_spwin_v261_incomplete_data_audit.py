#!/usr/bin/env python3
"""Audit SPWIN v2.6.1 incomplete-data PASS decisions.

This is a diagnostic tool only. It does not alter production recommendations.
It separates missing market channels from present-but-unaligned signals and
measures each sparse coverage/signature group against the stored result.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import argparse
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spwin_engine import integrity, v260, v261


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def signal_state(record: dict[str, Any]) -> dict[str, Any]:
    favourite_row = v260.closing_favourite(record)
    favourite = str(favourite_row.get("selection")) if favourite_row else None
    ah_row = v260.favourite_ah(record, favourite)
    ht_row = v260.infer_ht(record)
    fg_row = v260.infer_first_goal(record, favourite)

    one_x_two_available = favourite_row is not None
    ah_available = ah_row is not None
    ht_available = bool(v260.markets(record, "HT_1X2"))
    fg_available = fg_row is not None

    one_x_two_aligned = bool(favourite_row and v260.move(favourite_row) <= -8)
    ah_aligned = bool(ah_row and v260.move(ah_row) <= -8)
    ht_aligned = bool(
        ht_row
        and favourite
        and favourite in str(ht_row.get("selection", ""))
        and v260.move(ht_row) <= -5
    )
    fg_aligned = bool(fg_row and v260.move(fg_row) <= -4)

    channels = {
        "1X2": one_x_two_available,
        "AH": ah_available,
        "HT": ht_available,
        "FG": fg_available,
    }
    alignments = {
        "1X2": one_x_two_aligned,
        "AH": ah_aligned,
        "HT": ht_aligned,
        "FG": fg_aligned,
    }
    available_names = [name for name, present in channels.items() if present]
    aligned_names = [name for name, aligned in alignments.items() if aligned]

    return {
        "favourite_row": favourite_row,
        "favourite": favourite,
        "ah_row": ah_row,
        "ht_row": ht_row,
        "fg_row": fg_row,
        "coverage_signature": "+".join(available_names) if available_names else "NONE",
        "alignment_signature": "+".join(aligned_names) if aligned_names else "NONE",
        "available_count": len(available_names),
        "aligned_count": len(aligned_names),
    }


def result_pnl(outcome: str, odds: float) -> float | None:
    if outcome == "Win":
        return round(odds - 1.0, 4)
    if outcome == "Loss":
        return -1.0
    if outcome == "Push":
        return 0.0
    return None


def group_summary(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)

    output: list[dict[str, Any]] = []
    for values, members in groups.items():
        settled = [member for member in members if member["flat_pnl"] is not None]
        wins = sum(member["favourite_outcome"] == "Win" for member in settled)
        losses = sum(member["favourite_outcome"] == "Loss" for member in settled)
        pnl = sum(float(member["flat_pnl"]) for member in settled)
        item = {key: value for key, value in zip(keys, values)}
        item.update({
            "matches": len(members),
            "settled": len(settled),
            "wins": wins,
            "losses": losses,
            "hit_rate_pct": round(wins / len(settled) * 100, 2) if settled else 0.0,
            "flat_profit_units": round(pnl, 4),
            "flat_roi_pct": round(pnl / len(settled) * 100, 2) if settled else 0.0,
            "average_odds": round(
                sum(float(member["favourite_odds"]) for member in settled) / len(settled), 4
            ) if settled else 0.0,
            "average_cpi": round(
                sum(float(member["cpi"]) for member in members) / len(members), 2
            ),
        })
        output.append(item)

    return sorted(output, key=lambda item: tuple(str(item[key]) for key in keys))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--out-dir", default="reports/analysis/spwin_v261_incomplete_data")
    args = parser.parse_args()

    gold_dir = Path(args.gold_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = v260.load_gold_records(gold_dir)
    rows: list[dict[str, Any]] = []

    for record in records:
        recommendation = v261.make_recommendation(record)
        state = signal_state(record)
        favourite = state["favourite"]
        audit = integrity.audit_decision(
            record,
            favourite,
            cpi=recommendation.cpi,
            consensus=recommendation.consensus_count,
            flags=recommendation.red_flags,
            stake_pct=recommendation.stake_pct,
            cpi_threshold=80.0,
        )
        if audit["decision_status"] != "PASS_INCOMPLETE_DATA":
            continue

        favourite_odds = round(v260.odds(state["favourite_row"]), 3) if state["favourite_row"] else 0.0
        outcome = integrity.settle(record, "1X2", favourite) if favourite else "Unknown"
        pnl = result_pnl(outcome, favourite_odds)

        rows.append({
            "date": record.get("date", ""),
            "match_id": record.get("match_id", ""),
            "match": record.get("match", ""),
            "stage": record.get("stage", ""),
            "file": record.get("_file", ""),
            "favourite": favourite or "",
            "favourite_odds": favourite_odds,
            "favourite_outcome": outcome,
            "flat_pnl": pnl,
            "cpi": recommendation.cpi,
            "red_flags": "|".join(recommendation.red_flags),
            "full_1x2": audit["full_1x2"],
            "coverage_signature": state["coverage_signature"],
            "alignment_signature": state["alignment_signature"],
            "available_count": state["available_count"],
            "aligned_count": state["aligned_count"],
            "one_x_two_move": round(v260.move(state["favourite_row"]), 2) if state["favourite_row"] else None,
            "ah_move": round(v260.move(state["ah_row"]), 2) if state["ah_row"] else None,
            "ht_selection": state["ht_row"].get("selection") if state["ht_row"] else "",
            "ht_move": round(v260.move(state["ht_row"]), 2) if state["ht_row"] else None,
            "fg_move": round(v260.move(state["fg_row"]), 2) if state["fg_row"] else None,
            "missing_channels": "|".join(audit["missing_channels"]),
            "score_ft": record.get("score", {}).get("ft", record.get("score", {}).get("ft_90", "")),
        })

    rows.sort(key=lambda item: (item["date"], item["match_id"]))
    by_coverage = group_summary(rows, ("full_1x2", "coverage_signature"))
    by_signature = group_summary(rows, ("full_1x2", "coverage_signature", "alignment_signature"))
    by_counts = group_summary(rows, ("available_count", "aligned_count"))

    usable_two_channel = [
        row for row in rows
        if row["full_1x2"]
        and row["coverage_signature"] == "1X2+AH"
        and row["favourite_outcome"] in {"Win", "Loss"}
    ]
    two_channel_signatures = group_summary(usable_two_channel, ("alignment_signature",))

    summary = {
        "engine": v261.ENGINE_VERSION,
        "active_gold_records": len(records),
        "incomplete_data_passes": len(rows),
        "one_channel_or_less": sum(row["available_count"] <= 1 for row in rows),
        "two_channel": sum(row["available_count"] == 2 for row in rows),
        "three_channel": sum(row["available_count"] == 3 for row in rows),
        "full_1x2_incomplete_passes": sum(bool(row["full_1x2"]) for row in rows),
        "partial_1x2_incomplete_passes": sum(not bool(row["full_1x2"]) for row in rows),
        "usable_full_1x2_plus_ah": len(usable_two_channel),
        "conclusion_guardrail": (
            "Do not promote an incomplete-data rule from this audit alone. "
            "Use it to define isolated hypotheses for blocked validation."
        ),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "incomplete_matches.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (out_dir / "by_coverage.json").write_text(json.dumps(by_coverage, indent=2), encoding="utf-8")
    (out_dir / "by_signal_signature.json").write_text(json.dumps(by_signature, indent=2), encoding="utf-8")
    (out_dir / "by_channel_counts.json").write_text(json.dumps(by_counts, indent=2), encoding="utf-8")
    (out_dir / "two_channel_1x2_ah_signatures.json").write_text(json.dumps(two_channel_signatures, indent=2), encoding="utf-8")

    write_csv(out_dir / "incomplete_matches.csv", rows)
    write_csv(out_dir / "by_coverage.csv", by_coverage)
    write_csv(out_dir / "by_signal_signature.csv", by_signature)
    write_csv(out_dir / "by_channel_counts.csv", by_counts)
    write_csv(out_dir / "two_channel_1x2_ah_signatures.csv", two_channel_signatures)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
