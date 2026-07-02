#!/usr/bin/env python3
"""
SPWIN v2.6.2 Experimental Tiered Capital Preservation Engine
=============================================================

Purpose
-------
Experimental calibration step after v2.6.1. This version keeps v2.6.1 as the
frozen production baseline, but tests a controlled expansion framework before
promoting anything to v2.7.

Design goals
------------
- Preserve capital first.
- Increase qualified bet count without forcing bets.
- Separate major red flags from minor red flags.
- Add favourite-safe micro-stake zone.
- Keep blind replay discipline against immutable Gold records.

Key changes vs v2.6.1
---------------------
- Tiered staking rather than one hard CPI gate.
- Major red flags remain automatic PASS.
- One minor red flag can be allowed only at reduced stake.
- Favourite-safe zone allows tightly controlled micro exposure.
- Maximum stake remains below institutional risk limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import csv
import json

from spwin_engine import integrity, v260

ENGINE_VERSION = "SPWIN v2.6.2 Experimental Tiered Capital Preservation"

MAJOR_FLAGS = {
    "favourite drift",
    "AH drift/disagreement",
    "weak favourite price",
    "no favourite",
}

MINOR_FLAGS = {
    "draw compression",
    "HT draw pressure",
    "ultra-short price risk",
}


def split_red_flags(flags: list[str]) -> tuple[list[str], list[str]]:
    """Split inherited v2.6 red flags into major and minor groups."""
    major = [flag for flag in flags if flag in MAJOR_FLAGS]
    minor = [flag for flag in flags if flag in MINOR_FLAGS or flag not in MAJOR_FLAGS]
    return major, minor


def favourite_safe_zone(fav_odds: float, cpi: float, consensus: int, major_flags: list[str], minor_flags: list[str]) -> bool:
    """Controlled short-favourite expansion zone.

    This is intentionally narrow. It does not override major flags and only
    permits at most one minor warning.
    """
    return (
        1.18 <= fav_odds <= 1.45
        and cpi >= 72
        and consensus >= 3
        and not major_flags
        and len(minor_flags) <= 1
    )


def stake_policy(cpi: float, consensus: int, flags: list[str], fav_odds: float) -> tuple[str, float, str]:
    """Experimental tiered stake policy.

    Returns stake class, stake percentage, and classification.
    PASS remains the default.
    """
    major_flags, minor_flags = split_red_flags(flags)

    if major_flags or consensus < 3:
        return "PASS", 0.0, "Trap" if major_flags else "Avoid"

    # Tier A: very clean institutional-quality setup.
    if cpi >= 88 and consensus >= 4 and not minor_flags:
        return "TierA", 0.0100, "Institutional"

    # Tier B: clean high-quality setup. Similar risk spirit to v2.6.1, but not
    # overly dependent on a single CPI boundary.
    if cpi >= 80 and consensus >= 3 and not minor_flags:
        return "TierB", 0.0075, "Strong"

    # Tier C: controlled expansion with zero red flags.
    if cpi >= 76 and consensus >= 3 and not minor_flags:
        return "TierC", 0.0050, "Calibrated"

    # Favourite-safe micro zone. Allows one minor red flag only with reduced stake.
    if favourite_safe_zone(fav_odds, cpi, consensus, major_flags, minor_flags):
        return "FavSafeMicro", 0.0025, "FavouriteSafe"

    return "PASS", 0.0, "Avoid" if not flags else "Caution"


def make_recommendation(record: dict[str, Any]) -> v260.Recommendation:
    fav = v260.closing_favourite(record)
    fav_name = str(fav.get("selection")) if fav else "PASS"
    fav_odds = round(v260.odds(fav), 3) if fav else 0.0
    consensus, consensus_reasons = v260.compute_consensus(record, fav)
    flags = v260.red_flags(record, fav)
    cpi, cpi_reasons = v260.compute_cpi(record, fav, consensus, flags)
    stake_class, stake_pct, classification = stake_policy(cpi, consensus, flags, fav_odds)

    if stake_pct <= 0:
        market = "PASS"
        selection = "PASS"
    else:
        market = "1X2"
        selection = fav_name

    ht = v260.infer_ht(record)
    ou = v260.infer_ou(record)
    btts = v260.infer_btts(record)
    major_flags, minor_flags = split_red_flags(flags)
    confidence = min(95.0, max(40.0, cpi + (2 if consensus >= 4 else 0) - len(minor_flags)))

    flag_note = []
    if major_flags:
        flag_note.append("major flags: " + ", ".join(major_flags))
    if minor_flags:
        flag_note.append("minor flags: " + ", ".join(minor_flags))

    return v260.Recommendation(
        match_id=record.get("match_id", ""),
        match=record.get("match", ""),
        date=record.get("date", ""),
        stage=record.get("stage", ""),
        market=market,
        selection=selection,
        closing_odds=fav_odds,
        confidence=round(confidence, 1),
        cpi=cpi,
        classification=classification,
        stake_class=stake_class,
        stake_pct=stake_pct,
        red_flags=flags,
        consensus_count=consensus,
        rationale="; ".join(consensus_reasons + cpi_reasons + flag_note),
        ht_selection=ht.get("selection") if ht else None,
        ou_selection=ou.get("selection") if ou else None,
        btts_selection=btts.get("selection") if btts else None,
    )


def replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    bankroll = starting_bankroll
    peak = bankroll
    wins = losses = pushes = passes = 0
    gross_profit = 0.0
    gross_loss = 0.0
    max_dd = 0.0
    rows = []

    for idx, record in enumerate(records, start=1):
        rec = make_recommendation(record)
        stake = round(bankroll * rec.stake_pct, 2)
        outcome = "PASS" if stake <= 0 else integrity.require_settled(record, "1X2", rec.selection)
        pnl = 0.0

        if outcome == "Win":
            wins += 1
            pnl = round(stake * (rec.closing_odds - 1), 2)
            gross_profit += pnl
            bankroll += pnl
        elif outcome == "Loss":
            losses += 1
            pnl = -stake
            gross_loss += abs(pnl)
            bankroll += pnl
        elif outcome == "Push":
            pushes += 1
        else:
            passes += 1
            stake = 0.0

        bankroll = round(bankroll, 2)
        peak = max(peak, bankroll)
        dd = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_dd = max(max_dd, dd)

        rows.append({
            "#": idx,
            "date": rec.date,
            "match_id": rec.match_id,
            "match": rec.match,
            "stage": rec.stage,
            "classification": rec.classification,
            "cpi": rec.cpi,
            "consensus": rec.consensus_count,
            "red_flags": "|".join(rec.red_flags),
            "pick_market": rec.market,
            "pick": rec.selection,
            "odds": rec.closing_odds,
            "confidence": rec.confidence,
            "stake_class": rec.stake_class,
            "stake": stake,
            "outcome": outcome,
            "pnl": round(pnl, 2),
            "bankroll": bankroll,
            "ht_pick": rec.ht_selection or "",
            "ht_result": v260.settle(record, "HT_1X2", rec.ht_selection) if rec.ht_selection else "Unknown",
            "ou_pick": rec.ou_selection or "",
            "ou_result": v260.settle(record, "OU", rec.ou_selection) if rec.ou_selection else "Unknown",
            "btts_pick": rec.btts_selection or "",
            "btts_result": v260.settle(record, "BTTS", rec.btts_selection) if rec.btts_selection else "Unknown",
            "score_ht": record.get("score", {}).get("ht", ""),
            "score_ft": record.get("score", {}).get("ft", record.get("score", {}).get("ft_90", "")),
            "rationale": rec.rationale,
        })

    bets = wins + losses + pushes
    net = round(bankroll - starting_bankroll, 2)
    return {
        "engine_version": ENGINE_VERSION,
        "starting_bankroll": starting_bankroll,
        "final_bankroll": round(bankroll, 2),
        "net_profit": net,
        "roi_pct": round(net / starting_bankroll * 100, 2),
        "records": len(records),
        "bets": bets,
        "passes": passes,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate_pct": round(wins / bets * 100, 2) if bets else 0.0,
        "max_drawdown_pct": round(max_dd, 2),
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else ("inf" if gross_profit > 0 else 0.0),
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in result.items() if k != "rows"}
    (out_dir / "spwin_v2_6_2_gold_replay_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "spwin_v2_6_2_gold_replay_rows.json").write_text(json.dumps(result["rows"], indent=2), encoding="utf-8")
    if result["rows"]:
        with (out_dir / "spwin_v2_6_2_gold_replay.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(result["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SPWIN v2.6.2 experimental tiered Gold replay.")
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/benchmark/spwin_v2_6_2_gold")
    args = parser.parse_args()

    records = v260.load_gold_records(Path(args.gold_dir))
    result = replay(records, starting_bankroll=args.bankroll)
    write_outputs(result, Path(args.out_dir))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
