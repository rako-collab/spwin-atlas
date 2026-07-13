# SPWIN v2.7.1 Research — Argentina vs Switzerland 99-Record Replay

## Gold record

- Match: Argentina vs Switzerland
- Event: FIFA World Cup 2026 quarter-final
- SGOdds event id: 140317
- Half-time score: 1-0
- Regulation score: 1-1
- After extra time: 3-1
- Qualifier: Argentina
- Active Gold count: 99

The record deliberately omits `score.ft` and stores `score.ft_90` plus `score.aet` so regulation-time 1X2 settlement cannot use the extra-time result.

## Closing signals

- Argentina 1X2: 1.67 to 1.37 (-18.0%)
- Draw: 3.30 to 3.90 (+18.2%)
- Switzerland 1X2: 4.50 to 7.00 (+55.6%)
- Argentina main AH -0.75: 1.91 to 1.72 (-9.9%)
- Argentina alternative -1.5: 3.15 to 2.60 (-17.5%)
- Argentina HT 1X2: 2.30 to 2.03 (-11.7%)
- Argentina first goal: 1.55 to 1.42 (-8.4%)
- Normalized closing draw probability: 22.7074%

## Chronological replay

| Engine | Bets | W-L | Final bankroll | Net | ROI | Max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| v2.6.1 production baseline | 6 | 5-1 | 1001.50 | +1.50 | +0.15% | 1.25% |
| v2.7 correctness research | 4 | 3-1 | 993.43 | -6.57 | -0.66% | 1.25% |
| v2.7.1 knockout guard | 3 | 3-0 | 1006.01 | +6.01 | +0.60% | 0.00% |

## Argentina–Switzerland decision

- v2.6.1: Argentina regulation 1X2, loss.
- v2.7: Argentina regulation 1X2, loss.
- v2.7.1: `PASS_MARKET_MISMATCH`.

The v2.7.1 guard triggered because Argentina closed below 1.50 in a knockout match while normalized draw risk remained above 20%. No explicitly valued qualification market was stored, so the engine passed rather than substituting an unvalidated market.

## Research conclusion

The new Gold record supplies the first historical guard-trigger case. On the 99-record replay, v2.7.1 removed one losing regulation-time bet, improved net profit by 12.58 units versus v2.7, and reduced maximum drawdown by 1.25 percentage points. This is one case only and is not sufficient for production promotion.
