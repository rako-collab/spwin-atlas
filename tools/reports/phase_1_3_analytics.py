#!/usr/bin/env python3
"""
SPWIN Atlas Phase 1.3 Analytics Engine v0.1

Generates first-pass analytics outputs from data/world_cup_2026/*.csv.

Modules covered:
A1 Team Performance Profiles
A2 Favourite vs Underdog Analysis
A3 Goal Pattern Analysis
A4 HT -> FT Transition Matrix
A5 Knockout Behaviour
A6 Odds Validation
A7 Market Efficiency
A8 SPWIN Feature Dataset
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "world_cup_2026"
ANALYTICS_DIR = ROOT / "analytics"


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


def parse_score(score: str) -> Tuple[int, int]:
    if not score or "-" not in score:
        return 0, 0
    left, right = score.split("-", 1)
    return int(left.strip()), int(right.strip())


def get_closing_1x2(odds_rows: List[dict]) -> Dict[str, List[dict]]:
    by_match: Dict[str, List[dict]] = defaultdict(list)
    for row in odds_rows:
        if row.get("market") == "1X2" and row.get("closing_odds"):
            by_match[row["match_id"]].append(row)
    return by_match


def favourite_for_match(match: dict, odds_by_match: Dict[str, List[dict]]) -> Tuple[str, float]:
    rows = odds_by_match.get(match["match_id"], [])
    candidates = []
    for row in rows:
        try:
            odds = float(row["closing_odds"])
        except (ValueError, TypeError):
            continue
        if row["selection"].lower() != "draw":
            candidates.append((row["selection"], odds))
    if not candidates:
        return "", 0.0
    return min(candidates, key=lambda item: item[1])


def team_profiles(matches: List[dict]) -> List[dict]:
    table = defaultdict(lambda: defaultdict(int))
    for m in matches:
        home, away = m["home_team"], m["away_team"]
        hg, ag = parse_score(m["ft_score"])
        for team, gf, ga in [(home, hg, ag), (away, ag, hg)]:
            table[team]["matches"] += 1
            table[team]["goals_for"] += gf
            table[team]["goals_against"] += ga
            table[team]["clean_sheets"] += int(ga == 0)
            table[team]["failed_to_score"] += int(gf == 0)
            table[team]["btts_matches"] += int(gf > 0 and ga > 0)
            table[team]["over_2_5_matches"] += int(gf + ga > 2)
        if hg > ag:
            table[home]["wins"] += 1
            table[away]["losses"] += 1
        elif ag > hg:
            table[away]["wins"] += 1
            table[home]["losses"] += 1
        else:
            table[home]["draws"] += 1
            table[away]["draws"] += 1
    rows = []
    for team, s in sorted(table.items()):
        mp = max(s["matches"], 1)
        rows.append({
            "team": team,
            "matches": s["matches"],
            "wins": s["wins"],
            "draws": s["draws"],
            "losses": s["losses"],
            "goals_for": s["goals_for"],
            "goals_against": s["goals_against"],
            "goal_difference": s["goals_for"] - s["goals_against"],
            "avg_goals_for": round(s["goals_for"] / mp, 3),
            "avg_goals_against": round(s["goals_against"] / mp, 3),
            "clean_sheet_pct": round(s["clean_sheets"] / mp, 3),
            "failed_to_score_pct": round(s["failed_to_score"] / mp, 3),
            "btts_pct": round(s["btts_matches"] / mp, 3),
            "over_2_5_pct": round(s["over_2_5_matches"] / mp, 3),
        })
    return rows


def favourite_patterns(matches: List[dict], odds_by_match: Dict[str, List[dict]]) -> List[dict]:
    bands = defaultdict(lambda: defaultdict(int))
    for m in matches:
        fav, fav_odds = favourite_for_match(m, odds_by_match)
        if not fav:
            continue
        if fav_odds <= 1.20:
            band = "heavy_1.01_1.20"
        elif fav_odds <= 1.50:
            band = "strong_1.21_1.50"
        elif fav_odds <= 2.00:
            band = "medium_1.51_2.00"
        else:
            band = "light_2.01_plus"
        s = bands[band]
        s["matches"] += 1
        winner = m["winner"]
        s["fav_wins"] += int(winner == fav)
        s["draws"] += int(winner == "Draw")
        s["underdog_wins"] += int(winner not in (fav, "Draw"))
        s["over_2_5"] += int(m.get("over_2_5") == "Yes")
        s["btts"] += int(m.get("btts") == "Yes")
    rows = []
    for band, s in sorted(bands.items()):
        n = max(s["matches"], 1)
        rows.append({
            "odds_band": band,
            "matches": s["matches"],
            "fav_win_pct": round(s["fav_wins"] / n, 3),
            "draw_pct": round(s["draws"] / n, 3),
            "underdog_win_pct": round(s["underdog_wins"] / n, 3),
            "over_2_5_pct": round(s["over_2_5"] / n, 3),
            "btts_pct": round(s["btts"] / n, 3),
        })
    return rows


def goal_patterns(matches: List[dict]) -> List[dict]:
    buckets = defaultdict(int)
    for m in matches:
        goals = int(m.get("total_goals") or 0)
        bucket = str(goals) if goals <= 5 else "6+"
        buckets[bucket] += 1
    total = max(sum(buckets.values()), 1)
    return [{"total_goals_bucket": k, "matches": v, "pct": round(v / total, 3)} for k, v in sorted(buckets.items())]


def htft_matrix(matches: List[dict]) -> List[dict]:
    counts = defaultdict(int)
    for m in matches:
        ht = m.get("ht_score", "") or "Unknown"
        ft = m.get("ft_score", "") or "Unknown"
        counts[(ht, ft)] += 1
    return [{"ht_score": ht, "ft_score": ft, "matches": n} for (ht, ft), n in sorted(counts.items())]


def stage_patterns(matches: List[dict]) -> List[dict]:
    stats = defaultdict(lambda: defaultdict(int))
    for m in matches:
        stage = m.get("stage", "Unknown")
        s = stats[stage]
        s["matches"] += 1
        s["draws"] += int(m.get("winner") == "Draw")
        s["btts"] += int(m.get("btts") == "Yes")
        s["over_2_5"] += int(m.get("over_2_5") == "Yes")
        s["goals"] += int(m.get("total_goals") or 0)
    rows = []
    for stage, s in sorted(stats.items()):
        n = max(s["matches"], 1)
        rows.append({
            "stage": stage,
            "matches": s["matches"],
            "avg_goals": round(s["goals"] / n, 3),
            "draw_pct": round(s["draws"] / n, 3),
            "btts_pct": round(s["btts"] / n, 3),
            "over_2_5_pct": round(s["over_2_5"] / n, 3),
        })
    return rows


def market_efficiency(matches: List[dict], odds_by_match: Dict[str, List[dict]]) -> List[dict]:
    rows = []
    for m in matches:
        fav, fav_odds = favourite_for_match(m, odds_by_match)
        if not fav:
            continue
        winner = m["winner"]
        if winner == fav:
            outcome = "market_correct"
        elif winner == "Draw":
            outcome = "market_draw_miss"
        else:
            outcome = "market_upset"
        rows.append({
            "match_id": m["match_id"],
            "stage": m.get("stage", ""),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "favourite": fav,
            "favourite_closing_odds": fav_odds,
            "winner": winner,
            "market_outcome": outcome,
            "total_goals": m.get("total_goals", ""),
            "btts": m.get("btts", ""),
            "over_2_5": m.get("over_2_5", ""),
        })
    return rows


def spwin_features(matches: List[dict], odds_by_match: Dict[str, List[dict]]) -> List[dict]:
    rows = []
    for m in matches:
        fav, fav_odds = favourite_for_match(m, odds_by_match)
        implied = round(1 / fav_odds, 4) if fav_odds else ""
        rows.append({
            "match_id": m["match_id"],
            "stage": m.get("stage", ""),
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "favourite": fav,
            "favourite_closing_odds": fav_odds or "",
            "favourite_implied_probability": implied,
            "ht_score": m.get("ht_score", ""),
            "ft_score": m.get("ft_score", ""),
            "total_goals": m.get("total_goals", ""),
            "btts": m.get("btts", ""),
            "over_2_5": m.get("over_2_5", ""),
            "odd_even": m.get("odd_even", ""),
            "data_quality": m.get("data_quality", ""),
        })
    return rows


def main() -> None:
    matches = read_csv(DATA_DIR / "matches.csv")
    odds = read_csv(DATA_DIR / "odds.csv")
    odds_by_match = get_closing_1x2(odds)

    write_csv(ANALYTICS_DIR / "team_profiles.csv", [
        "team", "matches", "wins", "draws", "losses", "goals_for", "goals_against", "goal_difference",
        "avg_goals_for", "avg_goals_against", "clean_sheet_pct", "failed_to_score_pct", "btts_pct", "over_2_5_pct"
    ], team_profiles(matches))

    write_csv(ANALYTICS_DIR / "favourite_patterns.csv", [
        "odds_band", "matches", "fav_win_pct", "draw_pct", "underdog_win_pct", "over_2_5_pct", "btts_pct"
    ], favourite_patterns(matches, odds_by_match))

    write_csv(ANALYTICS_DIR / "goal_patterns.csv", ["total_goals_bucket", "matches", "pct"], goal_patterns(matches))
    write_csv(ANALYTICS_DIR / "htft_patterns.csv", ["ht_score", "ft_score", "matches"], htft_matrix(matches))
    write_csv(ANALYTICS_DIR / "knockout_patterns.csv", ["stage", "matches", "avg_goals", "draw_pct", "btts_pct", "over_2_5_pct"], stage_patterns(matches))
    write_csv(ANALYTICS_DIR / "market_efficiency.csv", [
        "match_id", "stage", "home_team", "away_team", "favourite", "favourite_closing_odds", "winner",
        "market_outcome", "total_goals", "btts", "over_2_5"
    ], market_efficiency(matches, odds_by_match))
    write_csv(ANALYTICS_DIR / "spwin_features.csv", [
        "match_id", "stage", "home_team", "away_team", "favourite", "favourite_closing_odds", "favourite_implied_probability",
        "ht_score", "ft_score", "total_goals", "btts", "over_2_5", "odd_even", "data_quality"
    ], spwin_features(matches, odds_by_match))

    print("SPWIN Phase 1.3 analytics generated.")


if __name__ == "__main__":
    main()
