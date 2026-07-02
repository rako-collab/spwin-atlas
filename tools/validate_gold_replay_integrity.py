#!/usr/bin/env python3
"""Validate SPWIN Gold replay settlement and market completeness."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spwin_engine import integrity, v260, v261


def validate(gold_dir: Path) -> dict[str, object]:
    records = v260.load_gold_records(gold_dir)
    raw_result_labels: Counter[str] = Counter()
    one_x_two_labels: Counter[str] = Counter()
    unresolved_1x2: list[dict[str, str]] = []
    data_statuses: Counter[str] = Counter()
    decision_statuses: Counter[str] = Counter()
    staked_bets: list[dict[str, str]] = []

    for record in records:
        for row in record.get("markets", []):
            label = str(row.get("result", "<missing>"))
            raw_result_labels[label] += 1
            if row.get("market_code") == "1X2":
                one_x_two_labels[label] += 1
                outcome = integrity.settle(record, "1X2", row.get("selection"))
                if outcome not in integrity.SETTLED_OUTCOMES:
                    unresolved_1x2.append({
                        "match_id": str(record.get("match_id", "")),
                        "selection": str(row.get("selection", "")),
                        "raw_result": label,
                    })

        rec = v261.make_recommendation(record)
        fav = v260.closing_favourite(record)
        audit = integrity.audit_decision(
            record,
            str(fav.get("selection")) if fav else None,
            cpi=rec.cpi,
            consensus=rec.consensus_count,
            flags=rec.red_flags,
            stake_pct=rec.stake_pct,
            cpi_threshold=80.0,
        )
        data_statuses[audit["data_status"]] += 1
        decision_statuses[audit["decision_status"]] += 1

        if rec.stake_pct > 0:
            outcome = integrity.require_settled(record, "1X2", rec.selection)
            staked_bets.append({
                "match_id": rec.match_id,
                "selection": rec.selection,
                "outcome": outcome,
            })

    return {
        "gold_records": len(records),
        "raw_result_labels": dict(sorted(raw_result_labels.items())),
        "one_x_two_result_labels": dict(sorted(one_x_two_labels.items())),
        "unresolved_1x2_rows": unresolved_1x2,
        "unresolved_1x2_count": len(unresolved_1x2),
        "data_status_counts": dict(data_statuses),
        "decision_status_counts": dict(decision_statuses),
        "staked_bets": staked_bets,
        "status": "PASS" if not unresolved_1x2 else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--out", default="reports/validation/gold_replay_integrity.json")
    args = parser.parse_args()

    result = validate(Path(args.gold_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
