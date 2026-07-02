# SPWIN v2.6.1-A1 Experimental Micro Lane

Date: 2026-07-02

## Status

Experimental micro-stake lane. SPWIN v2.6.1 remains the frozen production engine.

## Admission rule

A match qualifies only when all conditions are met:

- v2.6.1 classified the match as `PASS_INCOMPLETE_DATA`;
- complete 1X2 market is present;
- Asian Handicap market is present;
- the available consensus coverage is exactly 1X2 plus AH;
- no v2.6.1 red flags are present;
- favourite closing odds are between 1.20 and 2.00;
- favourite 1X2 movement is `<= -6%`;
- favourite AH movement is `> -12%` and `<= +5%`.

## Staking

- A1 stake: 0.25% of current bankroll.
- A1 performance is reported separately from production.
- Combined reporting is provided for visibility.

## Historical 82-match replay

### A1 lane only

| Metric | Result |
|---|---:|
| Bets | 7 |
| Wins | 6 |
| Losses | 1 |
| Hit rate | 85.71% |
| Starting bankroll | 1000.00 |
| Final bankroll | 1004.63 |
| Net profit | +4.63 |
| Bankroll ROI | +0.46% |
| Return on stakes | +26.43% |
| Maximum drawdown | 0.25% |

### Frozen v2.6.1 plus A1

| Metric | Result |
|---|---:|
| Total bets | 10 |
| Wins | 9 |
| Losses | 1 |
| Hit rate | 90.00% |
| Starting bankroll | 1000.00 |
| Final bankroll | 1010.67 |
| Net profit | +10.67 |
| Bankroll ROI | +1.07% |
| Maximum drawdown | 0.25% |

## A1 historical selections

| Match | Selection | Odds | Result |
|---|---|---:|---|
| Mexico vs South Africa | Mexico | 1.28 | Win |
| Sweden vs Tunisia | Sweden | 1.67 | Win |
| Iran vs New Zealand | Iran | 1.67 | Loss |
| Germany vs Ivory Coast | Germany | 1.33 | Win |
| Tunisia vs Japan | Japan | 1.25 | Win |
| New Zealand vs Egypt | Egypt | 1.37 | Win |
| Norway vs Senegal | Norway | 1.95 | Win |

## Important limitation

The rule was selected after analysis of the same 82-match dataset. Historical performance is therefore exploratory evidence, not an unbiased estimate of future returns.
