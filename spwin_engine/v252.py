#!/usr/bin/env python3
"""
SPWIN v2.5.2 Production Engine
==============================

Purpose
-------
Deterministic SPWIN production engine for replaying Gold records using only
pre-match archived odds and market movement.

Blind-replay rule
-----------------
The engine must not read match score/result fields before the recommendation is
locked. Scoring is performed only after prediction generation.

Supported markets
-----------------
- 1X2 winner/draw prediction
- Asian Handicap / alternate handicap signal
- Over/Under recommendation
- BTTS recommendation
- Half-time 1X2 / HT draw signal
- Confidence and stake class
- Portfolio stake sizing for a starting bankroll

This implementation is intentionally transparent and deterministic so every
Gold benchmark can be reproduced.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import argparse
import csv
import json
import math

ENGINE_VERSION = "SPWIN v2.5.2"


@dataclass
class Recommendation:
    match_id: str
    match: str
    date: str
    stage: str
    market: str
    selection: str
    closing_odds: float
    confidence: float
    confidence_band: str
    stake_class: str
    stake_pct: float
    rationale: str
    secondary_market: str | None = None
    secondary_selection: str | None = None
    secondary_odds: float | None = None
    ht_market: str | None = None
    ht_selection: str | None = None
    ht_odds: float | None = None
    btts_selection: str | None = None
    ou_selection: str | None = None


def load_gold_records(gold_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(gold_dir.glob("*.json")):
        if path.name == "MATCH_INDEX.json":
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("quality_grade") == "Gold" and record.get("status") == "COMPLETED":
            record["_file"] = path.name
            records.append(record)
    return sorted(records, key=lambda r: (r.get("date", ""), r.get("match_id", "")))


def markets(record: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [m for m in record.get("markets", []) if m.get("market_code") == code]


def by_selection(record: dict[str, Any], code: str, selection: str) -> dict[str, Any] | None:
    for m in markets(record, code):
        if m.get("selection") == selection:
            return m
    return None


def closing_favourite(record: dict[str, Any]) -> dict[str, Any] | None:
    rows = [m for m in markets(record, "1X2") if m.get("selection") != "Draw" and m.get("closing_odds")]
    return min(rows, key=lambda x: float(x["closing_odds"])) if rows else None


def draw_row(record: dict[str, Any]) -> dict[str, Any] | None:
    return by_selection(record, "1X2", "Draw")


def best_shortener(rows: Iterable[dict[str, Any]], prefix: str | None = None) -> dict[str, Any] | None:
    filtered = []
    for row in rows:
        if prefix and not str(row.get("selection", "")).lower().startswith(prefix.lower()):
            continue
        if row.get("movement_pct") is not None:
            filtered.append(row)
    return min(filtered, key=lambda x: float(x.get("movement_pct", 0))) if filtered else None


def movement(row: dict[str, Any] | None) -> float:
    return float(row.get("movement_pct", 0.0)) if row else 0.0


def odds(row: dict[str, Any] | None) -> float:
    return float(row.get("closing_odds", 0.0)) if row else 0.0


def infer_ou(record: dict[str, Any]) -> dict[str, Any] | None:
    ou_rows = markets(record, "OU")
    if not ou_rows:
        return None
    # Prefer the side with the strongest shortening. If no movement, prefer lower closing odds.
    return min(ou_rows, key=lambda x: (float(x.get("movement_pct", 0)), float(x.get("closing_odds", 99))))


def infer_btts(record: dict[str, Any]) -> dict[str, Any] | None:
    rows = markets(record, "BTTS")
    if not rows:
        return None
    return min(rows, key=lambda x: (float(x.get("movement_pct", 0)), float(x.get("closing_odds", 99))))


def infer_ht(record: dict[str, Any]) -> dict[str, Any] | None:
    rows = markets(record, "HT_1X2")
    if not rows:
        return None
    return min(rows, key=lambda x: (float(x.get("movement_pct", 0)), float(x.get("closing_odds", 99))))


def infer_ah(record: dict[str, Any], fav_selection: str | None) -> dict[str, Any] | None:
    if not fav_selection:
        return None
    candidates = []
    for code in ("AH", "HANDICAP_ALT"):
        for row in markets(record, code):
            if fav_selection in str(row.get("selection", "")):
                candidates.append(row)
    if not candidates:
        return None
    return min(candidates, key=lambda x: (float(x.get("movement_pct", 0)), float(x.get("closing_odds", 99))))


def confidence_band(conf: float) -> str:
    if conf >= 82:
        return "A"
    if conf >= 74:
        return "B"
    if conf >= 66:
        return "C"
    return "D"


def stake_class(conf: float, odds_value: float, conflict: bool) -> tuple[str, float]:
    if conflict:
        return "PASS_OR_MICRO", 0.00
    if conf >= 82 and 1.35 <= odds_value <= 2.20:
        return "A", 0.050
    if conf >= 74 and 1.45 <= odds_value <= 2.40:
        return "B", 0.035
    if conf >= 66 and 1.55 <= odds_value <= 2.80:
        return "C", 0.020
    return "PASS", 0.00


def make_recommendation(record: dict[str, Any]) -> Recommendation:
    fav = closing_favourite(record)
    draw = draw_row(record)
    ou = infer_ou(record)
    btts = infer_btts(record)
    ht = infer_ht(record)

    fav_sel = fav.get("selection") if fav else None
    fav_odds = odds(fav)
    fav_move = movement(fav)
    draw_move = movement(draw)
    draw_odds = odds(draw)
    ah = infer_ah(record, fav_sel)
    ah_move = movement(ah)

    score = 50.0
    reasons: list[str] = []
    conflict = False

    if fav:
        if fav_odds <= 1.25:
            score += 18
            reasons.append("elite short favourite")
        elif fav_odds <= 1.55:
            score += 14
            reasons.append("strong favourite")
        elif fav_odds <= 1.90:
            score += 9
            reasons.append("moderate favourite")
        elif fav_odds <= 2.30:
            score += 4
            reasons.append("soft favourite")

        if fav_move <= -15:
            score += 12
            reasons.append("heavy favourite steam")
        elif fav_move <= -8:
            score += 8
            reasons.append("favourite shortening")
        elif fav_move >= 8:
            score -= 10
            conflict = True
            reasons.append("favourite drift")

    if ah:
        if ah_move <= -18:
            score += 12
            reasons.append("handicap steam")
        elif ah_move <= -8:
            score += 7
            reasons.append("handicap support")
        elif ah_move >= 10:
            score -= 8
            conflict = True
            reasons.append("handicap drift")

    if draw and draw_move <= -12 and draw_odds <= 3.20:
        # Strong draw compression should downgrade favourite pick and may create draw selection.
        score -= 12
        conflict = True
        reasons.append("draw compression")

    if ht and fav_sel and fav_sel in str(ht.get("selection", "")) and movement(ht) <= -6:
        score += 5
        reasons.append("HT market aligned")
    elif ht and ht.get("selection") == "Draw" and movement(ht) <= -4:
        score -= 4
        reasons.append("HT draw pressure")

    # Draw override: use only when favourite is not strong and draw shortened heavily.
    market = "1X2"
    selection = fav_sel or "PASS"
    closing = fav_odds
    if draw and draw_move <= -14 and fav_odds >= 2.10:
        market = "1X2"
        selection = "Draw"
        closing = draw_odds
        score = max(62.0, 67.0 + min(8.0, abs(draw_move) / 3.0))
        conflict = False
        reasons.append("draw override")

    score = max(40.0, min(92.0, score))
    band = confidence_band(score)
    klass, pct = stake_class(score, closing, conflict)

    return Recommendation(
        match_id=record.get("match_id", ""),
        match=record.get("match", ""),
        date=record.get("date", ""),
        stage=record.get("stage", ""),
        market=market,
        selection=selection,
        closing_odds=round(closing, 3) if closing else 0.0,
        confidence=round(score, 1),
        confidence_band=band,
        stake_class=klass,
        stake_pct=pct,
        rationale="; ".join(reasons) if reasons else "no strong edge",
        secondary_market=ah.get("market_code") if ah else None,
        secondary_selection=ah.get("selection") if ah else None,
        secondary_odds=odds(ah) if ah else None,
        ht_market=ht.get("market_code") if ht else None,
        ht_selection=ht.get("selection") if ht else None,
        ht_odds=odds(ht) if ht else None,
        btts_selection=btts.get("selection") if btts else None,
        ou_selection=ou.get("selection") if ou else None,
    )


def settle_1x2(record: dict[str, Any], rec: Recommendation) -> str:
    for row in markets(record, "1X2"):
        if row.get("selection") == rec.selection:
            return row.get("result", "Unknown")
    return "Unknown"


def settle_market_selection(record: dict[str, Any], code: str | None, selection: str | None) -> str:
    if not code or not selection:
        return "Unknown"
    for row in markets(record, code):
        if row.get("selection") == selection:
            return row.get("result", "Unknown")
    return "Unknown"


def replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    bankroll = starting_bankroll
    peak = bankroll
    rows: list[dict[str, Any]] = []
    wins = losses = pushes = passes = 0
    max_drawdown = 0.0

    for idx, record in enumerate(records, start=1):
        rec = make_recommendation(record)
        stake = round(bankroll * rec.stake_pct, 2)
        outcome = "PASS" if stake <= 0 else settle_1x2(record, rec)
        pnl = 0.0
        if outcome == "Win":
            wins += 1
            pnl = round(stake * (rec.closing_odds - 1), 2)
            bankroll += pnl
        elif outcome == "Loss":
            losses += 1
            pnl = -stake
            bankroll += pnl
        elif outcome == "Push":
            pushes += 1
        else:
            passes += 1
            stake = 0.0
        bankroll = round(bankroll, 2)
        peak = max(peak, bankroll)
        dd = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_drawdown = max(max_drawdown, dd)

        rows.append({
            "#": idx,
            "date": rec.date,
            "match_id": rec.match_id,
            "match": rec.match,
            "stage": rec.stage,
            "pick_market": rec.market,
            "pick": rec.selection,
            "odds": rec.closing_odds,
            "confidence": rec.confidence,
            "band": rec.confidence_band,
            "stake_class": rec.stake_class,
            "stake": stake,
            "outcome": outcome,
            "pnl": round(pnl, 2),
            "bankroll": bankroll,
            "ht_pick": rec.ht_selection or "",
            "ht_result": settle_market_selection(record, rec.ht_market, rec.ht_selection),
            "ou_pick": rec.ou_selection or "",
            "ou_result": settle_market_selection(record, "OU", rec.ou_selection),
            "btts_pick": rec.btts_selection or "",
            "btts_result": settle_market_selection(record, "BTTS", rec.btts_selection),
            "score_ht": record.get("score", {}).get("ht", ""),
            "score_ft": record.get("score", {}).get("ft", record.get("score", {}).get("ft_90", "")),
            "rationale": rec.rationale,
        })

    bets = wins + losses + pushes
    final_profit = round(bankroll - starting_bankroll, 2)
    return {
        "engine_version": ENGINE_VERSION,
        "starting_bankroll": starting_bankroll,
        "final_bankroll": round(bankroll, 2),
        "net_profit": final_profit,
        "roi_pct": round(final_profit / starting_bankroll * 100, 2),
        "records": len(records),
        "bets": bets,
        "passes": passes,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate_pct": round(wins / bets * 100, 2) if bets else 0.0,
        "max_drawdown_pct": round(max_drawdown, 2),
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "spwin_v2_5_2_gold_replay_summary.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2), encoding="utf-8"
    )
    (out_dir / "spwin_v2_5_2_gold_replay_rows.json").write_text(
        json.dumps(result["rows"], indent=2), encoding="utf-8"
    )
    with (out_dir / "spwin_v2_5_2_gold_replay.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(result["rows"][0].keys()) if result["rows"] else [])
        writer.writeheader()
        writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SPWIN v2.5.2 Gold replay.")
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/benchmark/spwin_v2_5_2_gold")
    args = parser.parse_args()

    records = load_gold_records(Path(args.gold_dir))
    result = replay(records, starting_bankroll=args.bankroll)
    write_outputs(result, Path(args.out_dir))

    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
