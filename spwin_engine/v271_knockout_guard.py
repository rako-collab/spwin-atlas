#!/usr/bin/env python3
"""SPWIN v2.7.1 research engine with knockout market guard.

Research-only extension of v2.7 correctness fixes. Production v2.6.1 remains
frozen and unchanged.

The guard prevents an admitted short-priced knockout favourite from being
automatically converted into a regulation-time 1X2 bet when the current no-vig
draw probability remains material. In that case, the engine may use an
explicitly valued qualification market; otherwise it passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import argparse
import csv
import json

from spwin_engine import integrity, v260, v270_research as v270

ENGINE_VERSION = "SPWIN v2.7.1 Research Knockout Market Guard"
RESEARCH_ONLY = True
PRODUCTION_ENGINE = "SPWIN v2.6.1"
REGULATION_MARKET = "1X2"
QUALIFY_MARKET = "QUALIFY"
KNOCKOUT_FAVOURITE_ODDS_MAX = 1.50
KNOCKOUT_DRAW_PROBABILITY_MIN = 0.20
MIN_EXPECTED_VALUE = 0.02
KNOCKOUT_STAKE_CAP = 0.0075


@dataclass
class V271Recommendation:
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
    normalized_draw_probability: float | None = None
    draw_risk_band: str = "unknown"
    knockout_guard_triggered: bool = False
    knockout_guard_reason: str = ""
    decision_code: str = ""
    expected_value: float | None = None
    steam_saturation: bool = False


def is_knockout_stage(stage: Any) -> bool:
    points, reason = v270.stage_context(stage)
    return points == 3 and reason == "knockout caution"


def normalized_1x2_probabilities(record: dict[str, Any]) -> dict[str, float]:
    """Return no-vig probabilities for a complete positive-priced 1X2 market."""

    rows = [row for row in v260.markets(record, "1X2") if row.get("closing_odds")]
    implied: dict[str, float] = {}
    for row in rows:
        selection = str(row.get("selection", "")).strip()
        price = v260.odds(row)
        if selection and price > 1.0:
            implied[selection] = 1.0 / price

    if len(implied) < 3 or "Draw" not in implied:
        return {}

    total = sum(implied.values())
    if total <= 0:
        return {}
    return {selection: value / total for selection, value in implied.items()}


def normalized_draw_probability(record: dict[str, Any]) -> float | None:
    probabilities = normalized_1x2_probabilities(record)
    value = probabilities.get("Draw")
    return round(value, 6) if value is not None else None


def draw_risk_band(probability: float | None) -> str:
    if probability is None:
        return "unknown"
    if probability < 0.18:
        return "low"
    if probability < 0.22:
        return "moderate"
    if probability <= 0.25:
        return "high"
    return "very_high"


def steam_saturation(favourite: dict[str, Any] | None) -> bool:
    if not favourite:
        return False
    return v260.move(favourite) <= -15 and v260.odds(favourite) < 1.45


def knockout_guard_applies(
    record: dict[str, Any],
    favourite: dict[str, Any] | None,
    draw_probability: float | None,
) -> bool:
    if not favourite or draw_probability is None:
        return False
    return (
        is_knockout_stage(record.get("stage"))
        and v260.odds(favourite) < KNOCKOUT_FAVOURITE_ODDS_MAX
        and draw_probability >= KNOCKOUT_DRAW_PROBABILITY_MIN
    )


def _market_rows(record: dict[str, Any], codes: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in codes:
        rows.extend(v260.markets(record, code))
    return rows


def _same_selection(left: Any, right: Any) -> bool:
    return str(left).strip().casefold() == str(right).strip().casefold()


def qualify_row(record: dict[str, Any], favourite_name: str) -> dict[str, Any] | None:
    candidates = [
        row
        for row in _market_rows(record, ("QUALIFY", "TO_QUALIFY"))
        if _same_selection(row.get("selection"), favourite_name)
        and v260.odds(row) > 1.0
    ]
    return max(candidates, key=v260.odds) if candidates else None


def explicit_fair_probability(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    for key in ("model_probability", "fair_probability", "estimated_probability"):
        raw = row.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 1.0:
            value /= 100.0
        if 0.0 < value <= 1.0:
            return value
    return None


def expected_value(row: dict[str, Any] | None) -> float | None:
    probability = explicit_fair_probability(row)
    if row is None or probability is None:
        return None
    return round(probability * v260.odds(row) - 1.0, 6)


def evaluate_qualification_market(
    record: dict[str, Any],
    favourite_name: str,
) -> tuple[dict[str, Any] | None, float | None, str]:
    row = qualify_row(record, favourite_name)
    if row is None:
        return None, None, "PASS_MARKET_MISMATCH"

    edge = expected_value(row)
    if edge is None or edge < MIN_EXPECTED_VALUE:
        return row, edge, "PASS_NO_VALUE"

    return row, edge, "QUALIFY_VALUE_ACCEPTED"


def _from_base(base: v270.ResearchRecommendation) -> V271Recommendation:
    return V271Recommendation(
        match_id=base.match_id,
        match=base.match,
        date=base.date,
        stage=base.stage,
        market=base.market,
        selection=base.selection,
        price=base.price,
        price_type=base.price_type,
        signal_score=base.signal_score,
        cpi=base.cpi,
        classification=base.classification,
        stake_class=base.stake_class,
        stake_pct=base.stake_pct,
        red_flags=list(base.red_flags),
        consensus_count=base.consensus_count,
        rationale=base.rationale,
        ht_selection=base.ht_selection,
        ou_selection=base.ou_selection,
        btts_selection=base.btts_selection,
        primary_ah_selection=base.primary_ah_selection,
        primary_ah_movement=base.primary_ah_movement,
        alternate_ah_observation=base.alternate_ah_observation,
    )


def make_recommendation(record: dict[str, Any]) -> V271Recommendation:
    base = v270.make_recommendation(record)
    recommendation = _from_base(base)
    favourite = v260.closing_favourite(record)
    favourite_name = str(favourite.get("selection")) if favourite else "PASS"
    draw_probability = normalized_draw_probability(record)

    recommendation.normalized_draw_probability = draw_probability
    recommendation.draw_risk_band = draw_risk_band(draw_probability)
    recommendation.steam_saturation = steam_saturation(favourite)
    recommendation.decision_code = (
        "RESEARCH_BET_1X2" if recommendation.stake_pct > 0 else "PASS_BASE_MODEL"
    )

    if recommendation.steam_saturation:
        recommendation.rationale += "; steam saturation observation"

    # Only intervene after the inherited signal/admission gates would place a bet.
    if recommendation.stake_pct <= 0:
        return recommendation

    # Temporary research stake cap for all knockout-stage bets.
    if is_knockout_stage(record.get("stage")):
        recommendation.stake_pct = min(recommendation.stake_pct, KNOCKOUT_STAKE_CAP)
        if recommendation.stake_class == "Strong":
            recommendation.stake_class = "KnockoutMicro"

    if not knockout_guard_applies(record, favourite, draw_probability):
        recommendation.decision_code = "RESEARCH_BET_1X2"
        return recommendation

    recommendation.knockout_guard_triggered = True
    recommendation.knockout_guard_reason = (
        f"knockout favourite {v260.odds(favourite):.2f} below "
        f"{KNOCKOUT_FAVOURITE_ODDS_MAX:.2f} with normalized draw risk "
        f"{draw_probability:.1%} at or above {KNOCKOUT_DRAW_PROBABILITY_MIN:.0%}"
    )

    row, edge, decision = evaluate_qualification_market(record, favourite_name)
    recommendation.expected_value = edge

    if decision == "QUALIFY_VALUE_ACCEPTED" and row is not None:
        recommendation.market = QUALIFY_MARKET
        recommendation.selection = favourite_name
        recommendation.price = round(v260.odds(row), 3)
        recommendation.classification = "KnockoutGuard"
        recommendation.stake_class = "KnockoutMicro"
        recommendation.stake_pct = min(recommendation.stake_pct, KNOCKOUT_STAKE_CAP)
        recommendation.decision_code = "RESEARCH_BET_QUALIFY"
        recommendation.rationale += (
            f"; knockout guard redirected regulation 1X2 to qualification market; "
            f"explicit expected value {edge:.2%}"
        )
        return recommendation

    recommendation.market = "PASS"
    recommendation.selection = "PASS"
    recommendation.price = 0.0
    recommendation.classification = "Avoid"
    recommendation.stake_class = "PASS"
    recommendation.stake_pct = 0.0
    recommendation.decision_code = decision
    recommendation.rationale += (
        f"; knockout guard blocked regulation 1X2; {decision}"
    )
    return recommendation


def settle_qualification(record: dict[str, Any], selection: str | None) -> str:
    if not selection:
        return "Unknown"

    row = qualify_row(record, selection)
    if row is not None:
        normalized = integrity.normalize_result(row.get("result"))
        if normalized:
            return normalized

    qualifier = record.get("qualifier")
    if qualifier is None:
        return "Unknown"
    return "Win" if _same_selection(selection, qualifier) else "Loss"


def require_research_settled(
    record: dict[str, Any],
    market: str,
    selection: str | None,
) -> str:
    if market == REGULATION_MARKET:
        return integrity.require_settled(record, REGULATION_MARKET, selection)
    if market == QUALIFY_MARKET:
        outcome = settle_qualification(record, selection)
        if outcome not in integrity.SETTLED_OUTCOMES:
            raise ValueError(
                "Unresolved staked research settlement: "
                f"match_id={record.get('match_id', '')!r}, market={market!r}, "
                f"selection={selection!r}, outcome={outcome!r}"
            )
        return outcome
    raise ValueError(f"Unsupported staked research market: {market!r}")


def replay(
    records: list[dict[str, Any]],
    starting_bankroll: float = 1000.0,
) -> dict[str, Any]:
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
            else require_research_settled(
                record, recommendation.market, recommendation.selection
            )
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
        current_drawdown = round((peak - bankroll) / peak * 100, 2) if peak else 0.0
        max_drawdown = max(max_drawdown, current_drawdown)

        favourite = v260.closing_favourite(record)
        favourite_name = str(favourite.get("selection")) if favourite else None
        base_audit = v270.audit_decision(
            record,
            favourite_name,
            cpi=recommendation.cpi,
            consensus=recommendation.consensus_count,
            flags=recommendation.red_flags,
            stake_pct=recommendation.stake_pct,
        )
        decision_status = recommendation.decision_code
        decision_reasons = list(base_audit["decision_reasons"])
        if recommendation.knockout_guard_triggered:
            decision_reasons.append(recommendation.knockout_guard_reason)
        if recommendation.decision_code in {"PASS_MARKET_MISMATCH", "PASS_NO_VALUE"}:
            decision_reasons.append(recommendation.decision_code)

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
            "data_status": base_audit["data_status"],
            "available_consensus_channels": base_audit["available_consensus_channels"],
            "missing_channels": "|".join(base_audit["missing_channels"]),
            "decision_status": decision_status,
            "decision_reasons": "|".join(decision_reasons),
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
            "normalized_draw_probability": recommendation.normalized_draw_probability,
            "draw_risk_band": recommendation.draw_risk_band,
            "knockout_guard_triggered": recommendation.knockout_guard_triggered,
            "knockout_guard_reason": recommendation.knockout_guard_reason,
            "expected_value": recommendation.expected_value,
            "steam_saturation": recommendation.steam_saturation,
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
            "score_ft_90": record.get("score", {}).get(
                "ft_90", record.get("score", {}).get("ft", "")
            ),
            "qualifier": record.get("qualifier", ""),
            "rationale": recommendation.rationale,
        })

    bets = wins + losses + pushes
    net_profit = round(bankroll - starting_bankroll, 2)
    decision_status_counts: dict[str, int] = {}
    guard_trigger_count = 0
    guard_redirect_count = 0
    guard_pass_count = 0
    for row in rows:
        code = str(row["decision_status"])
        decision_status_counts[code] = decision_status_counts.get(code, 0) + 1
        if row["knockout_guard_triggered"]:
            guard_trigger_count += 1
        if code == "RESEARCH_BET_QUALIFY":
            guard_redirect_count += 1
        if code in {"PASS_MARKET_MISMATCH", "PASS_NO_VALUE"}:
            guard_pass_count += 1

    return {
        "engine_version": ENGINE_VERSION,
        "research_only": RESEARCH_ONLY,
        "production_engine_unchanged": PRODUCTION_ENGINE,
        "chronological_order": "date_asc,match_id_asc",
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
        "knockout_guard_trigger_count": guard_trigger_count,
        "knockout_guard_redirect_count": guard_redirect_count,
        "knockout_guard_pass_count": guard_pass_count,
        "decision_status_counts": decision_status_counts,
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in result.items() if key != "rows"}
    (out_dir / "spwin_v2_7_1_research_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (out_dir / "spwin_v2_7_1_research_rows.json").write_text(
        json.dumps(result["rows"], indent=2), encoding="utf-8"
    )
    if result["rows"]:
        with (out_dir / "spwin_v2_7_1_research.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(result["rows"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run SPWIN v2.7.1 knockout market guard research replay."
    )
    parser.add_argument("--gold-dir", default="data/world_cup_2026/gold")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument(
        "--out-dir",
        default="reports/research/spwin_v2_7_1_knockout_market_guard",
    )
    args = parser.parse_args()

    records = v260.load_gold_records(Path(args.gold_dir))
    result = replay(records, starting_bankroll=args.bankroll)
    write_outputs(result, Path(args.out_dir))
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
