#!/usr/bin/env python3
"""Experiment A1: robustness audit for incomplete-data 1X2+AH signals.

Diagnostic only. Production SPWIN v2.6.1 is not modified.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import product
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

STEAM_THRESHOLDS = (-6.0, -8.0, -10.0, -12.0, -14.0)
AH_MIN_EXCLUSIVE = (-15.0, -12.0, -10.0, -8.0, -6.0, -4.0)
AH_MAX_INCLUSIVE = (0.0, 3.0, 5.0, 8.0)
ODDS_BANDS = (
    (1.20, 2.00),
    (1.25, 2.00),
    (1.30, 2.00),
    (1.35, 2.00),
    (1.20, 1.90),
    (1.30, 1.90),
)

BASE_RULE = {
    "steam_threshold": -8.0,
    "ah_min_exclusive": -8.0,
    "ah_max_inclusive": 5.0,
    "odds_min": 1.30,
    "odds_max": 2.00,
}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def flat_pnl(outcome: str, odds: float) -> float | None:
    if outcome == "Win":
        return round(odds - 1.0, 4)
    if outcome == "Loss":
        return -1.0
    if outcome == "Push":
        return 0.0
    return None


def max_drawdown_units(pnls: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    return round(max_drawdown, 4)


def make_pool(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    block_by_id: dict[str, int] = {}
    total = len(records)
    for index, record in enumerate(records):
        block_by_id[str(record.get("match_id", ""))] = min(4, index * 4 // total + 1)

    pool: list[dict[str, Any]] = []
    for record in records:
        rec = v261.make_recommendation(record)
        favourite_row = v260.closing_favourite(record)
        favourite = str(favourite_row.get("selection")) if favourite_row else None
        ah_row = v260.favourite_ah(record, favourite)
        audit = integrity.audit_decision(
            record,
            favourite,
            cpi=rec.cpi,
            consensus=rec.consensus_count,
            flags=rec.red_flags,
            stake_pct=rec.stake_pct,
            cpi_threshold=80.0,
        )
        if audit["decision_status"] != "PASS_INCOMPLETE_DATA":
            continue

        coverage = []
        if favourite_row:
            coverage.append("1X2")
        if ah_row:
            coverage.append("AH")
        if v260.markets(record, "HT_1X2"):
            coverage.append("HT")
        if v260.infer_first_goal(record, favourite):
            coverage.append("FG")

        if not audit["full_1x2"] or coverage != ["1X2", "AH"]:
            continue
        if rec.red_flags:
            continue

        outcome = integrity.settle(record, "1X2", favourite)
        odds = round(v260.odds(favourite_row), 3)
        pnl = flat_pnl(outcome, odds)
        if pnl is None:
            continue

        pool.append({
            "date": str(record.get("date", "")),
            "match_id": str(record.get("match_id", "")),
            "match": str(record.get("match", "")),
            "stage": str(record.get("stage", "")),
            "block": block_by_id[str(record.get("match_id", ""))],
            "favourite": favourite or "",
            "odds": odds,
            "one_x_two_move": round(v260.move(favourite_row), 2),
            "ah_move": round(v260.move(ah_row), 2),
            "cpi": rec.cpi,
            "outcome": outcome,
            "flat_pnl": pnl,
            "score_ft": record.get("score", {}).get(
                "ft", record.get("score", {}).get("ft_90", "")
            ),
        })

    return sorted(pool, key=lambda row: (row["date"], row["match_id"]))


def select_rows(pool: list[dict[str, Any]], config: dict[str, float]) -> list[dict[str, Any]]:
    return [
        row for row in pool
        if row["one_x_two_move"] <= config["steam_threshold"]
        and row["ah_move"] > config["ah_min_exclusive"]
        and row["ah_move"] <= config["ah_max_inclusive"]
        and row["odds"] >= config["odds_min"]
        and row["odds"] <= config["odds_max"]
    ]


def evaluate(selected: list[dict[str, Any]], config: dict[str, float]) -> dict[str, Any]:
    pnls = [float(row["flat_pnl"]) for row in selected]
    profit = round(sum(pnls), 4)
    wins = sum(row["outcome"] == "Win" for row in selected)
    losses = sum(row["outcome"] == "Loss" for row in selected)
    block_pnls = {
        block: round(sum(float(row["flat_pnl"]) for row in selected if row["block"] == block), 4)
        for block in range(1, 5)
    }
    block_bets = {
        block: sum(row["block"] == block for row in selected)
        for block in range(1, 5)
    }
    covered_blocks = sum(count > 0 for count in block_bets.values())
    positive_blocks = sum(block_bets[block] > 0 and block_pnls[block] > 0 for block in range(1, 5))

    winning_pnls = [pnl for pnl in pnls if pnl > 0]
    gross_wins = sum(winning_pnls)
    largest_win_share = max(winning_pnls) / gross_wins if gross_wins else 1.0

    passes_guardrails = (
        len(selected) >= 5
        and profit > 0
        and max_drawdown_units(pnls) <= 2.0
        and covered_blocks >= 2
        and positive_blocks >= 2
        and largest_win_share <= 0.60
    )

    selection_ids = "|".join(row["match_id"] for row in selected)
    return {
        **config,
        "bets": len(selected),
        "wins": wins,
        "losses": losses,
        "hit_rate_pct": round(wins / len(selected) * 100, 2) if selected else 0.0,
        "profit_units": profit,
        "roi_pct": round(profit / len(selected) * 100, 2) if selected else 0.0,
        "max_drawdown_units": max_drawdown_units(pnls),
        "covered_blocks": covered_blocks,
        "positive_blocks": positive_blocks,
        "block_1_bets": block_bets[1],
        "block_1_profit": block_pnls[1],
        "block_2_bets": block_bets[2],
        "block_2_profit": block_pnls[2],
        "block_3_bets": block_bets[3],
        "block_3_profit": block_pnls[3],
        "block_4_bets": block_bets[4],
        "block_4_profit": block_pnls[4],
        "largest_win_share_pct": round(largest_win_share * 100, 2),
        "passes_guardrails": passes_guardrails,
        "selection_ids": selection_ids,
        "matches": "|".join(row["match"] for row in selected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--out-dir", default="reports/analysis/spwin_v261_a1_robustness")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = v260.load_gold_records(Path(args.gold_dir))
    pool = make_pool(records)

    grid: list[dict[str, Any]] = []
    for steam, ah_min, ah_max, odds_band in product(
        STEAM_THRESHOLDS, AH_MIN_EXCLUSIVE, AH_MAX_INCLUSIVE, ODDS_BANDS
    ):
        if ah_min >= ah_max:
            continue
        config = {
            "steam_threshold": steam,
            "ah_min_exclusive": ah_min,
            "ah_max_inclusive": ah_max,
            "odds_min": odds_band[0],
            "odds_max": odds_band[1],
        }
        selected = select_rows(pool, config)
        if selected:
            grid.append(evaluate(selected, config))

    grid.sort(
        key=lambda row: (
            not bool(row["passes_guardrails"]),
            -int(row["bets"]),
            -float(row["roi_pct"]),
            float(row["max_drawdown_units"]),
        )
    )
    robust = [row for row in grid if row["passes_guardrails"]]

    base_selected = select_rows(pool, BASE_RULE)
    base_result = evaluate(base_selected, BASE_RULE)

    selection_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in grid:
        selection_groups[str(row["selection_ids"])].append(row)
    clusters = []
    for selection_ids, configs in selection_groups.items():
        representative = configs[0]
        clusters.append({
            "configuration_count": len(configs),
            "bets": representative["bets"],
            "wins": representative["wins"],
            "losses": representative["losses"],
            "profit_units": representative["profit_units"],
            "roi_pct": representative["roi_pct"],
            "covered_blocks": representative["covered_blocks"],
            "positive_blocks": representative["positive_blocks"],
            "selection_ids": selection_ids,
            "matches": representative["matches"],
        })
    clusters.sort(key=lambda row: (-row["configuration_count"], -row["bets"], -row["roi_pct"]))

    frequency: Counter[str] = Counter()
    robust_frequency: Counter[str] = Counter()
    for row in grid:
        for match_id in str(row["selection_ids"]).split("|"):
            if match_id:
                frequency[match_id] += 1
    for row in robust:
        for match_id in str(row["selection_ids"]).split("|"):
            if match_id:
                robust_frequency[match_id] += 1
    pool_by_id = {row["match_id"]: row for row in pool}
    match_frequency = [
        {
            **pool_by_id[match_id],
            "all_config_selections": count,
            "robust_config_selections": robust_frequency.get(match_id, 0),
        }
        for match_id, count in frequency.most_common()
    ]

    strict_family = [
        row for row in grid
        if row["steam_threshold"] == -10.0
        and row["ah_min_exclusive"] == -12.0
        and row["odds_max"] == 2.0
    ]
    wider_family = [
        row for row in grid
        if row["steam_threshold"] == -6.0
        and row["ah_min_exclusive"] == -12.0
        and row["odds_max"] == 2.0
    ]

    summary = {
        "engine": v261.ENGINE_VERSION,
        "production_changed": False,
        "active_gold_records": len(records),
        "eligible_incomplete_1x2_ah_no_flag_pool": len(pool),
        "configurations_tested": len(grid),
        "configurations_passing_guardrails": len(robust),
        "unique_selection_sets": len(clusters),
        "base_rule": base_result,
        "strict_family_configuration_count": len(strict_family),
        "strict_family_passing_count": sum(bool(row["passes_guardrails"]) for row in strict_family),
        "wider_family_configuration_count": len(wider_family),
        "wider_family_passing_count": sum(bool(row["passes_guardrails"]) for row in wider_family),
        "guardrails": {
            "minimum_bets": 5,
            "positive_overall_profit": True,
            "maximum_drawdown_units": 2.0,
            "minimum_covered_chronological_blocks": 2,
            "minimum_positive_chronological_blocks": 2,
            "maximum_largest_winner_share_pct": 60.0,
        },
        "interpretation_guardrail": (
            "Passing configurations are research hypotheses, not production approval. "
            "All thresholds were inspected on the same 82-match sample."
        ),
    }

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "eligible_pool.json").write_text(json.dumps(pool, indent=2), encoding="utf-8")
    (out_dir / "grid.json").write_text(json.dumps(grid, indent=2), encoding="utf-8")
    (out_dir / "robust_configurations.json").write_text(json.dumps(robust, indent=2), encoding="utf-8")
    (out_dir / "selection_clusters.json").write_text(json.dumps(clusters, indent=2), encoding="utf-8")
    (out_dir / "match_frequency.json").write_text(json.dumps(match_frequency, indent=2), encoding="utf-8")
    write_csv(out_dir / "eligible_pool.csv", pool)
    write_csv(out_dir / "grid.csv", grid)
    write_csv(out_dir / "robust_configurations.csv", robust)
    write_csv(out_dir / "selection_clusters.csv", clusters)
    write_csv(out_dir / "match_frequency.csv", match_frequency)
    write_csv(out_dir / "base_rule_matches.csv", base_selected)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
