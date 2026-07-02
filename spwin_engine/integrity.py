#!/usr/bin/env python3
"""Replay-integrity helpers shared by SPWIN engines.

This module does not alter recommendation logic. It provides:
- normalized settlement labels,
- score-derived settlement fallbacks,
- fail-closed handling for unresolved staked bets,
- market-completeness and PASS audit metadata.
"""

from __future__ import annotations

from typing import Any
import re

SETTLED_OUTCOMES = {"Win", "Loss", "Push"}

_RESULT_ALIASES = {
    "win": "Win",
    "won": "Win",
    "loss": "Loss",
    "lose": "Loss",
    "lost": "Loss",
    "push": "Push",
    "void": "Push",
    "refund": "Push",
    "refunded": "Push",
}


def _market_rows(record: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [row for row in record.get("markets", []) if row.get("market_code") == code]


def normalize_result(value: Any) -> str | None:
    """Return canonical Win/Loss/Push for recognized result labels."""
    if value is None:
        return None
    return _RESULT_ALIASES.get(str(value).strip().casefold())


def _parse_score_value(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", str(value))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def score(record: dict[str, Any], period: str = "FT") -> tuple[int, int] | None:
    score_obj = record.get("score", {}) or {}
    if period.upper() == "HT":
        return _parse_score_value(score_obj.get("ht"))
    return _parse_score_value(score_obj.get("ft", score_obj.get("ft_90")))


def teams(record: dict[str, Any]) -> tuple[str, str] | None:
    match_name = str(record.get("match", ""))
    if " vs " not in match_name:
        return None
    home, away = match_name.split(" vs ", 1)
    home, away = home.strip(), away.strip()
    return (home, away) if home and away else None


def _same_selection(left: Any, right: Any) -> bool:
    return str(left).strip().casefold() == str(right).strip().casefold()


def _winner_selection(record: dict[str, Any], period: str) -> str | None:
    parsed_score = score(record, period)
    parsed_teams = teams(record)
    if not parsed_score or not parsed_teams:
        return None
    home_goals, away_goals = parsed_score
    home, away = parsed_teams
    if home_goals > away_goals:
        return home
    if away_goals > home_goals:
        return away
    return "Draw"


def _extract_ou(selection: str) -> tuple[str, float] | None:
    match = re.search(r"\b(Over|Under)\s*([0-9]+(?:\.[0-9]+)?)\b", selection, re.I)
    if not match:
        return None
    return match.group(1).title(), float(match.group(2))


def derive_settlement(record: dict[str, Any], code: str, selection: str) -> str:
    """Derive settlement from stored scores for deterministic markets."""
    code = str(code)
    selection = str(selection)

    if code in {"1X2", "HT_1X2"}:
        winner = _winner_selection(record, "HT" if code == "HT_1X2" else "FT")
        if winner is None:
            return "Unknown"
        return "Win" if _same_selection(selection, winner) else "Loss"

    if code in {"BTTS", "HT_BTTS"}:
        parsed_score = score(record, "HT" if code == "HT_BTTS" else "FT")
        if not parsed_score:
            return "Unknown"
        btts = parsed_score[0] > 0 and parsed_score[1] > 0
        normalized_selection = selection.strip().casefold()
        if normalized_selection not in {"yes", "no"}:
            return "Unknown"
        selected_yes = normalized_selection == "yes"
        return "Win" if selected_yes == btts else "Loss"

    if code in {"OU", "HT_OU"}:
        parsed_score = score(record, "HT" if code == "HT_OU" else "FT")
        parsed_ou = _extract_ou(selection)
        if not parsed_score or not parsed_ou:
            return "Unknown"
        direction, line = parsed_ou
        goals = sum(parsed_score)
        if goals == line:
            return "Push"
        won = goals > line if direction == "Over" else goals < line
        return "Win" if won else "Loss"

    if code in {"PTS", "HT_PTS"}:
        parsed_score = score(record, "HT" if code == "HT_PTS" else "FT")
        selected_score = _parse_score_value(selection)
        if not parsed_score or not selected_score:
            return "Unknown"
        return "Win" if parsed_score == selected_score else "Loss"

    return "Unknown"


def settle(record: dict[str, Any], code: str, selection: str | None) -> str:
    """Settle a selection safely, normalizing labels and falling back to scores."""
    if not selection:
        return "Unknown"

    matched_row: dict[str, Any] | None = None
    for row in _market_rows(record, code):
        if _same_selection(row.get("selection"), selection):
            matched_row = row
            break

    if matched_row is None:
        return "Unknown"

    normalized = normalize_result(matched_row.get("result"))
    if normalized:
        return normalized

    return derive_settlement(record, code, str(selection))


def require_settled(record: dict[str, Any], code: str, selection: str | None) -> str:
    """Fail closed when a staked recommendation cannot be settled."""
    outcome = settle(record, code, selection)
    if outcome not in SETTLED_OUTCOMES:
        raise ValueError(
            "Unresolved staked bet settlement: "
            f"match_id={record.get('match_id', '')!r}, market={code!r}, "
            f"selection={selection!r}, outcome={outcome!r}"
        )
    return outcome


def assess_market_completeness(record: dict[str, Any], favourite: str | None) -> dict[str, Any]:
    """Assess whether enough independent market channels exist for 3/4 consensus."""
    one_x_two = [row for row in _market_rows(record, "1X2") if row.get("closing_odds")]
    team_rows = [row for row in one_x_two if str(row.get("selection", "")).casefold() != "draw"]
    has_draw = any(str(row.get("selection", "")).casefold() == "draw" for row in one_x_two)
    full_1x2 = len(team_rows) >= 2 and has_draw

    favourite_folded = str(favourite or "").strip().casefold()
    has_ah = False
    has_fg = False
    if favourite_folded:
        for code in ("AH", "HANDICAP_ALT"):
            has_ah = has_ah or any(
                favourite_folded in str(row.get("selection", "")).casefold()
                for row in _market_rows(record, code)
            )
        has_fg = any(
            _same_selection(row.get("selection"), favourite)
            for row in _market_rows(record, "FG")
        )

    channels = {
        "1X2": bool(favourite),
        "AH": has_ah,
        "HT_1X2": bool(_market_rows(record, "HT_1X2")),
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
    cpi_threshold: float,
) -> dict[str, Any]:
    """Return explicit data and decision classifications without changing the bet."""
    completeness = assess_market_completeness(record, favourite)
    reasons: list[str] = []

    if stake_pct > 0:
        status = "BET"
        reasons.append("admission gates passed")
    else:
        if not completeness["consensus_capable"]:
            reasons.append("incomplete market coverage")
        if flags:
            reasons.append("red flags: " + ", ".join(flags))
        if consensus < 3:
            reasons.append(f"consensus {consensus}/4 below 3/4")
        if cpi < cpi_threshold:
            reasons.append(f"CPI {cpi:.1f} below {cpi_threshold:.1f}")

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
    }
