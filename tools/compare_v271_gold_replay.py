#!/usr/bin/env python3
"""Compare production, v2.7, and v2.7.1 chronological Gold replay summaries."""

from __future__ import annotations

from pathlib import Path
import argparse
import json


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def compact(summary: dict) -> dict:
    keys = (
        "engine_version",
        "research_only",
        "production_engine_unchanged",
        "chronological_order",
        "records",
        "bets",
        "passes",
        "wins",
        "losses",
        "pushes",
        "hit_rate_pct",
        "starting_bankroll",
        "final_bankroll",
        "net_profit",
        "roi_pct",
        "max_drawdown_pct",
        "knockout_guard_trigger_count",
        "knockout_guard_redirect_count",
        "knockout_guard_pass_count",
        "decision_status_counts",
    )
    return {key: summary[key] for key in keys if key in summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v261", required=True)
    parser.add_argument("--v270", required=True)
    parser.add_argument("--v271", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    v261 = load(Path(args.v261))
    v270 = load(Path(args.v270))
    v271 = load(Path(args.v271))

    record_counts = {v261.get("records"), v270.get("records"), v271.get("records")}
    if len(record_counts) != 1:
        raise ValueError(f"Replay record counts differ: {sorted(record_counts)}")

    comparison = {
        "comparison": "SPWIN chronological Gold replay",
        "authoritative_record_count": v271.get("records"),
        "production_unchanged": True,
        "engines": {
            "v2.6.1_production": compact(v261),
            "v2.7_research_correctness": compact(v270),
            "v2.7.1_research_knockout_guard": compact(v271),
        },
        "delta_v271_vs_v270": {
            "bets": v271.get("bets", 0) - v270.get("bets", 0),
            "wins": v271.get("wins", 0) - v270.get("wins", 0),
            "losses": v271.get("losses", 0) - v270.get("losses", 0),
            "net_profit": round(
                v271.get("net_profit", 0.0) - v270.get("net_profit", 0.0), 2
            ),
            "max_drawdown_pct": round(
                v271.get("max_drawdown_pct", 0.0)
                - v270.get("max_drawdown_pct", 0.0),
                2,
            ),
        },
        "promotion_status": "RESEARCH_ONLY_NOT_APPROVED_FOR_LIVE_USE",
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print(json.dumps(comparison, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
