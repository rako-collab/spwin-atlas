# SPWIN v2.6.1 Experiment A1 — Incomplete-Data Robustness

Date: 2026-07-02

## Status

Research only. SPWIN v2.6.1 production rules, staking, thresholds, and Gold records are unchanged.

## Objective

Test whether incomplete records containing a complete 1X2 market and Asian Handicap market can support a controlled research lane when HT 1X2 and first-goal channels are missing.

## Eligible pool

The 82-match authoritative Gold set contained:

- 56 `PASS_INCOMPLETE_DATA` decisions
- 34 records with complete 1X2 plus AH only
- 21 records after excluding all existing v2.6.1 red flags

## Parameter grid

The audit tested 504 combinations across:

- Favourite 1X2 shortening: `-6%`, `-8%`, `-10%`, `-12%`, `-14%`
- AH lower boundary: `>-15%`, `>-12%`, `>-10%`, `>-8%`, `>-6%`, `>-4%`
- AH upper boundary: `<=0%`, `<=3%`, `<=5%`, `<=8%`
- Favourite odds bands from `1.20–1.90` through `1.35–2.00`

Forty configurations passed the fixed research guardrails.

## Original A1 rule

```text
1X2 movement <= -8%
AH movement > -8% and <= +5%
Favourite odds 1.30–2.00
No v2.6.1 red flags
```

Result:

| Metric | Result |
|---|---:|
| Bets | 3 |
| Wins | 3 |
| Losses | 0 |
| Flat profit | +1.65 units |
| Flat ROI | +55.00% |
| Chronological blocks | 2 |

This rule failed the minimum five-bet guardrail.

## Strict robust family

The strongest stable family was:

```text
1X2 movement <= -10%
AH movement > -12%
AH movement <= 0% to +8%
Favourite odds 1.20/1.25–2.00
No v2.6.1 red flags
```

Eight nearby configurations selected the same five matches:

| Match | Favourite | Odds | 1X2 movement | AH movement | Result |
|---|---|---:|---:|---:|---|
| Sweden vs Tunisia | Sweden | 1.67 | -10.7% | -10.7% | Win |
| Germany vs Ivory Coast | Germany | 1.33 | -11.3% | -7.9% | Win |
| Tunisia vs Japan | Japan | 1.25 | -15.5% | -11.3% | Win |
| New Zealand vs Egypt | Egypt | 1.37 | -11.6% | -2.9% | Win |
| Norway vs Senegal | Norway | 1.95 | -11.4% | -1.7% | Win |

| Metric | Result |
|---|---:|
| Bets | 5 |
| Wins | 5 |
| Losses | 0 |
| Flat profit | +2.57 units |
| Flat ROI | +51.40% |
| Maximum drawdown | 0.00 units |
| Chronological blocks covered | 3 |
| Positive blocks | 3 |

## Wider robust family

A wider family used:

```text
1X2 movement <= -6%
AH movement > -12%
AH movement <= 0% to +8%
Favourite odds 1.20/1.25–2.00
No v2.6.1 red flags
```

Result:

| Metric | Result |
|---|---:|
| Bets | 7 |
| Wins | 6 |
| Losses | 1 |
| Flat profit | +1.85 units |
| Flat ROI | +26.43% |
| Maximum drawdown | 1.00 unit |
| Chronological blocks covered | 3 |
| Positive blocks | 2 |

The loss was Iran vs New Zealand. The two additional winners were Mexico vs South Africa and Sweden vs Tunisia.

## Main finding

The important boundary was not simply `2 of 2` agreement. The useful region was:

- decisive 1X2 favourite shortening;
- AH support that did not become more extreme than approximately `-12%`;
- no existing v2.6.1 red flags.

Heavy simultaneous AH movement beyond this boundary included several failures and should not be treated as stronger consensus.

## Decision

Experiment A1 passes initial threshold-neighbourhood and chronological-block checks as a research hypothesis.

It is **not approved for production** because all parameter combinations were inspected on the same 82-match dataset. The next controlled step is an isolated shadow lane using the strict family, with no effect on production recommendations or bankroll.
