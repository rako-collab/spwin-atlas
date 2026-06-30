#!/usr/bin/env python3
"""
SPWIN v2.5 Baseline Backtest Engine v0.1

Replays historical matches using SPWIN Atlas data.

Current scope:
- World Cup 2026
- 1X2 closing-odds baseline only
- Singapore Pools/SGOdds market data already stored in data/world_cup_2026/odds.csv

The full all-market backtest will be added after Asian Handicap, O/U, and BTTS
historical markets are fully enriched.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[2]


def read_csv(path: Path) -> List[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: List[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def odds_band(odds: float) -> str:
    if odds <= 1.20:
        return "heavy_1.01_1.20"
    if odds <= 1.50:
        return "strong_1.21_1.50"
    if odds <= 2.00:
        return "medium_1.51_2.00"
    return "light_2.01_plus"


def grade_from_pick(odds: float, stage: str) -> Tuple[str, str]:
    """Baseline v2.5 1X2 grading rules.

    These are intentionally conservative until full AH/O-U/BTTS markets are loaded.
    """
    band = odds_band(odds)
    if stage == "Round of 32" and odds <= 1.25:
        return "PASS", "Knockout short favourite risk filter"
    if odds <= 1.20:
        return "B", "Heavy favourite but price compressed"
    if odds <= 1.50:
        return "A", "Strong favourite with acceptable price"
    if odds <= 2.00:
        return "B", "Medium favourite; moderate volatility"
    return "PASS", "Light favourite or coin-flip profile"


def stake_for_grade(grade: str) -> float:
    return {
        "S": 5.0,
        "A+": 3.0,
        "A": 2.0,
        "B": 1.0,
        "C": 0.5,
        "PASS": 0.0,
    }.get(grade, 0.0)


def closing_1x2_by_match(odds_rows: List[dict]) -> Dict[str, Dict[str, float]]:
    by_match: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in odds_rows:
        if row.get("market") != "1X2":
            continue
        try:
            closing = float(row.get("closing_odds") or "")
        except ValueError:
            continue
        by_match[row["match_id"]][row["selection"]] = closing
    return by_match


def favourite_from_odds(match: dict, match_odds: Dict[str, float]) -> Tuple[str, float]:
    candidates = [(team, odds) for team, odds in match_odds.items() if team.lower() != "draw"]
    if not candidates:
        return "", 0.0
    return min(candidates, key=lambda item: item[1])


def settle_1x2(selection: str, winner: str, odds: float, stake: float) -> Tuple[str, float]:
    if stake == 0:
        return "PASS", 0.0
    if winner == selection:
        return "Win", round(stake * (odds - 1), 4)
    return "Loss", -stake


def run_backtest(competition: str, engine: str, markets: str) -> None:
    if competition != "world_cup_2026":
        raise SystemExit("Only world_cup_2026 is supported in v0.1")
    if markets.lower() != "1x2":
        raise SystemExit("Only --markets 1x2 is supported in v0.1")

    data_dir = ROOT / "data" / "world_cup_2026"
    output_dir = ROOT / "backtests" / "world_cup_2026" / "v2_5_baseline_2026_1"

    matches = read_csv(data_dir / "matches.csv")
    odds_rows = read_csv(data_dir / "odds.csv")
    odds_by_match = closing_1x2_by_match(odds_rows)

    result_rows: List[dict] = []
    for match in matches:
        match_id = match["match_id"]
        match_odds = odds_by_match.get(match_id, {})
        fav, fav_odds = favourite_from_odds(match, match_odds)
        if not fav:
            continue
        grade, pass_reason = grade_from_pick(fav_odds, match.get("stage", ""))
        stake = stake_for_grade(grade)
        settlement, profit_loss = settle_1x2(fav, match.get("winner", ""), fav_odds, stake)
        result_rows.append({
            "match_id": match_id,
            "stage": match.get("stage", ""),
            "home_team": match.get("home_team", ""),
            "away_team": match.get("away_team", ""),
            "market": "01 1X2",
            "selection": fav if grade != "PASS" else "PASS",
            "closing_odds": fav_odds,
            "odds_band": odds_band(fav_odds),
            "grade": grade,
            "stake_units": stake,
            "winner": match.get("winner", ""),
            "ft_score": match.get("ft_score", ""),
            "settlement": settlement,
            "profit_loss_units": profit_loss,
            "pass_reason": pass_reason if grade == "PASS" else "",
        })

    write_csv(output_dir / "backtest_match_results.csv", [
        "match_id", "stage", "home_team", "away_team", "market", "selection", "closing_odds",
        "odds_band", "grade", "stake_units", "winner", "ft_score", "settlement", "profit_loss_units",
        "pass_reason",
    ], result_rows)

    write_summary_reports(output_dir, result_rows)
    print(f"Backtest complete: {len(result_rows)} replayed matches")
    print(f"Output directory: {output_dir}")


def aggregate(rows: List[dict], key: str) -> List[dict]:
    stats = defaultdict(lambda: defaultdict(float))
    for row in rows:
        bucket = row[key]
        stake = float(row["stake_units"] or 0)
        pnl = float(row["profit_loss_units"] or 0)
        stats[bucket]["recommendations"] += 1
        stats[bucket]["bets"] += int(stake > 0)
        stats[bucket]["passes"] += int(stake == 0)
        stats[bucket]["wins"] += int(row["settlement"] == "Win")
        stats[bucket]["losses"] += int(row["settlement"] == "Loss")
        stats[bucket]["staked"] += stake
        stats[bucket]["pnl"] += pnl
    output = []
    for bucket, s in sorted(stats.items()):
        staked = s["staked"]
        bets = s["bets"]
        output.append({
            key: bucket,
            "recommendations": int(s["recommendations"]),
            "bets": int(bets),
            "passes": int(s["passes"]),
            "wins": int(s["wins"]),
            "losses": int(s["losses"]),
            "staked_units": round(staked, 4),
            "profit_loss_units": round(s["pnl"], 4),
            "roi_pct": round((s["pnl"] / staked) * 100, 2) if staked else "",
            "hit_rate_pct": round((s["wins"] / bets) * 100, 2) if bets else "",
        })
    return output


def write_summary_reports(output_dir: Path, rows: List[dict]) -> None:
    total_recs = len(rows)
    total_bets = sum(1 for r in rows if float(r["stake_units"] or 0) > 0)
    total_passes = total_recs - total_bets
    total_staked = sum(float(r["stake_units"] or 0) for r in rows)
    total_pnl = sum(float(r["profit_loss_units"] or 0) for r in rows)
    wins = sum(1 for r in rows if r["settlement"] == "Win")
    losses = sum(1 for r in rows if r["settlement"] == "Loss")

    summary = [
        {"metric": "engine", "value": "SPWIN v2.5 Platinum Pro Baseline 2026.1", "notes": "1X2-only reproducible baseline"},
        {"metric": "total_replayed_matches", "value": total_recs, "notes": "Rows with available closing 1X2 odds"},
        {"metric": "total_bets", "value": total_bets, "notes": "Non-PASS recommendations"},
        {"metric": "total_passes", "value": total_passes, "notes": "Filtered recommendations"},
        {"metric": "wins", "value": wins, "notes": "Winning bets"},
        {"metric": "losses", "value": losses, "notes": "Losing bets"},
        {"metric": "hit_rate_pct", "value": round((wins / total_bets) * 100, 2) if total_bets else "", "notes": "Wins / bets"},
        {"metric": "total_staked_units", "value": round(total_staked, 4), "notes": "Grade-based units"},
        {"metric": "total_profit_loss_units", "value": round(total_pnl, 4), "notes": "Decimal odds settlement"},
        {"metric": "roi_pct", "value": round((total_pnl / total_staked) * 100, 2) if total_staked else "", "notes": "Profit / staked"},
    ]
    write_csv(output_dir / "backtest_summary.csv", ["metric", "value", "notes"], summary)

    agg_fields = ["recommendations", "bets", "passes", "wins", "losses", "staked_units", "profit_loss_units", "roi_pct", "hit_rate_pct"]
    write_csv(output_dir / "roi_by_grade.csv", ["grade"] + agg_fields, aggregate(rows, "grade"))
    write_csv(output_dir / "roi_by_odds_band.csv", ["odds_band"] + agg_fields, aggregate(rows, "odds_band"))
    write_csv(output_dir / "roi_by_stage.csv", ["stage"] + agg_fields, aggregate(rows, "stage"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SPWIN historical backtest")
    parser.add_argument("--competition", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--markets", required=True)
    args = parser.parse_args()
    run_backtest(args.competition, args.engine, args.markets)


if __name__ == "__main__":
    main()
