#!/usr/bin/env python3
"""Observation-only labels for the SPWIN forward trial.

These labels are descriptive metadata. They must never change a v2.6.1 or A1
recommendation, qualification decision, selection, or stake.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spwin_engine import v260

PRICE_ZONE = "PRICE_ZONE_1.20_1.39"
OUTSIDE_PRICE_ZONE = "OUTSIDE_PRICE_ZONE"
PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"

CONTROLLED_BOTH = "CONTROLLED_BOTH"
CONTROLLED_1X2_ONLY = "CONTROLLED_1X2_ONLY"
CONTROLLED_AH_ONLY = "CONTROLLED_AH_ONLY"
NO_CONTROLLED_STEAM = "NO_CONTROLLED_STEAM"
STEAM_UNAVAILABLE = "STEAM_UNAVAILABLE"

DRAW_MILD_SHORTENING = "MILD_DRAW_SHORTENING"
DRAW_STRONG_COMPRESSION = "STRONG_DRAW_COMPRESSION"
DRAW_NO_SHORTENING = "NO_DRAW_SHORTENING"
DRAW_UNAVAILABLE = "DRAW_UNAVAILABLE"


@dataclass(frozen=True)
class ObservationLabels:
    price_zone: str
    controlled_steam: str
    draw_structure: str
    favourite_odds: float | None
    one_x_two_move_pct: float | None
    ah_move_pct: float | None
    draw_move_pct: float | None


def _number(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def price_zone_label(favourite_odds: float | None) -> str:
    value = _number(favourite_odds)
    if value is None:
        return PRICE_UNAVAILABLE
    if 1.20 <= value <= 1.39:
        return PRICE_ZONE
    return OUTSIDE_PRICE_ZONE


def _is_controlled_shortening(value: float | None) -> bool:
    number = _number(value)
    return number is not None and -12.0 <= number <= -6.0


def controlled_steam_label(
    one_x_two_move_pct: float | None,
    ah_move_pct: float | None,
) -> str:
    one_x_two = _number(one_x_two_move_pct)
    ah = _number(ah_move_pct)
    if one_x_two is None and ah is None:
        return STEAM_UNAVAILABLE

    one_x_two_controlled = _is_controlled_shortening(one_x_two)
    ah_controlled = _is_controlled_shortening(ah)
    if one_x_two_controlled and ah_controlled:
        return CONTROLLED_BOTH
    if one_x_two_controlled:
        return CONTROLLED_1X2_ONLY
    if ah_controlled:
        return CONTROLLED_AH_ONLY
    return NO_CONTROLLED_STEAM


def draw_structure_label(draw_move_pct: float | None) -> str:
    value = _number(draw_move_pct)
    if value is None:
        return DRAW_UNAVAILABLE
    if value <= -10.0:
        return DRAW_STRONG_COMPRESSION
    if value < 0.0:
        return DRAW_MILD_SHORTENING
    return DRAW_NO_SHORTENING


def derive_from_values(
    *,
    favourite_odds: float | None,
    one_x_two_move_pct: float | None,
    ah_move_pct: float | None,
    draw_move_pct: float | None,
) -> ObservationLabels:
    """Derive labels from captured pre-match values without changing inputs."""
    return ObservationLabels(
        price_zone=price_zone_label(favourite_odds),
        controlled_steam=controlled_steam_label(one_x_two_move_pct, ah_move_pct),
        draw_structure=draw_structure_label(draw_move_pct),
        favourite_odds=_number(favourite_odds),
        one_x_two_move_pct=_number(one_x_two_move_pct),
        ah_move_pct=_number(ah_move_pct),
        draw_move_pct=_number(draw_move_pct),
    )


def derive_from_record(record: dict[str, Any]) -> ObservationLabels:
    """Derive labels from a SPWIN record. The record is never mutated."""
    favourite_row = v260.closing_favourite(record)
    favourite = str(favourite_row.get("selection")) if favourite_row else None
    ah_row = v260.favourite_ah(record, favourite)
    draw_row = v260.draw_row(record)
    return derive_from_values(
        favourite_odds=v260.odds(favourite_row) if favourite_row else None,
        one_x_two_move_pct=v260.move(favourite_row) if favourite_row else None,
        ah_move_pct=v260.move(ah_row) if ah_row else None,
        draw_move_pct=v260.move(draw_row) if draw_row else None,
    )
