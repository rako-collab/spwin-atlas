# World Cup 2026 — 82-Match Pattern Audit

Date: 2026-07-03 SGT

## Status

Diagnostic research only. No SPWIN v2.6.1 or A1 thresholds, staking, or Gold records are changed.

## Dataset

- 82 active completed Gold records
- 72 group-stage matches
- 10 knockout matches
- 80 matches with a usable complete favourite identity
- 25 consensus-capable records under the current completeness definition
- 57 partial-market records

## Overall match profile

| Metric | Result |
|---|---:|
| Favourite wins in 90 minutes | 53 of 80 (66.25%) |
| Draws in 90 minutes | 21 of 80 (26.25%) |
| Outright favourite losses | 6 of 80 (7.50%) |
| Average goals | 2.93 |
| Over 2.5 | 45 of 82 (54.88%) |
| BTTS Yes | 45 of 82 (54.88%) |
| Halftime draw | 31 of 82 (37.80%) |
| Halftime 0–0 | 23 of 82 (28.05%) |

The tournament did not show a strong global Over/Under or BTTS bias. Both finished almost exactly 55/45.

## Pattern 1 — Favourite price sweet spot

The cleanest pre-match price band was favourite odds from 1.20 to 1.39.

| Favourite closing odds | Matches | Favourite record | Win rate | Flat ROI |
|---|---:|---:|---:|---:|
| Below 1.20 | 17 | 12–5–0 | 70.59% | -23.06% |
| 1.20–1.39 | 20 | 17–3–0 | 85.00% | +8.95% |
| 1.40–1.59 | 15 | 9–3–3 | 60.00% | -12.33% |
| 1.60–1.79 | 14 | 8–4–2 | 57.14% | -4.21% |
| 1.80–2.00 | 8 | 4–4–0 | 50.00% | -6.62% |

Interpretation:

- Ultra-short favourites won often but did not win often enough to justify the tiny prices.
- The 1.20–1.39 range offered the best balance between win probability and payout.
- This supports retaining the ultra-short-price veto below 1.20.

Within the 1.20–1.39 band, matches without an existing red flag went 14–3 and returned approximately +5.7% at flat stake. This is a useful screening zone, not a standalone betting rule.

## Pattern 2 — Moderate movement was better than extreme movement

More shortening was not automatically better.

### Favourite 1X2 movement

| Movement | Matches | Favourite win rate | Flat ROI |
|---|---:|---:|---:|
| 12% or more shortening | 14 | 64.29% | -9.79% |
| 8%–12% shortening | 12 | 58.33% | -16.92% |
| 6%–8% shortening | 9 | 88.89% | +23.00% |
| Less than 6% shortening | 18 | 61.11% | -18.72% |

### Favourite Asian Handicap movement

| Movement | Matches | Favourite win rate | Flat ROI |
|---|---:|---:|---:|
| 12% or more shortening | 21 | 66.67% | -10.38% |
| 8%–12% shortening | 7 | 85.71% | +22.43% |
| Neutral/supportive: -8% to +5% | 37 | 62.16% | -1.35% |

Interpretation:

- Moderate, controlled support performed better than very aggressive steam.
- Extreme movement may mean the useful price has already disappeared, or that the market is reacting to uncertainty rather than revealing a clean edge.
- This is consistent with A1's design: strong but not extreme movement, with micro staking.

The favourable buckets are still small, so these boundaries should remain fixed during the forward trial rather than being tuned again.

## Pattern 3 — Mild draw shortening was not a warning sign

| Draw movement | Settled matches | Favourite wins | Win rate | Flat ROI |
|---|---:|---:|---:|---:|
| Strong compression: 10%+ | 6 | 4 | 66.67% | +11.33% |
| Mild shortening: 0%–10% | 18 | 15 | 83.33% | +36.28% |
| Draw odds drifted | 48 | 26 | 54.17% | -29.25% |

Interpretation:

- Mild draw shortening often occurred while the favourite still won.
- It may represent the market moving away from the outsider rather than directly predicting a draw.
- Strong draw compression had only six cases and should remain a caution signal, but this sample does not prove it should always be an automatic veto.
- The current frozen production rule must not be changed during the forward trial; this belongs in a future isolated red-flag study.

## Pattern 4 — High consensus worked, but the sample is tiny

| Consensus | Matches | Favourite record | Flat ROI |
|---|---:|---:|---:|
| 0 | 42 settled | 27 wins | -5.10% |
| 1 | 16 | 11 wins | -3.31% |
| 2 | 16 | 9 wins | -17.88% |
| 3 | 4 | 4 wins | +30.00% |
| 4 | 2 | 2 wins | +14.00% |

The six matches reaching at least 3/4 consensus all won. This supports the conservative architecture, but six matches are not enough to estimate the true future win rate.

## Pattern 5 — A1 remains promising

The approved A1 lane selected seven historical matches:

- 6 wins
- 1 loss
- 85.71% hit rate
- +26.43% flat-stake ROI

This is consistent with the wider audit, but it was discovered on the same historical sample. It remains a 0.25% forward-trial lane, not a full production rule.

## Pattern 6 — Halftime 0–0 was a strong live-under state

| Halftime state | Matches | Average final goals | Over 2.5 | BTTS Yes |
|---|---:|---:|---:|---:|
| 0–0 | 23 | 1.52 | 26.09% | 30.43% |
| Any other halftime score | 59 | 3.47 | 66.10% | 64.41% |

This was one of the strongest descriptive patterns in the dataset.

A 0–0 halftime score was followed by Under 2.5 in 17 of 23 matches and BTTS No in 16 of 23. It can inform a future in-play module, but it is not a pre-match signal.

More generally, when the match was level at halftime, the favourite won only 13 of the 29 matches with a usable favourite (44.83%). When the match was not level at halftime, favourites won 40 of 51 (78.43%).

## Pattern 7 — Knockout matches were more decisive early, but sample is limited

The 10 completed knockout matches produced:

- seven favourite wins in 90 minutes;
- three draws in 90 minutes;
- no outright underdog win in 90 minutes;
- only two halftime draws (20%), compared with 40.28% in the group stage.

This is worth monitoring, but ten matches are insufficient for a knockout-specific engine adjustment.

## Weak or absent patterns

### Over/Under movement

The strongest-shortening OU side hit 41 of 67 settled cases (61.19%). When the movement was at least 5%, accuracy fell to 23 of 41 (56.10%). Stronger movement did not improve prediction quality.

### BTTS movement

The strongest-shortening BTTS side hit 39 of 75 cases (52.00%). With at least 5% shortening it hit only 17 of 36 (47.22%). This is effectively noise in the current sample.

Neither OU nor BTTS movement should become a standalone admission gate based on these records.

## Data-quality warning — historical HT market rows

The archived HT 1X2 data often contains only one selection, and that selection is frequently the actual halftime winner or draw. For example, the Argentina vs Austria record stores only the Argentina HT selection, which was also the actual halftime result.

Across the records containing an HT row, this one-sided selection matched the halftime result in 35 of 37 cases. That is likely archive/selection bias, not genuine predictive accuracy.

Therefore:

- do not use the 35/37 figure as an edge;
- do not optimise HT thresholds from these historical rows;
- future Gold records should capture the full HT home/draw/away market whenever possible;
- actual halftime score patterns remain valid because they come from match results, not the archived selected market row.

## Practical implications for the forward trial

1. Keep the A1 rule and 0.25% stake unchanged.
2. Continue rejecting favourites below 1.20 for value reasons.
3. Treat 1.20–1.39 as the most interesting price zone for further observation.
4. Prefer controlled 6%–12% movement over extreme steam when comparing research candidates.
5. Do not use OU or BTTS movement alone.
6. Record full three-way HT markets going forward.
7. Study draw compression separately after the tournament rather than changing the frozen red flag now.

## Statistical caution

Several patterns were selected after inspecting many possible groupings. Wilson intervals remain wide for the smaller buckets, and none of these findings should be treated as a guaranteed future edge. The forward ledger is the unbiased test.
