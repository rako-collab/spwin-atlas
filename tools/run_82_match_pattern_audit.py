#!/usr/bin/env python3
"""Broad descriptive pattern audit for the authoritative 82-match Gold set.

This tool is research-only. It does not modify SPWIN production or A1 rules.
It reports sample sizes, hit rates, flat-stake ROI and Wilson intervals so small
or unstable patterns are not mistaken for proven edges.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
import argparse
import csv
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spwin_engine import integrity, v260, v261, v261_a1


def parse_score(value: Any) -> tuple[int, int] | None:
    text = str(value or "").strip()
    match = re.match(r"^(\d+)\s*[-:]\s*(\d+)$", text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def score90(record: dict[str, Any]) -> tuple[int, int] | None:
    score = record.get("score", {})
    return parse_score(score.get("ft_90", score.get("ft", "")))


def scoreht(record: dict[str, Any]) -> tuple[int, int] | None:
    return parse_score(record.get("score", {}).get("ht", ""))


def actual_result(score: tuple[int, int] | None) -> str:
    if score is None:
        return "Unknown"
    if score[0] > score[1]:
        return "Home"
    if score[0] < score[1]:
        return "Away"
    return "Draw"


def selection_side(record: dict[str, Any], selection: str) -> str:
    match = str(record.get("match", ""))
    if " vs " not in match:
        return "Unknown"
    home, away = match.split(" vs ", 1)
    folded = selection.casefold()
    if home.casefold() in folded:
        return "Home"
    if away.casefold() in folded:
        return "Away"
    if selection.strip().casefold() == "draw":
        return "Draw"
    return "Unknown"


def stage_bucket(stage: Any) -> str:
    text = str(stage or "").casefold()
    return "Group Stage" if "group" in text else "Knockout"


def favourite_odds_band(value: float) -> str:
    if value < 1.20:
        return "<1.20"
    if value < 1.40:
        return "1.20-1.39"
    if value < 1.60:
        return "1.40-1.59"
    if value < 1.80:
        return "1.60-1.79"
    if value <= 2.00:
        return "1.80-2.00"
    return ">2.00"


def favourite_move_band(value: float) -> str:
    if value <= -12:
        return "<=-12%"
    if value <= -8:
        return "-12% to -8%"
    if value <= -6:
        return "-8% to -6%"
    if value < 0:
        return "-6% to 0%"
    return ">=0% drift"


def draw_move_band(value: float | None) -> str:
    if value is None:
        return "Missing"
    if value <= -10:
        return "<=-10% compression"
    if value < 0:
        return "-10% to 0% shortening"
    return ">=0% drift"


def ah_move_band(value: float | None) -> str:
    if value is None:
        return "Missing"
    if value <= -12:
        return "<=-12% extreme steam"
    if value <= -8:
        return "-12% to -8% strong steam"
    if value <= 5:
        return "-8% to +5% neutral/supportive"
    return ">+5% disagreement"


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def favourite_pnl(row: dict[str, Any]) -> float:
    if row["favourite_outcome"] == "Win":
        return round(float(row["favourite_odds"]) - 1.0, 4)
    if row["favourite_outcome"] in {"Loss", "Draw"}:
        return -1.0
    if row["favourite_outcome"] == "Push":
        return 0.0
    return 0.0


def summarise_favourite_groups(
    rows: list[dict[str, Any]],
    key: str,
    order: list[str] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)

    output: list[dict[str, Any]] = []
    keys = order or sorted(groups)
    for value in keys:
        members = groups.get(value, [])
        if not members:
            continue
        settled = [row for row in members if row["favourite_outcome"] in {"Win", "Loss", "Draw", "Push"}]
        wins = sum(row["favourite_outcome"] == "Win" for row in settled)
        draws = sum(row["favourite_outcome"] == "Draw" for row in settled)
        losses = sum(row["favourite_outcome"] == "Loss" for row in settled)
        pnl = sum(favourite_pnl(row) for row in settled)
        lower, upper = wilson(wins, len(settled))
        output.append({
            key: value,
            "matches": len(members),
            "settled": len(settled),
            "favourite_wins": wins,
            "draws": draws,
            "favourite_losses": losses,
            "favourite_win_rate_pct": round(wins / len(settled) * 100, 2) if settled else 0.0,
            "win_rate_wilson_low_pct": round(lower * 100, 2),
            "win_rate_wilson_high_pct": round(upper * 100, 2),
            "flat_profit_units": round(pnl, 4),
            "flat_roi_pct": round(pnl / len(settled) * 100, 2) if settled else 0.0,
            "average_favourite_odds": round(sum(float(row["favourite_odds"]) for row in settled) / len(settled), 3) if settled else 0.0,
            "average_goals": round(sum(int(row["total_goals"]) for row in members) / len(members), 2),
            "over_2_5_pct": round(sum(bool(row["over_2_5"]) for row in members) / len(members) * 100, 2),
            "btts_pct": round(sum(bool(row["btts"]) for row in members) / len(members) * 100, 2),
            "ht_draw_pct": round(sum(row["ht_result"] == "Draw" for row in members) / len(members) * 100, 2),
        })
    return output


def summarise_binary(
    rows: list[dict[str, Any]],
    key: str,
    success_key: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    output: list[dict[str, Any]] = []
    for value in sorted(groups):
        members = groups[value]
        wins = sum(bool(row[success_key]) for row in members)
        lower, upper = wilson(wins, len(members))
        output.append({
            key: value,
            "matches": len(members),
            "successes": wins,
            "success_rate_pct": round(wins / len(members) * 100, 2),
            "wilson_low_pct": round(lower * 100, 2),
            "wilson_high_pct": round(upper * 100, 2),
        })
    return output


def market_pick_hit(record: dict[str, Any], row: dict[str, Any] | None, market: str) -> bool | None:
    if not row:
        return None
    selection = str(row.get("selection", ""))
    ft = score90(record)
    if ft is None:
        return None
    total = ft[0] + ft[1]
    if market == "OU":
        match = re.search(r"(Over|Under)\s+([0-9.]+)", selection, re.I)
        if not match:
            return None
        side = match.group(1).casefold()
        line = float(match.group(2))
        if total == line:
            return None
        return total > line if side == "over" else total < line
    if market == "BTTS":
        actual = ft[0] > 0 and ft[1] > 0
        if selection.casefold() == "yes":
            return actual
        if selection.casefold() == "no":
            return not actual
    if market == "HT_1X2":
        ht = scoreht(record)
        if ht is None:
            return None
        return selection_side(record, selection) == actual_result(ht)
    return None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        ft = score90(record)
        ht_score = scoreht(record)
        if ft is None or ht_score is None:
            raise ValueError(f"Missing parseable score for {record.get('match_id')}")

        favourite_row = v260.closing_favourite(record)
        favourite = str(favourite_row.get("selection")) if favourite_row else ""
        ah_row = v260.favourite_ah(record, favourite)
        draw_row = v260.draw_row(record)
        ht_market = v260.infer_ht(record)
        ou_market = v260.infer_ou(record)
        btts_market = v260.infer_btts(record)
        fg_row = v260.infer_first_goal(record, favourite)
        recommendation = v261.make_recommendation(record)
        completeness = integrity.assess_market_completeness(record, favourite)
        a1 = v261_a1.evaluate(record)

        favourite_outcome = integrity.settle(record, "1X2", favourite) if favourite else "Unknown"
        # Normalise 1X2 non-win results for descriptive tables.
        if favourite_outcome == "Loss" and actual_result(ft) == "Draw":
            favourite_outcome = "Draw"

        total_goals = ft[0] + ft[1]
        row = {
            "date": record.get("date", ""),
            "match_id": record.get("match_id", ""),
            "match": record.get("match", ""),
            "stage": record.get("stage", ""),
            "stage_bucket": stage_bucket(record.get("stage")),
            "ft_score": f"{ft[0]}-{ft[1]}",
            "ht_score": f"{ht_score[0]}-{ht_score[1]}",
            "total_goals": total_goals,
            "over_2_5": total_goals >= 3,
            "btts": ft[0] > 0 and ft[1] > 0,
            "ht_result": actual_result(ht_score),
            "ht_0_0": ht_score == (0, 0),
            "favourite": favourite,
            "favourite_odds": round(v260.odds(favourite_row), 3) if favourite_row else 0.0,
            "favourite_odds_band": favourite_odds_band(v260.odds(favourite_row)) if favourite_row else "Missing",
            "favourite_move": round(v260.move(favourite_row), 2) if favourite_row else None,
            "favourite_move_band": favourite_move_band(v260.move(favourite_row)) if favourite_row else "Missing",
            "favourite_outcome": favourite_outcome,
            "ah_move": round(v260.move(ah_row), 2) if ah_row else None,
            "ah_move_band": ah_move_band(v260.move(ah_row) if ah_row else None),
            "draw_move": round(v260.move(draw_row), 2) if draw_row else None,
            "draw_move_band": draw_move_band(v260.move(draw_row) if draw_row else None),
            "ht_market_selection": ht_market.get("selection", "") if ht_market else "",
            "ht_market_move": round(v260.move(ht_market), 2) if ht_market else None,
            "ht_market_hit": market_pick_hit(record, ht_market, "HT_1X2"),
            "ou_market_selection": ou_market.get("selection", "") if ou_market else "",
            "ou_market_move": round(v260.move(ou_market), 2) if ou_market else None,
            "ou_market_hit": market_pick_hit(record, ou_market, "OU"),
            "btts_market_selection": btts_market.get("selection", "") if btts_market else "",
            "btts_market_move": round(v260.move(btts_market), 2) if btts_market else None,
            "btts_market_hit": market_pick_hit(record, btts_market, "BTTS"),
            "fg_available": fg_row is not None,
            "consensus": recommendation.consensus_count,
            "cpi": recommendation.cpi,
            "red_flags": "|".join(recommendation.red_flags),
            "red_flag_count": len(recommendation.red_flags),
            "data_status": completeness["data_status"],
            "available_channels": completeness["available_consensus_channels"],
            "a1_qualified": a1.qualified,
        }
        rows.append(row)
    return rows


def signal_accuracy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    definitions: list[tuple[str, Callable[[dict[str, Any]], bool], str]] = [
        ("Favourite 1X2 steam <= -8%", lambda r: r["favourite_move"] is not None and r["favourite_move"] <= -8, "favourite"),
        ("Favourite AH steam <= -8%", lambda r: r["ah_move"] is not None and r["ah_move"] <= -8, "favourite"),
        ("Draw compression <= -10%", lambda r: r["draw_move"] is not None and r["draw_move"] <= -10, "draw_or_upset"),
        ("A1 qualified", lambda r: bool(r["a1_qualified"]), "favourite"),
        ("Consensus >= 3", lambda r: int(r["consensus"]) >= 3, "favourite"),
        ("No red flags", lambda r: int(r["red_flag_count"]) == 0, "favourite"),
    ]
    output: list[dict[str, Any]] = []
    for name, predicate, outcome_type in definitions:
        members = [row for row in rows if predicate(row)]
        if outcome_type == "favourite":
            successes = sum(row["favourite_outcome"] == "Win" for row in members)
            pnl = sum(favourite_pnl(row) for row in members)
            metric = "favourite_win"
        else:
            successes = sum(row["favourite_outcome"] != "Win" for row in members)
            pnl = 0.0
            metric = "favourite_failed"
        lower, upper = wilson(successes, len(members))
        output.append({
            "signal": name,
            "matches": len(members),
            "success_metric": metric,
            "successes": successes,
            "success_rate_pct": round(successes / len(members) * 100, 2) if members else 0.0,
            "wilson_low_pct": round(lower * 100, 2),
            "wilson_high_pct": round(upper * 100, 2),
            "flat_favourite_roi_pct": round(pnl / len(members) * 100, 2) if members and outcome_type == "favourite" else None,
        })
    return output


def market_accuracy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for label, hit_key, selection_key, move_key in [
        ("HT strongest shortening", "ht_market_hit", "ht_market_selection", "ht_market_move"),
        ("OU strongest shortening", "ou_market_hit", "ou_market_selection", "ou_market_move"),
        ("BTTS strongest shortening", "btts_market_hit", "btts_market_selection", "btts_market_move"),
    ]:
        members = [row for row in rows if row[hit_key] is not None]
        hits = sum(bool(row[hit_key]) for row in members)
        strong = [row for row in members if row[move_key] is not None and float(row[move_key]) <= -5]
        strong_hits = sum(bool(row[hit_key]) for row in strong)
        lower, upper = wilson(hits, len(members))
        strong_lower, strong_upper = wilson(strong_hits, len(strong))
        output.append({
            "market_signal": label,
            "available_matches": len(members),
            "hits": hits,
            "hit_rate_pct": round(hits / len(members) * 100, 2) if members else 0.0,
            "wilson_low_pct": round(lower * 100, 2),
            "wilson_high_pct": round(upper * 100, 2),
            "strong_shortening_matches": len(strong),
            "strong_shortening_hits": strong_hits,
            "strong_shortening_hit_rate_pct": round(strong_hits / len(strong) * 100, 2) if strong else 0.0,
            "strong_wilson_low_pct": round(strong_lower * 100, 2),
            "strong_wilson_high_pct": round(strong_upper * 100, 2),
        })
    return output


def red_flag_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flag_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        flags = [flag for flag in str(row["red_flags"]).split("|") if flag]
        if not flags:
            flag_members["No red flags"].append(row)
        for flag in flags:
            flag_members[flag].append(row)

    output: list[dict[str, Any]] = []
    for flag in sorted(flag_members):
        members = flag_members[flag]
        wins = sum(row["favourite_outcome"] == "Win" for row in members)
        pnl = sum(favourite_pnl(row) for row in members)
        lower, upper = wilson(wins, len(members))
        output.append({
            "flag": flag,
            "matches": len(members),
            "favourite_wins": wins,
            "favourite_win_rate_pct": round(wins / len(members) * 100, 2),
            "wilson_low_pct": round(lower * 100, 2),
            "wilson_high_pct": round(upper * 100, 2),
            "flat_favourite_roi_pct": round(pnl / len(members) * 100, 2),
        })
    return output


def make_findings(
    rows: list[dict[str, Any]],
    odds: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    draw_moves: list[dict[str, Any]],
    ah_moves: list[dict[str, Any]],
    consensus: list[dict[str, Any]],
    flags: list[dict[str, Any]],
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_wins = sum(row["favourite_outcome"] == "Win" for row in rows)
    baseline = baseline_wins / len(rows) * 100
    findings: list[dict[str, Any]] = []

    def add(category: str, title: str, evidence: str, n: int, strength: str) -> None:
        findings.append({
            "category": category,
            "title": title,
            "evidence": evidence,
            "sample_size": n,
            "strength": strength,
        })

    # Automatically surface favourite tables with at least five matches and material lift/decline.
    for table_name, table, key in [
        ("Odds", odds, "favourite_odds_band"),
        ("1X2 movement", moves, "favourite_move_band"),
        ("Draw movement", draw_moves, "draw_move_band"),
        ("AH movement", ah_moves, "ah_move_band"),
        ("Consensus", consensus, "consensus"),
    ]:
        for item in table:
            n = int(item["matches"])
            if n < 5:
                continue
            rate = float(item["favourite_win_rate_pct"])
            roi = float(item["flat_roi_pct"])
            delta = rate - baseline
            if abs(delta) >= 12 or abs(roi) >= 12:
                strength = "Moderate" if n >= 10 else "Tentative"
                add(
                    table_name,
                    f"{key}={item[key]}",
                    f"Favourite win rate {rate:.1f}% versus baseline {baseline:.1f}%; flat ROI {roi:+.1f}%.",
                    n,
                    strength,
                )

    for item in flags:
        n = int(item["matches"])
        if n < 5:
            continue
        rate = float(item["favourite_win_rate_pct"])
        roi = float(item["flat_favourite_roi_pct"])
        if abs(rate - baseline) >= 12 or abs(roi) >= 12:
            add(
                "Red flag",
                str(item["flag"]),
                f"Favourite win rate {rate:.1f}% versus baseline {baseline:.1f}%; flat ROI {roi:+.1f}%.",
                n,
                "Moderate" if n >= 10 else "Tentative",
            )

    for item in markets:
        n = int(item["strong_shortening_matches"])
        if n >= 8:
            rate = float(item["strong_shortening_hit_rate_pct"])
            if rate >= 65 or rate <= 45:
                add(
                    "Secondary market",
                    str(item["market_signal"]),
                    f"When shortening was at least 5%, the selected side hit {rate:.1f}% of {n} settled cases.",
                    n,
                    "Moderate" if n >= 12 else "Tentative",
                )

    # Always retain the A1 result as a known research pattern.
    a1_members = [row for row in rows if row["a1_qualified"]]
    if a1_members:
        a1_wins = sum(row["favourite_outcome"] == "Win" for row in a1_members)
        add(
            "A1",
            "Incomplete 1X2+AH micro lane",
            f"{a1_wins}-{len(a1_members)-a1_wins} favourite record; this was discovered on the same sample and remains forward-trial only.",
            len(a1_members),
            "Overfit risk",
        )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--out-dir", default="reports/analysis/world_cup_82_patterns")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = v260.load_gold_records(Path(args.gold_dir))
    rows = build_rows(records)

    favourite_wins = sum(row["favourite_outcome"] == "Win" for row in rows)
    favourite_draws = sum(row["favourite_outcome"] == "Draw" for row in rows)
    favourite_losses = sum(row["favourite_outcome"] == "Loss" for row in rows)
    goals = [int(row["total_goals"]) for row in rows]

    summary = {
        "active_gold_records": len(records),
        "group_stage_matches": sum(row["stage_bucket"] == "Group Stage" for row in rows),
        "knockout_matches": sum(row["stage_bucket"] == "Knockout" for row in rows),
        "favourite_wins_90m": favourite_wins,
        "draws_90m": favourite_draws,
        "favourite_losses_90m": favourite_losses,
        "favourite_win_rate_pct": round(favourite_wins / len(rows) * 100, 2),
        "average_goals": round(sum(goals) / len(goals), 2),
        "median_goals": sorted(goals)[len(goals) // 2],
        "over_2_5_matches": sum(bool(row["over_2_5"]) for row in rows),
        "over_2_5_pct": round(sum(bool(row["over_2_5"]) for row in rows) / len(rows) * 100, 2),
        "btts_matches": sum(bool(row["btts"]) for row in rows),
        "btts_pct": round(sum(bool(row["btts"]) for row in rows) / len(rows) * 100, 2),
        "ht_draw_matches": sum(row["ht_result"] == "Draw" for row in rows),
        "ht_draw_pct": round(sum(row["ht_result"] == "Draw" for row in rows) / len(rows) * 100, 2),
        "ht_0_0_matches": sum(bool(row["ht_0_0"]) for row in rows),
        "ht_0_0_pct": round(sum(bool(row["ht_0_0"]) for row in rows) / len(rows) * 100, 2),
        "complete_market_records": sum(row["data_status"] == "COMPLETE" for row in rows),
        "partial_market_records": sum(row["data_status"] == "PARTIAL" for row in rows),
        "a1_qualifiers": sum(bool(row["a1_qualified"]) for row in rows),
        "research_warning": "Patterns are descriptive and many were inspected on the same 82-match sample.",
    }

    stage = summarise_favourite_groups(rows, "stage_bucket", ["Group Stage", "Knockout"])
    odds = summarise_favourite_groups(rows, "favourite_odds_band", ["<1.20", "1.20-1.39", "1.40-1.59", "1.60-1.79", "1.80-2.00", ">2.00"])
    moves = summarise_favourite_groups(rows, "favourite_move_band", ["<=-12%", "-12% to -8%", "-8% to -6%", "-6% to 0%", ">=0% drift"])
    draw_moves = summarise_favourite_groups(rows, "draw_move_band", ["<=-10% compression", "-10% to 0% shortening", ">=0% drift", "Missing"])
    ah_moves = summarise_favourite_groups(rows, "ah_move_band", ["<=-12% extreme steam", "-12% to -8% strong steam", "-8% to +5% neutral/supportive", ">+5% disagreement", "Missing"])
    consensus = summarise_favourite_groups(rows, "consensus", ["0", "1", "2", "3", "4"])
    channel_count = summarise_favourite_groups(rows, "available_channels", ["1", "2", "3", "4"])
    flags = red_flag_table(rows)
    signals = signal_accuracy(rows)
    markets = market_accuracy(rows)
    findings = make_findings(rows, odds, moves, draw_moves, ah_moves, consensus, flags, markets)

    payloads = {
        "summary.json": summary,
        "findings.json": findings,
        "matches.json": rows,
        "by_stage.json": stage,
        "by_favourite_odds.json": odds,
        "by_favourite_move.json": moves,
        "by_draw_move.json": draw_moves,
        "by_ah_move.json": ah_moves,
        "by_consensus.json": consensus,
        "by_channel_count.json": channel_count,
        "by_red_flag.json": flags,
        "signal_accuracy.json": signals,
        "secondary_market_accuracy.json": markets,
    }
    for filename, payload in payloads.items():
        (out_dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    write_csv(out_dir / "matches.csv", rows)
    write_csv(out_dir / "by_stage.csv", stage)
    write_csv(out_dir / "by_favourite_odds.csv", odds)
    write_csv(out_dir / "by_favourite_move.csv", moves)
    write_csv(out_dir / "by_draw_move.csv", draw_moves)
    write_csv(out_dir / "by_ah_move.csv", ah_moves)
    write_csv(out_dir / "by_consensus.csv", consensus)
    write_csv(out_dir / "by_channel_count.csv", channel_count)
    write_csv(out_dir / "by_red_flag.csv", flags)
    write_csv(out_dir / "signal_accuracy.csv", signals)
    write_csv(out_dir / "secondary_market_accuracy.csv", markets)
    write_csv(out_dir / "findings.csv", findings)

    print(json.dumps({"summary": summary, "findings": findings}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
