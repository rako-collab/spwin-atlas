#!/usr/bin/env python3
"""
SPWIN Capital Preservation Validator v0.1

Fails CI if a backtest violates the absolute Capital Preservation rule.

Current checks:
- backtest summary exists
- ROI is present
- if allow-negative-roi is false, ROI must be >= 0
- total staked units must be present
- total bets must be present

Future checks:
- max drawdown threshold
- longest losing streak threshold
- grade-specific ROI gates
- PASS effectiveness gate
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def load_summary(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Missing backtest summary: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["metric"]: row["value"] for row in rows}


def as_float(summary: dict, metric: str) -> float:
    value = summary.get(metric, "")
    if value == "":
        raise SystemExit(f"Missing required metric: {metric}")
    try:
        return float(value)
    except ValueError as exc:
        raise SystemExit(f"Metric {metric} is not numeric: {value}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate SPWIN capital preservation gate")
    parser.add_argument("--summary", required=True, help="Path to backtest_summary.csv")
    parser.add_argument("--allow-negative-roi", default="false", choices=["true", "false"])
    args = parser.parse_args()

    summary = load_summary(Path(args.summary))

    total_bets = as_float(summary, "total_bets")
    total_staked = as_float(summary, "total_staked_units")
    roi = as_float(summary, "roi_pct")

    if total_bets <= 0:
        raise SystemExit("Capital Preservation Gate FAILED: no bets were evaluated")

    if total_staked <= 0:
        raise SystemExit("Capital Preservation Gate FAILED: total_staked_units must be greater than zero")

    if args.allow_negative_roi == "false" and roi < 0:
        raise SystemExit(
            f"Capital Preservation Gate FAILED: ROI is negative ({roi}%). "
            "Engine cannot be promoted or accepted."
        )

    print("Capital Preservation Gate PASSED")
    print(f"total_bets={total_bets}")
    print(f"total_staked_units={total_staked}")
    print(f"roi_pct={roi}")


if __name__ == "__main__":
    main()
