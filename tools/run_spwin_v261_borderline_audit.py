#!/usr/bin/env python3
"""Run the authoritative SPWIN v2.6.1 replay and Borderline Audit.

The Gold directory preserves immutable superseded records. The shared Gold
loader follows MATCH_INDEX.json so each active match is loaded exactly once.
"""

from __future__ import annotations

from collections import Counter
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


def raw_gold_file_count(gold_dir: Path) -> int:
    count = 0
    for path in gold_dir.glob("*.json"):
        if path.name == "MATCH_INDEX.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("quality_grade") == "Gold" and record.get("status") == "COMPLETED":
            count += 1
    return count


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_audit(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for record in records:
        recommendation = v261.make_recommendation(record)
        favourite_row = v260.closing_favourite(record)
        favourite = str(favourite_row.get("selection")) if favourite_row else None
        audit = integrity.audit_decision(
            record,
            favourite,
            cpi=recommendation.cpi,
            consensus=recommendation.consensus_count,
            flags=recommendation.red_flags,
            stake_pct=recommendation.stake_pct,
            cpi_threshold=80.0,
        )
        favourite_outcome = (
            integrity.settle(record, "1X2", favourite) if favourite else "Unknown"
        )

        row = {
            "date": recommendation.date,
            "match_id": recommendation.match_id,
            "match": recommendation.match,
            "stage": recommendation.stage,
            "file": record.get("_file", ""),
            "favourite": favourite or "",
            "favourite_odds": round(v260.odds(favourite_row), 3) if favourite_row else 0.0,
            "favourite_outcome": favourite_outcome,
            "cpi": recommendation.cpi,
            "consensus": recommendation.consensus_count,
            "red_flags": "|".join(recommendation.red_flags),
            "data_status": audit["data_status"],
            "available_consensus_channels": audit["available_consensus_channels"],
            "missing_channels": "|".join(audit["missing_channels"]),
            "decision_status": audit["decision_status"],
            "decision_reasons": "|".join(audit["decision_reasons"]),
            "pick": recommendation.selection,
            "stake_pct": recommendation.stake_pct,
            "score_ft": record.get("score", {}).get(
                "ft", record.get("score", {}).get("ft_90", "")
            ),
        }
        rows.append(row)

        if (
            audit["data_status"] == "COMPLETE"
            and audit["decision_status"] in {"PASS_MODEL", "PASS_RED_FLAG"}
            and 70.0 <= recommendation.cpi <= 85.0
        ):
            candidates.append(row)

    rows.sort(key=lambda item: (-float(item["cpi"]), item["date"], item["match_id"]))
    candidates.sort(key=lambda item: (-float(item["cpi"]), item["date"], item["match_id"]))
    return rows, candidates


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/analysis/spwin_v261_borderline_82")
    args = parser.parse_args()

    gold_dir = Path(args.gold_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index_path = gold_dir / "MATCH_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    records = v260.load_gold_records(gold_dir)
    replay = v261.replay(records, starting_bankroll=args.bankroll)
    rows, candidates = build_audit(records)

    raw_count = raw_gold_file_count(gold_dir)
    decision_counts = Counter(row["decision_status"] for row in rows)
    data_counts = Counter(row["data_status"] for row in rows)
    candidate_outcomes = Counter(row["favourite_outcome"] for row in candidates)

    summary = {
        "engine_version": replay["engine_version"],
        "index_total_records": index.get("total_records"),
        "indexed_records_loaded": len(records),
        "raw_completed_gold_files": raw_count,
        "superseded_files_excluded": raw_count - len(records),
        "starting_bankroll": replay["starting_bankroll"],
        "final_bankroll": replay["final_bankroll"],
        "net_profit": replay["net_profit"],
        "roi_pct": replay["roi_pct"],
        "bets": replay["bets"],
        "wins": replay["wins"],
        "losses": replay["losses"],
        "pushes": replay["pushes"],
        "passes": replay["passes"],
        "max_drawdown_pct": replay["max_drawdown_pct"],
        "decision_status_counts": dict(decision_counts),
        "data_status_counts": dict(data_counts),
        "borderline_candidate_count": len(candidates),
        "borderline_favourite_outcomes": dict(candidate_outcomes),
        "borderline_rule": (
            "COMPLETE data; PASS_MODEL or PASS_RED_FLAG; CPI from 70 through 85"
        ),
    }

    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (out_dir / "all_matches.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )
    (out_dir / "borderline_candidates.json").write_text(
        json.dumps(candidates, indent=2), encoding="utf-8"
    )
    write_csv(out_dir / "all_matches.csv", rows)
    write_csv(out_dir / "borderline_candidates.csv", candidates)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
