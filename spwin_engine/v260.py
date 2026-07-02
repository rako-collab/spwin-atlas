#!/usr/bin/env python3
"""
SPWIN v2.6 Capital Preservation Engine
======================================

Design goal
-----------
Preserve capital first. PASS is the default unless the market edge is exceptional.

Core differences vs v2.5.2
--------------------------
- Capital Preservation Index (CPI) is the first decision gate.
- Mandatory market consensus: 3 of 4 alignment required.
- Automatic red flags veto bets.
- Lower maximum staking: 2.0% bankroll cap.
- Keeps blind replay discipline: recommendations are generated from pre-match
  market data only, then settled against Gold results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import argparse
import csv
import json

from spwin_engine import integrity

ENGINE_VERSION = "SPWIN v2.6 Capital Preservation"


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
    cpi: float
    classification: str
    stake_class: str
    stake_pct: float
    red_flags: list[str]
    consensus_count: int
    rationale: str
    ht_selection: str | None = None
    ou_selection: str | None = None
    btts_selection: str | None = None


def load_gold_records(gold_dir: Path) -> list[dict[str, Any]]:
    """Load the active completed Gold set.

    When ``MATCH_INDEX.json`` exists it is authoritative. This prevents
    immutable superseded correction files from being replayed alongside their
    active replacements. A directory-scan fallback is retained for ad-hoc test
    directories that do not have an index.
    """
    index_path = gold_dir / "MATCH_INDEX.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        entries = index.get("records")
        if not isinstance(entries, list):
            raise ValueError(f"MATCH_INDEX records must be a list: {index_path}")

        expected = int(index.get("total_records", len(entries)))
        if expected != len(entries):
            raise ValueError(
                f"MATCH_INDEX total_records={expected}, but records contains {len(entries)} entries"
            )

        records: list[dict[str, Any]] = []
        seen_files: set[str] = set()
        seen_match_ids: set[str] = set()

        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"MATCH_INDEX entry must be an object: {entry!r}")

            filename = str(entry.get("file", "")).strip()
            if not filename:
                raise ValueError("MATCH_INDEX entry missing file")
            if filename in seen_files:
                raise ValueError(f"Duplicate indexed file: {filename}")
            seen_files.add(filename)

            path = gold_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"Indexed Gold record missing: {path}")

            rec = json.loads(path.read_text(encoding="utf-8"))
            if rec.get("quality_grade") != "Gold" or rec.get("status") != "COMPLETED":
                raise ValueError(f"Indexed file is not completed Gold: {filename}")

            indexed_match_id = str(entry.get("match_id", "")).strip()
            record_match_id = str(rec.get("match_id", "")).strip()
            if indexed_match_id and indexed_match_id != record_match_id:
                raise ValueError(
                    f"match_id mismatch for {filename}: index={indexed_match_id!r}, "
                    f"record={record_match_id!r}"
                )
            if not record_match_id:
                raise ValueError(f"Indexed Gold record missing match_id: {filename}")
            if record_match_id in seen_match_ids:
                raise ValueError(f"Duplicate active match_id in MATCH_INDEX: {record_match_id}")
            seen_match_ids.add(record_match_id)

            rec["_file"] = filename
            records.append(rec)

        return sorted(records, key=lambda r: (r.get("date", ""), r.get("match_id", "")))

    records = []
    for path in sorted(gold_dir.glob("*.json")):
        if path.name == "MATCH_INDEX.json":
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("quality_grade") == "Gold" and rec.get("status") == "COMPLETED":
            rec["_file"] = path.name
            records.append(rec)
    return sorted(records, key=lambda r: (r.get("date", ""), r.get("match_id", "")))


def markets(record: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [m for m in record.get("markets", []) if m.get("market_code") == code]


def row_by_selection(record: dict[str, Any], code: str, selection: str) -> dict[str, Any] | None:
    for row in markets(record, code):
        if row.get("selection") == selection:
            return row
    return None


def odds(row: dict[str, Any] | None) -> float:
    return float(row.get("closing_odds", 0.0)) if row else 0.0


def move(row: dict[str, Any] | None) -> float:
    return float(row.get("movement_pct", 0.0)) if row else 0.0


def closing_favourite(record: dict[str, Any]) -> dict[str, Any] | None:
    rows = [r for r in markets(record, "1X2") if r.get("selection") != "Draw" and r.get("closing_odds")]
    return min(rows, key=lambda r: float(r.get("closing_odds", 99))) if rows else None


def draw_row(record: dict[str, Any]) -> dict[str, Any] | None:
    return row_by_selection(record, "1X2", "Draw")


def best_shortening(rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    rows = [r for r in rows if r.get("movement_pct") is not None]
    return min(rows, key=lambda r: (float(r.get("movement_pct", 0)), float(r.get("closing_odds", 99)))) if rows else None


def favourite_ah(record: dict[str, Any], fav: str | None) -> dict[str, Any] | None:
    if not fav:
        return None
    rows = []
    for code in ("AH", "HANDICAP_ALT"):
        rows.extend([r for r in markets(record, code) if fav in str(r.get("selection", ""))])
    return best_shortening(rows)


def infer_ht(record: dict[str, Any]) -> dict[str, Any] | None:
    return best_shortening(markets(record, "HT_1X2"))


def infer_ou(record: dict[str, Any]) -> dict[str, Any] | None:
    return best_shortening(markets(record, "OU"))


def infer_btts(record: dict[str, Any]) -> dict[str, Any] | None:
    return best_shortening(markets(record, "BTTS"))


def infer_first_goal(record: dict[str, Any], fav: str | None) -> dict[str, Any] | None:
    if not fav:
        return None
    for row in markets(record, "FG"):
        if row.get("selection") == fav:
            return row
    return None


def compute_consensus(record: dict[str, Any], fav: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not fav:
        return 0, []
    fav_name = str(fav.get("selection"))
    items = []
    count = 0

    if move(fav) <= -8:
        count += 1
        items.append("1X2 shortening")
    else:
        items.append("1X2 not strong")

    ah = favourite_ah(record, fav_name)
    if ah and move(ah) <= -8:
        count += 1
        items.append("AH aligned")
    else:
        items.append("AH not aligned")

    ht = infer_ht(record)
    if ht and fav_name in str(ht.get("selection", "")) and move(ht) <= -5:
        count += 1
        items.append("HT aligned")
    else:
        items.append("HT not aligned")

    fg = infer_first_goal(record, fav_name)
    if fg and move(fg) <= -4:
        count += 1
        items.append("first-goal aligned")
    else:
        items.append("first-goal not aligned")

    return count, items


def red_flags(record: dict[str, Any], fav: dict[str, Any] | None) -> list[str]:
    flags = []
    if not fav:
        return ["no favourite"]
    fav_name = str(fav.get("selection"))
    fav_odds = odds(fav)
    fav_move = move(fav)
    draw = draw_row(record)
    ah = favourite_ah(record, fav_name)
    ht = infer_ht(record)

    if fav_move > 0:
        flags.append("favourite drift")
    if draw and move(draw) <= -10:
        flags.append("draw compression")
    if ah and move(ah) > 5:
        flags.append("AH drift/disagreement")
    if ht and ht.get("selection") == "Draw" and move(ht) <= -4:
        flags.append("HT draw pressure")
    if fav_odds < 1.20:
        flags.append("ultra-short price risk")
    if fav_odds > 2.10:
        flags.append("weak favourite price")
    return flags


def compute_cpi(record: dict[str, Any], fav: dict[str, Any] | None, consensus: int, flags: list[str]) -> tuple[float, list[str]]:
    if not fav:
        return 0.0, ["no favourite"]
    fav_name = str(fav.get("selection"))
    fav_odds = odds(fav)
    fav_move = move(fav)
    ah = favourite_ah(record, fav_name)
    ht = infer_ht(record)
    ou = infer_ou(record)
    btts = infer_btts(record)

    cpi = 0.0
    reasons = []

    # Closing odds quality: max 20
    if 1.35 <= fav_odds <= 1.80:
        cpi += 20
        reasons.append("good price quality")
    elif 1.20 <= fav_odds < 1.35 or 1.80 < fav_odds <= 2.00:
        cpi += 14
        reasons.append("acceptable price")
    elif fav_odds < 1.20:
        cpi += 6
        reasons.append("too short")
    else:
        cpi += 8
        reasons.append("soft price")

    # AH confirmation: max 15
    if ah and move(ah) <= -15:
        cpi += 15
        reasons.append("strong AH confirmation")
    elif ah and move(ah) <= -8:
        cpi += 11
        reasons.append("AH confirmation")
    elif ah:
        cpi += 4
        reasons.append("weak AH support")

    # HT confirmation: max 10
    if ht and fav_name in str(ht.get("selection", "")) and move(ht) <= -8:
        cpi += 10
        reasons.append("strong HT confirmation")
    elif ht and fav_name in str(ht.get("selection", "")):
        cpi += 5
        reasons.append("HT partial confirmation")

    # OU/BTTS agreement: max 10. Conservative engines prefer clean and coherent side profile.
    if btts and str(btts.get("selection")) == "No" and move(btts) <= -4:
        cpi += 6
        reasons.append("BTTS No supports control")
    elif btts and move(btts) <= -10:
        cpi += 3
        reasons.append("BTTS event signal")
    if ou and move(ou) <= -8:
        cpi += 4
        reasons.append("OU confirms event profile")

    # Odds movement: max 20
    if fav_move <= -15:
        cpi += 20
        reasons.append("heavy favourite steam")
    elif fav_move <= -8:
        cpi += 14
        reasons.append("favourite steam")
    elif fav_move <= -3:
        cpi += 7
        reasons.append("mild favourite support")

    # Draw pressure: max 10
    draw = draw_row(record)
    if draw and move(draw) > -5:
        cpi += 10
        reasons.append("no draw pressure")
    elif draw and move(draw) > -10:
        cpi += 4
        reasons.append("mild draw pressure")
    else:
        reasons.append("draw pressure penalty")

    # Consensus: max 10
    if consensus >= 4:
        cpi += 10
        reasons.append("4/4 consensus")
    elif consensus == 3:
        cpi += 7
        reasons.append("3/4 consensus")
    else:
        reasons.append("consensus below threshold")

    # Tournament context: max 5
    if record.get("stage") == "Round of 32":
        cpi += 3
        reasons.append("knockout caution")
    else:
        cpi += 5
        reasons.append("group-stage context")

    # Red-flag penalties
    cpi -= min(35, len(flags) * 12)
    if flags:
        reasons.append("red flags: " + ", ".join(flags))

    return max(0.0, min(100.0, round(cpi, 1))), reasons


def classify(cpi: float, flags: list[str], consensus: int) -> str:
    if flags:
        return "Trap"
    if cpi >= 92 and consensus >= 3:
        return "Elite"
    if cpi >= 88 and consensus >= 3:
        return "Strong"
    if cpi >= 84 and consensus >= 3:
        return "Micro"
    return "Avoid"


def stake_policy(cpi: float, classification: str) -> tuple[str, float]:
    if classification == "Elite" and cpi >= 92:
        return "Elite", 0.020
    if classification == "Strong" and cpi >= 88:
        return "Strong", 0.0125
    if classification == "Micro" and cpi >= 84:
        return "Micro", 0.005
    return "PASS", 0.0


def make_recommendation(record: dict[str, Any]) -> Recommendation:
    fav = closing_favourite(record)
    fav_name = str(fav.get("selection")) if fav else "PASS"
    consensus, consensus_reasons = compute_consensus(record, fav)
    flags = red_flags(record, fav)
    cpi, cpi_reasons = compute_cpi(record, fav, consensus, flags)
    cls = classify(cpi, flags, consensus)
    stake_class, stake_pct = stake_policy(cpi, cls)

    # Conservative veto: require 3/4 consensus and no red flags.
    if consensus < 3 or flags:
        stake_class = "PASS"
        stake_pct = 0.0

    ht = infer_ht(record)
    ou = infer_ou(record)
    btts = infer_btts(record)
    confidence = min(95.0, max(40.0, cpi + (2 if consensus >= 4 else 0)))

    return Recommendation(
        match_id=record.get("match_id", ""),
        match=record.get("match", ""),
        date=record.get("date", ""),
        stage=record.get("stage", ""),
        market="1X2" if stake_pct > 0 else "PASS",
        selection=fav_name if stake_pct > 0 else "PASS",
        closing_odds=round(odds(fav), 3) if fav else 0.0,
        confidence=round(confidence, 1),
        cpi=cpi,
        classification=cls,
        stake_class=stake_class,
        stake_pct=stake_pct,
        red_flags=flags,
        consensus_count=consensus,
        rationale="; ".join(consensus_reasons + cpi_reasons),
        ht_selection=ht.get("selection") if ht else None,
        ou_selection=ou.get("selection") if ou else None,
        btts_selection=btts.get("selection") if btts else None,
    )


def settle(record: dict[str, Any], code: str, selection: str | None) -> str:
    """Settle safely using normalized labels and score-derived fallbacks."""
    return integrity.settle(record, code, selection)


def replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    bankroll = starting_bankroll
    peak = bankroll
    wins = losses = pushes = passes = 0
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
            "ht_result": settle(record, "HT_1X2", rec.ht_selection) if rec.ht_selection else "Unknown",
            "ou_pick": rec.ou_selection or "",
            "ou_result": settle(record, "OU", rec.ou_selection) if rec.ou_selection else "Unknown",
            "btts_pick": rec.btts_selection or "",
            "btts_result": settle(record, "BTTS", rec.btts_selection) if rec.btts_selection else "Unknown",
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
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in result.items() if k != "rows"}
    (out_dir / "spwin_v2_6_gold_replay_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "spwin_v2_6_gold_replay_rows.json").write_text(json.dumps(result["rows"], indent=2), encoding="utf-8")
    if result["rows"]:
        with (out_dir / "spwin_v2_6_gold_replay.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(result["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SPWIN v2.6 Capital Preservation Gold replay.")
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/benchmark/spwin_v2_6_gold")
    args = parser.parse_args()

    records = load_gold_records(Path(args.gold_dir))
    result = replay(records, starting_bankroll=args.bankroll)
    write_outputs(result, Path(args.out_dir))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
