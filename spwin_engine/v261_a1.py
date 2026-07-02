#!/usr/bin/env python3
"""SPWIN v2.6.1 A1 experimental incomplete-data micro-stake lane.

This module does not modify v2.6.1 production decisions. It evaluates a
separate 0.25% bankroll lane for sparse records containing only complete 1X2
and Asian Handicap markets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import csv
import json

from spwin_engine import integrity, v260, v261

ENGINE_VERSION = "SPWIN v2.6.1-A1 Experimental Micro Lane"
STAKE_PCT = 0.0025


@dataclass
class A1Decision:
    qualified: bool
    match_id: str
    match: str
    date: str
    selection: str
    odds: float
    one_x_two_move: float | None
    ah_move: float | None
    reason: str


def _coverage(record: dict[str, Any], favourite: str | None) -> list[str]:
    channels: list[str] = []
    if v260.closing_favourite(record):
        channels.append("1X2")
    if v260.favourite_ah(record, favourite):
        channels.append("AH")
    if v260.markets(record, "HT_1X2"):
        channels.append("HT")
    if v260.infer_first_goal(record, favourite):
        channels.append("FG")
    return channels


def evaluate(record: dict[str, Any]) -> A1Decision:
    production = v261.make_recommendation(record)
    favourite_row = v260.closing_favourite(record)
    favourite = str(favourite_row.get("selection")) if favourite_row else None
    ah_row = v260.favourite_ah(record, favourite)

    audit = integrity.audit_decision(
        record,
        favourite,
        cpi=production.cpi,
        consensus=production.consensus_count,
        flags=production.red_flags,
        stake_pct=production.stake_pct,
        cpi_threshold=80.0,
    )

    odds = round(v260.odds(favourite_row), 3) if favourite_row else 0.0
    one_x_two_move = round(v260.move(favourite_row), 2) if favourite_row else None
    ah_move = round(v260.move(ah_row), 2) if ah_row else None

    checks = [
        (audit["decision_status"] == "PASS_INCOMPLETE_DATA", "not an incomplete-data PASS"),
        (bool(audit["full_1x2"]), "1X2 market is incomplete"),
        (_coverage(record, favourite) == ["1X2", "AH"], "coverage is not exactly 1X2+AH"),
        (not production.red_flags, "v2.6.1 red flag present"),
        (favourite_row is not None and ah_row is not None, "favourite or AH row missing"),
        (1.20 <= odds <= 2.00, "favourite odds outside 1.20-2.00"),
        (one_x_two_move is not None and one_x_two_move <= -6.0, "1X2 shortening weaker than 6%"),
        (ah_move is not None and ah_move > -12.0, "AH shortening is too extreme"),
        (ah_move is not None and ah_move <= 5.0, "AH drift exceeds 5%"),
    ]

    failures = [message for passed, message in checks if not passed]
    return A1Decision(
        qualified=not failures,
        match_id=str(record.get("match_id", "")),
        match=str(record.get("match", "")),
        date=str(record.get("date", "")),
        selection=favourite or "PASS",
        odds=odds,
        one_x_two_move=one_x_two_move,
        ah_move=ah_move,
        reason="qualified" if not failures else "; ".join(failures),
    )


def _apply_bet(bankroll: float, stake_pct: float, odds: float, outcome: str) -> tuple[float, float, float]:
    stake = round(bankroll * stake_pct, 2)
    if outcome == "Win":
        pnl = round(stake * (odds - 1.0), 2)
    elif outcome == "Loss":
        pnl = -stake
    elif outcome == "Push":
        pnl = 0.0
    else:
        raise ValueError(f"Unsupported outcome: {outcome!r}")
    return stake, pnl, round(bankroll + pnl, 2)


def replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    bankroll = starting_bankroll
    peak = bankroll
    rows: list[dict[str, Any]] = []
    wins = losses = pushes = 0
    total_staked = 0.0
    max_drawdown = 0.0

    for record in records:
        decision = evaluate(record)
        if not decision.qualified:
            continue
        outcome = integrity.require_settled(record, "1X2", decision.selection)
        stake, pnl, bankroll = _apply_bet(bankroll, STAKE_PCT, decision.odds, outcome)
        total_staked = round(total_staked + stake, 2)
        peak = max(peak, bankroll)
        drawdown = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)

        wins += outcome == "Win"
        losses += outcome == "Loss"
        pushes += outcome == "Push"
        rows.append({
            "date": decision.date,
            "match_id": decision.match_id,
            "match": decision.match,
            "selection": decision.selection,
            "odds": decision.odds,
            "one_x_two_move": decision.one_x_two_move,
            "ah_move": decision.ah_move,
            "stake_pct": STAKE_PCT,
            "stake": stake,
            "outcome": outcome,
            "pnl": pnl,
            "bankroll": bankroll,
            "score_ft": record.get("score", {}).get("ft", record.get("score", {}).get("ft_90", "")),
        })

    net = round(bankroll - starting_bankroll, 2)
    bets = wins + losses + pushes
    return {
        "engine_version": ENGINE_VERSION,
        "starting_bankroll": starting_bankroll,
        "final_bankroll": bankroll,
        "net_profit": net,
        "bankroll_roi_pct": round(net / starting_bankroll * 100, 2),
        "total_staked": total_staked,
        "return_on_stakes_pct": round(net / total_staked * 100, 2) if total_staked else 0.0,
        "bets": bets,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate_pct": round(wins / bets * 100, 2) if bets else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "rows": rows,
    }


def combined_replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    events: list[tuple[str, str, dict[str, Any], str, float, float, str]] = []
    for record in records:
        production = v261.make_recommendation(record)
        if production.stake_pct > 0:
            outcome = integrity.require_settled(record, "1X2", production.selection)
            events.append((
                str(record.get("date", "")),
                str(record.get("match_id", "")),
                record,
                "v2.6.1 Production",
                production.stake_pct,
                production.closing_odds,
                production.selection,
            ))

        a1 = evaluate(record)
        if a1.qualified:
            outcome = integrity.require_settled(record, "1X2", a1.selection)
            events.append((
                a1.date,
                a1.match_id,
                record,
                "A1 Experimental",
                STAKE_PCT,
                a1.odds,
                a1.selection,
            ))

    bankroll = starting_bankroll
    peak = bankroll
    rows: list[dict[str, Any]] = []
    wins = losses = pushes = 0
    max_drawdown = 0.0
    total_staked = 0.0

    for date, match_id, record, lane, stake_pct, odds, selection in sorted(events, key=lambda item: (item[0], item[1], item[3])):
        outcome = integrity.require_settled(record, "1X2", selection)
        stake, pnl, bankroll = _apply_bet(bankroll, stake_pct, odds, outcome)
        total_staked = round(total_staked + stake, 2)
        peak = max(peak, bankroll)
        drawdown = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        wins += outcome == "Win"
        losses += outcome == "Loss"
        pushes += outcome == "Push"
        rows.append({
            "date": date,
            "match_id": match_id,
            "match": record.get("match", ""),
            "lane": lane,
            "selection": selection,
            "odds": odds,
            "stake_pct": stake_pct,
            "stake": stake,
            "outcome": outcome,
            "pnl": pnl,
            "bankroll": bankroll,
        })

    net = round(bankroll - starting_bankroll, 2)
    bets = wins + losses + pushes
    return {
        "engine_version": "SPWIN v2.6.1 Production + A1 Experimental Micro Lane",
        "starting_bankroll": starting_bankroll,
        "final_bankroll": bankroll,
        "net_profit": net,
        "bankroll_roi_pct": round(net / starting_bankroll * 100, 2),
        "total_staked": total_staked,
        "return_on_stakes_pct": round(net / total_staked * 100, 2) if total_staked else 0.0,
        "bets": bets,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate_pct": round(wins / bets * 100, 2) if bets else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], path_prefix: Path) -> None:
    path_prefix.parent.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in result.items() if key != "rows"}
    path_prefix.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    path_prefix.with_suffix(".rows.json").write_text(json.dumps(result["rows"], indent=2), encoding="utf-8")
    if result["rows"]:
        with path_prefix.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/benchmark/spwin_v261_a1_micro")
    args = parser.parse_args()

    records = v260.load_gold_records(Path(args.gold_dir))
    out_dir = Path(args.out_dir)
    a1 = replay(records, args.bankroll)
    combined = combined_replay(records, args.bankroll)
    write_outputs(a1, out_dir / "a1_only")
    write_outputs(combined, out_dir / "combined")
    print(json.dumps({"a1_only": {k: v for k, v in a1.items() if k != "rows"}, "combined": {k: v for k, v in combined.items() if k != "rows"}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
