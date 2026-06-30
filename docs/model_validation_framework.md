# SPWIN Model Validation Framework

The Model Validation Framework measures SPWIN by long-term betting quality, not simple prediction win/loss.

## Objectives

- Track ROI and yield by market.
- Track closing line value (CLV).
- Measure probability calibration.
- Evaluate performance by grade band.
- Evaluate performance by favourite odds band.
- Evaluate performance by tournament stage.
- Identify whether PASS decisions protected bankroll.

## Core Metrics

### ROI

```text
ROI = total_profit_loss_units / total_staked_units
```

### Yield

```text
Yield = total_profit_loss_units / number_of_bets
```

### CLV

CLV compares odds taken versus closing odds.

For decimal odds:

```text
CLV = odds_taken - closing_odds
```

Positive CLV means SPWIN beat the closing line.

### Calibration

Calibration compares predicted probability versus actual hit rate.

Example:

| Confidence Band | Expected Win Rate | Actual Win Rate |
|---|---:|---:|
| 60-69% | 65% | 63% |
| 70-79% | 75% | 76% |
| 80-89% | 85% | 82% |

### Grade Performance

Track each grade independently:

- A+
- A
- B
- C
- PASS

A PASS is considered correct when the match shows poor value, high trap risk, or a losing favourite profile.

## Required Inputs

Each SPWIN recommendation should record:

- match_id
- engine_version
- market
- selection
- odds_taken
- closing_odds
- stake_units
- predicted_probability
- grade
- confidence_band
- result
- profit_loss_units
- clv
- stage
- favourite_closing_odds_band
- pass_reason, where applicable

## Validation Outputs

The framework produces:

- `analytics/model_validation_summary.csv`
- `analytics/grade_performance.csv`
- `analytics/clv_tracker.csv`
- `analytics/calibration_report.csv`
- `analytics/roi_by_market.csv`
- `analytics/pass_performance.csv`

## Design Principle

SPWIN should only be upgraded when validation evidence shows improved long-term decision quality.
