# SPWIN Atlas Schema v1

SPWIN Atlas stores World Cup 2026 match records in structured, replayable form.

## Core principles

1. Preserve raw user-provided odds snapshots.
2. Normalize every match into structured records for backtesting.
3. Never overwrite completed historical records. Apply corrections as new versions.
4. Only Gold and Platinum records are eligible for official production replay.

## Quality grades

| Grade | Requirement | Production replay |
|---|---|---|
| Bronze | Final score plus partial/core odds | No |
| Silver | Bronze plus HT markets/results | No |
| Gold | Full Singapore Pools/SGOdds market snapshot with HT/FT result | Yes |
| Platinum | Gold plus confirmed lineups, live stats, xG, timeline, referee, cards, substitutions | Yes |

## Normalized match JSON fields

```json
{
  "schema_version": "1.0",
  "match_id": "WC2026-R32-COD-UZB",
  "source_event_id": "unknown",
  "match": "Congo DR vs Uzbekistan",
  "date": "2026-06-28",
  "competition": "FIFA World Cup 2026",
  "stage": "Round of 32",
  "status": "COMPLETED",
  "quality_grade": "Gold",
  "immutable": true,
  "score": {
    "ht": "0-1",
    "ft": "3-1"
  },
  "markets": [
    {
      "market_code": "1X2",
      "market_name": "Full Time 1X2",
      "selection": "Congo DR",
      "team": "Congo DR",
      "line": null,
      "opening_odds": 1.72,
      "closing_odds": 1.45,
      "movement_pct": -15.7,
      "result": "Win"
    }
  ],
  "derived_features": {
    "favorite": "Congo DR",
    "winner_market_signal": "Congo DR",
    "goals_market_signal": "Under 2.5",
    "btts_signal": "No",
    "market_conflict": true,
    "notes": "Winner markets supported Congo DR; goals/BTTS markets were wrong."
  },
  "provenance": {
    "source": "User-provided SGOdds past odds text",
    "archived_by": "ChatGPT",
    "archive_policy": "Rule 7 immutable historical data"
  }
}
```

## Market codes

| Code | Meaning |
|---|---|
| AH | Asian Handicap |
| HT_AH | Half Time Asian Handicap |
| 1X2 | Full Time 1X2 |
| OU | Over/Under |
| BTTS | Both Teams To Score |
| HTFT | Half Time / Full Time |
| PTS | Pick The Score |
| TG | Total Goals |
| FG | Team To Score First Goal |
| OE | Odd/Even |
| HT_1X2 | Half Time 1X2 |
| HT_PTS | Half Time Pick The Score |
| HT_OU | Half Time Over/Under |
| HT_OE | Half Time Odd/Even |
| HT_TG | Half Time Total Goals |
| HT_FG | Half Time Team To Score First Goal |
| HT_BTTS | Half Time Both Teams To Score |
```

## Immutable update rule

Completed match records must not be overwritten. If a correction or enrichment is needed, create a new file with a higher version suffix, for example:

```text
WC2026-R32-COD-UZB_v1.0.json
WC2026-R32-COD-UZB_v1.1_correction.json
WC2026-R32-COD-UZB_v1.2_enriched.json
```
