# SPWIN v2.7.1 Research — Knockout Market Guard

## Status

- Research only.
- Production `spwin_engine/v261.py` is unchanged.
- The approved Argentina vs Switzerland completed Gold record is active in the research branch.
- The authoritative research index contains 99 records.
- Not approved for live use; one historical guard-trigger case is insufficient for promotion.

## Failure mode addressed

A strong favourite signal in a knockout match was automatically converted into a 90-minute `1X2` bet. This ignored the possibility that the favourite could qualify after a regulation-time draw.

The guard separates:

1. signal admission;
2. market suitability;
3. qualification-market value;
4. settlement at 90 minutes versus qualification.

## Research rule

After the inherited v2.7 signal gates admit a bet, block regulation `1X2` when all are true:

- the stage is a knockout stage;
- favourite closing odds are below `1.50`;
- normalized no-vig draw probability is at least `20%`.

When blocked:

- use `QUALIFY` only when an explicit fair/model probability is stored;
- require expected value of at least `2%`;
- otherwise return `PASS_MARKET_MISMATCH` or `PASS_NO_VALUE`.

All knockout research stakes are capped at `0.75%`.

## Settlement

- `1X2` uses `score.ft_90` when present and therefore excludes extra time and penalties.
- `QUALIFY` uses the explicit market result when present, otherwise the record's `qualifier`.
- unresolved staked markets fail closed.

## Observations

The engine records:

- normalized draw probability;
- draw-risk band;
- guard trigger and reason;
- qualification expected value;
- steam-saturation observation;
- decision code.

## Validation

Regression tests cover:

- no-vig draw probability;
- blocking an admitted regulation `1X2` bet;
- qualification market value requirement;
- group-stage non-application;
- distinct 90-minute and qualification settlement;
- replay audit output;
- explicit T-10 closing-lock validation without weakening the ordinary T-30 to T-15 rule.

The 99-record chronological replay produced:

| Engine | Bets | W-L | Net | ROI | Max drawdown |
|---|---:|---:|---:|---:|---:|
| v2.6.1 production baseline | 6 | 5-1 | +1.50 | +0.15% | 1.25% |
| v2.7 correctness research | 4 | 3-1 | -6.57 | -0.66% | 1.25% |
| v2.7.1 knockout guard | 3 | 3-0 | +6.01 | +0.60% | 0.00% |

For Argentina vs Switzerland, v2.7.1 triggered the guard and returned `PASS_MARKET_MISMATCH`, while v2.6.1 and v2.7 selected Argentina regulation 1X2 and lost on the 1-1 90-minute score.

The full replay uses the authoritative indexed Gold set in chronological order:

```bash
python tools/run_spwin_v271_research_replay.py \
  --gold-dir data/world_cup_2026/gold \
  --bankroll 1000 \
  --out-dir reports/research/spwin_v2_7_1_knockout_market_guard
```

Promotion remains blocked until more independent guard-trigger cases are accumulated and reviewed.
