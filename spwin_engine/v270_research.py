#!/usr/bin/env python3
"""SPWIN v2.7 research engine with correctness-only fixes.

This module preserves the v2.6.1 admission thresholds and stake policy while
fixing implementation defects identified during the v2.6.1 audit. It is a
research branch and must not replace the frozen v2.6.1 production benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import csv
import json

from spwin_engine import integrity, v260, v261

ENGINE_VERSION = "SPWIN v2.7 Research Correctness"
RESEARCH_ONLY = True
CPI_THRESHOLD = 80.0
CONSENSUS_THRESHOLD = 3
HT_PARTIAL_THRESHOLD = -3.0


@dataclass
class ResearchRecommendation:
    match_id: str
    match: str
    date: str
    stage: str
    market: str
    selection: str
    price: float
    price_type: str
    signal_score: float
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
    primary_ah_selection: str | None = None
    primary_ah_movement: float | None = None
    alternate_ah_observation: str | None = None


def _favourite_rows(record: dict[str, Any], code: str, favourite: str | None) -> list[dict[str, Any]]:
    if not favourite:
        return []
    folded = favourite.strip().casefold()
    return [
        row
        for row in v260.markets(record, code)
        if folded in str(row.get("selection", "")).casefold()
    ]


def primary_favourite_ah(record: dict[str, Any], favourite: str | None) -> dict[str, Any] | None:
    """Return the favourite's main AH row only.

    v2.6.1 selected the strongest shortening across AH and HANDICAP_ALT. That
    allowed a lower-liquidity alternate handicap to override a non-confirming
    main line. v2.7 research uses AH as the scoring source and keeps alternate
    handicaps as observations only.
    """

    return v260.best_shortening(_favourite_rows(record, "AH", favourite))


def alternate_favourite_ah(record: dict[str, Any], favourite: str | None) -> dict[str, Any] | None:
    return v260.best_shortening(_favourite_rows(record, "HANDICAP_ALT", favourite))


def normalize_stage(stage: Any) -> str:
    return " ".join(str(stage or "").replace("_", " ").replace("-", " ").casefold().split())


def stage_context(stage: Any) -> tuple[int, str]:
    """Return explicit context points without misclassifying knockout rounds."""

    normalized = normalize_stage(stage)
    if "group" in normalized:
        return 5, "group-stage context"

    knockout_tokens = (
        "round of 32",
        "round 32",
        "round of 16",
        "round 16",
        "quarter",
        "semi",
        "final",
        "third place",
        "3rd place",
    )
    if any(token in normalized for token in knockout_tokens):
        return 3, "knockout caution"

    return 0, "unknown stage context"


def price_type(record: dict[str, Any]) -> str:
    """Label the price honestly as closing or as a current snapshot."""

    explicit = (
        record.get("odds_snapshot_type")
        or record.get("market_snapshot_type")
        or (record.get("provenance", {}) or {}).get("odds_snapshot_type")
    )
    if explicit:
        return str(explicit)
    if str(record.get("status", "")).strip().upper() == "COMPLETED":
        return "closing"
    return "current_snapshot"


def compute_consensus(record: dict[str, Any], favourite: dict[str, Any] | None) -> tuple[int, list[str]]:
    if not favourite:
        return 0, []

    favourite_name = str(favourite.get("selection"))
    count = 0
    reasons: list[str] = []

    if v260.move(favourite) <= -8:
        count += 1
        reasons.append("1X2 shortening")
    else:
        reasons.append("1X2 not strong")

    ah = primary_favourite_ah(record, favourite_name)
    if ah and v260.move(ah) <= -8:
        count += 1
        reasons.append("main AH aligned")
    else:
        reasons.append("main AH not aligned")

    ht = v260.infer_ht(record)
    if ht and favourite_name in str(ht.get("selection", "")) and v260.move(ht) <= -5:
        count += 1
        reasons.append("HT aligned")
    else:
        reasons.append("HT not aligned")

    first_goal = v260.infer_first_goal(record, favourite_name)
    if first_goal and v260.move(first_goal) <= -4:
        count += 1
        reasons.append("first-goal aligned")
    else:
        reasons.append("first-goal not aligned")

    return count, reasons


def red_flags(record: dict[str, Any], favourite: dict[str, Any] | None) -> list[str]:
    flags: list[str] = []
    if not favourite:
        return ["no favourite"]

    favourite_name = str(favourite.get("selection"))
    favourite_odds = v260.odds(favourite)
    favourite_move = v260.move(favourite)
    draw = v260.draw_row(record)
    ah = primary_favourite_ah(record, favourite_name)
    ht = v260.infer_ht(record)

    if favourite_move > 0:
        flags.append("favourite drift")
    if draw and v260.move(draw) <= -10:
        flags.append("draw compression")
    if ah and v260.move(ah) > 5:
        flags.append("main AH drift/disagreement")
    if ht and str(ht.get("selection", "")).casefold() == "draw" and v260.move(ht) <= -4:
        flags.append("HT draw pressure")
    if favourite_odds < 1.20:
        flags.append("ultra-short price risk")
    if favourite_odds > 2.10:
        flags.append("weak favourite price")
    return flags


def compute_cpi(
    record: dict[str, Any],
    favourite: dict[str, Any] | None,
    consensus: int,
    flags: list[str],
) -> tuple[float, list[str]]:
    if not favourite:
        return 0.0, ["no favourite"]

    favourite_name = str(favourite.get("selection"))
    favourite_odds = v260.odds(favourite)
    favourite_move = v260.move(favourite)
    ah = primary_favourite_ah(record, favourite_name)
    ht = v260.infer_ht(record)
    ou = v260.infer_ou(record)
    btts = v260.infer_btts(record)

    cpi = 0.0
    reasons: list[str] = []

    if 1.35 <= favourite_odds <= 1.80:
        cpi += 20
        reasons.append("good price quality")
    elif 1.20 <= favourite_odds < 1.35 or 1.80 < favourite_odds <= 2.00:
        cpi += 14
        reasons.append("acceptable price")
    elif favourite_odds < 1.20:
        cpi += 6
        reasons.append("too short")
    else:
        cpi += 8
        reasons.append("soft price")

    if ah and v260.move(ah) <= -15:
        cpi += 15
        reasons.append("strong main AH confirmation")
    elif ah and v260.move(ah) <= -8:
        cpi += 11
        reasons.append("main AH confirmation")
    elif ah:
        cpi += 4
        reasons.append("weak main AH support")

    if ht and favourite_name in str(ht.get("selection", "")) and v260.move(ht) <= -8:
        cpi += 10
        reasons.append("strong HT confirmation")
    elif (
        ht
        and favourite_name in str(ht.get("selection", ""))
        and v260.move(ht) <= HT_PARTIAL_THRESHOLD
    ):
        cpi += 5
        reasons.append("HT partial confirmation")

    if btts and str(btts.get("selection")) == "No" and v260.move(btts) <= -4:
        cpi += 6
        reasons.append("BTTS No supports control")
    elif btts and v260.move(btts) <= -10:
        cpi += 3
        reasons.append("BTTS event signal")
    if ou and v260.move(ou) <= -8:
        cpi += 4
        reasons.append("OU confirms event profile")

    if favourite_move <= -15:
        cpi += 20
        reasons.append("heavy favourite steam")
    elif favourite_move <= -8:
        cpi += 14
        reasons.append("favourite steam")
    elif favourite_move <= -3:
        cpi += 7
        reasons.append("mild favourite support")

    draw = v260.draw_row(record)
    if draw and v260.move(draw) > -5:
        cpi += 10
        reasons.append("no draw pressure")
    elif draw and v260.move(draw) > -10:
        cpi += 4
        reasons.append("mild draw pressure")
    else:
        reasons.append("draw pressure penalty")

    if consensus >= 4:
        cpi += 10
        reasons.append("4/4 consensus")
    elif consensus == 3:
        cpi += 7
        reasons.append("3/4 consensus")
    else:
        reasons.append("consensus below threshold")

    context_points, context_reason = stage_context(record.get("stage"))
    cpi += context_points
    reasons.append(context_reason)

    cpi -= min(35, len(flags) * 12)
    if flags:
        reasons.append("red flags: " + ", ".join(flags))

    return max(0.0, min(100.0, round(cpi, 1))), reasons


def assess_market_completeness(record: dict[str, Any], favourite: str | None) -> dict[str, Any]:
    one_x_two = [row for row in v260.markets(record, "1X2") if row.get("closing_odds")]
    team_rows = [row for row in one_x_two if str(row.get("selection", "")).casefold() != "draw"]
    has_draw = any(str(row.get("selection", "")).casefold() == "draw" for row in one_x_two)
    full_1x2 = len(team_rows) >= 2 and has_draw

    has_main_ah = bool(primary_favourite_ah(record, favourite))
    has_ht = bool(v260.markets(record, "HT_1X2"))
    has_fg = bool(v260.infer_first_goal(record, favourite))

    channels = {
        "1X2": bool(favourite),
        "AH": has_main_ah,
        "HT_1X2": has_ht,
        "FG": has_fg,
    }
    available_channels = sum(1 for available in channels.values() if available)
    consensus_capable = full_1x2 and available_channels >= 3
    missing = [name for name, available in channels.items() if not available]
    if not full_1x2:
        missing.insert(0, "full_1X2")

    return {
        "data_status": "COMPLETE" if consensus_capable else "PARTIAL",
        "full_1x2": full_1x2,
        "available_consensus_channels": available_channels,
        "consensus_capable": consensus_capable,
        "missing_channels": missing,
    }


def audit_decision(
    record: dict[str, Any],
    favourite: str | None,
    *,
    cpi: float,
    consensus: int,
    flags: list[str],
    stake_pct: float,
) -> dict[str, Any]:
    completeness = assess_market_completeness(record, favourite)
    reasons: list[str] = []

    if stake_pct > 0:
        status = "RESEARCH_BET"
        reasons.append("research admission gates passed")
    else:
        if not completeness["consensus_capable"]:
            reasons.append("incomplete market coverage")
        if flags:
            reasons.append("red flags: " + ", ".join(flags))
        if consensus < CONSENSUS_THRESHOLD:
            reasons.append(f"consensus {consensus}/4 below {CONSENSUS_THRESHOLD}/4")
        if cpi < CPI_THRESHOLD:
            reasons.append(f"CPI {cpi:.1f} below {CPI_THRESHOLD:.1f}")

        if not completeness["consensus_capable"]:
            status = "PASS_INCOMPLETE_DATA"
        elif flags:
            status = "PASS_RED_FLAG"
        else:
            status = "PASS_MODEL"

    return {
        **completeness,
        "decision_status": status,
        "decision_reasons": reasons,
        "research_only": True,
    }


def _alternate_ah_observation(record: dict[str, Any], favourite_name: str) -> str | None:
    row = alternate_favourite_ah(record, favourite_name)
    if not row:
        return None
    return f"{row.get('selection')} {v260.move(row):+.1f}% (observation only)"


def make_recommendation(record: dict[str, Any]) -> ResearchRecommendation:
    favourite = v260.closing_favourite(record)
    favourite_name = str(favourite.get("selection")) if favourite else "PASS"
    consensus, consensus_reasons = compute_consensus(record, favourite)
    flags = red_flags(record, favourite)
    cpi, cpi_reasons = compute_cpi(record, favourite, consensus, flags)
    stake_class, stake_pct = v261.stake_policy(cpi, consensus, flags)

    if stake_pct <= 0:
        classification = "Trap" if flags else "Avoid"
        market = "PASS"
        selection = "PASS"
    elif cpi >= 85:
        classification = "Strong"
        market = "1X2"
        selection = favourite_name
    else:
        classification = "CalibratedMicro"
        market = "1X2"
        selection = favourite_name

    ht = v260.infer_ht(record)
    ou = v260.infer_ou(record)
    btts = v260.infer_btts(record)
    main_ah = primary_favourite_ah(record, favourite_name)
    signal_score = min(95.0, max(40.0, cpi + (2 if consensus >= 4 else 0)))

    return ResearchRecommendation(
        match_id=str(record.get("match_id", "")),
        match=str(record.get("match", "")),
        date=str(record.get("date", "")),
        stage=str(record.get("stage", "")),
        market=market,
        selection=selection,
        price=round(v260.odds(favourite), 3) if favourite else 0.0,
        price_type=price_type(record),
        signal_score=round(signal_score, 1),
        cpi=cpi,
        classification=classification,
        stake_class=stake_class,
        stake_pct=stake_pct,
        red_flags=flags,
        consensus_count=consensus,
        rationale="; ".join(consensus_reasons + cpi_reasons),
        ht_selection=ht.get("selection") if ht else None,
        ou_selection=ou.get("selection") if ou else None,
        btts_selection=btts.get("selection") if btts else None,
        primary_ah_selection=str(main_ah.get("selection")) if main_ah else None,
        primary_ah_movement=round(v260.move(main_ah), 1) if main_ah else None,
        alternate_ah_observation=_alternate_ah_observation(record, favourite_name),
    )


def replay(records: list[dict[str, Any]], starting_bankroll: float = 1000.0) -> dict[str, Any]:
    bankroll = starting_bankroll
    peak = bankroll
    wins = losses = pushes = passes = 0
    max_drawdown = 0.0
    rows: list[dict[str, Any]] = []

    for index, record in enumerate(records, start=1):
        recommendation = make_recommendation(record)
        stake = round(bankroll * recommendation.stake_pct, 2)
        outcome = (
            "PASS"
            if stake <= 0
            else integrity.require_settled(record, "1X2", recommendation.selection)
        )
        pnl = 0.0

        if outcome == "Win":
            wins += 1
            pnl = round(stake * (recommendation.price - 1), 2)
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
        drawdown = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_drawdown = max(max_drawdown, drawdown)

        favourite = v260.closing_favourite(record)
        favourite_name = str(favourite.get("selection")) if favourite else None
        audit = audit_decision(
            record,
            favourite_name,
            cpi=recommendation.cpi,
            consensus=recommendation.consensus_count,
            flags=recommendation.red_flags,
            stake_pct=recommendation.stake_pct,
        )

        rows.append({
            "#": index,
            "date": recommendation.date,
            "match_id": recommendation.match_id,
            "match": recommendation.match,
            "stage": recommendation.stage,
            "classification": recommendation.classification,
            "cpi": recommendation.cpi,
            "consensus": recommendation.consensus_count,
            "red_flags": "|".join(recommendation.red_flags),
            "data_status": audit["data_status"],
            "available_consensus_channels": audit["available_consensus_channels"],
            "missing_channels": "|".join(audit["missing_channels"]),
            "decision_status": audit["decision_status"],
            "decision_reasons": "|".join(audit["decision_reasons"]),
            "research_only": True,
            "pick_market": recommendation.market,
            "pick": recommendation.selection,
            "price": recommendation.price,
            "price_type": recommendation.price_type,
            "signal_score": recommendation.signal_score,
            "stake_class": recommendation.stake_class,
            "stake": stake,
            "outcome": outcome,
            "pnl": round(pnl, 2),
            "bankroll": bankroll,
            "primary_ah": recommendation.primary_ah_selection or "",
            "primary_ah_movement": recommendation.primary_ah_movement,
            "alternate_ah_observation": recommendation.alternate_ah_observation or "",
            "ht_pick": recommendation.ht_selection or "",
            "ht_result": v260.settle(record, "HT_1X2", recommendation.ht_selection)
            if recommendation.ht_selection
            else "Unknown",
            "ou_pick": recommendation.ou_selection or "",
            "ou_result": v260.settle(record, "OU", recommendation.ou_selection)
            if recommendation.ou_selection
            else "Unknown",
            "btts_pick": recommendation.btts_selection or "",
            "btts_result": v260.settle(record, "BTTS", recommendation.btts_selection)
            if recommendation.btts_selection
            else "Unknown",
            "score_ht": record.get("score", {}).get("ht", ""),
            "score_ft": record.get("score", {}).get("ft", record.get("score", {}).get("ft_90", "")),
            "rationale": recommendation.rationale,
        })

    bets = wins + losses + pushes
    net_profit = round(bankroll - starting_bankroll, 2)
    return {
        "engine_version": ENGINE_VERSION,
        "research_only": RESEARCH_ONLY,
        "production_engine_unchanged": "SPWIN v2.6.1",
        "starting_bankroll": starting_bankroll,
        "final_bankroll": round(bankroll, 2),
        "net_profit": net_profit,
        "roi_pct": round(net_profit / starting_bankroll * 100, 2),
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
    summary = {key: value for key, value in result.items() if key != "rows"}
    (out_dir / "spwin_v2_7_research_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (out_dir / "spwin_v2_7_research_rows.json").write_text(
        json.dumps(result["rows"], indent=2), encoding="utf-8"
    )
    if result["rows"]:
        with (out_dir / "spwin_v2_7_research.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SPWIN v2.7 correctness research replay.")
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--out-dir", default="reports/research/spwin_v2_7_correctness")
    args = parser.parse_args()

    records = v260.load_gold_records(Path(args.gold_dir))
    result = replay(records, starting_bankroll=args.bankroll)
    write_outputs(result, Path(args.out_dir))
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
