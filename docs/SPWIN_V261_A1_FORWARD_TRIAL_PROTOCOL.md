# SPWIN v2.6.1-A1 Forward Trial Protocol

Date adopted: 2026-07-02
Observation labels added: 2026-07-03

## Purpose

Run the A1 incomplete-data micro-stake lane on all remaining World Cup 2026 matches while keeping SPWIN v2.6.1 frozen.

## Engine status

- SPWIN v2.6.1 remains the production engine.
- A1 remains a separate experimental lane.
- No A1 result may change a v2.6.1 recommendation.
- No thresholds may be adjusted during the trial.
- Observation labels are descriptive only and cannot create, remove, upgrade, downgrade, or resize any bet.

## A1 admission rule

A match qualifies only when every condition is satisfied:

1. v2.6.1 returns `PASS_INCOMPLETE_DATA`.
2. The complete 1X2 market is available.
3. The favourite Asian Handicap market is available.
4. HT 1X2 and first-goal channels are unavailable, so coverage is exactly `1X2+AH`.
5. No v2.6.1 red flags are present.
6. Favourite odds are between `1.20` and `2.00` inclusive.
7. Favourite 1X2 movement is `<= -6%`.
8. Favourite AH movement is `> -12%` and `<= +5%`.

If any required input is unavailable or ambiguous, the A1 decision is `PASS`.

## Stake

- A1 stake is fixed at `0.25%` of the current combined bankroll.
- Stake is rounded to two decimal places using the same convention as the existing replay engines.
- A1 bets and production bets are reported separately and together.

## Observation labels

Every remaining match receives three labels after the final pre-match snapshot. These labels are locked with the recommendation but remain analytically separate from all decision and staking logic.

### Price Zone

Derived from the favourite's final 1X2 odds:

- `PRICE_ZONE_1.20_1.39` — favourite odds are from 1.20 through 1.39 inclusive.
- `OUTSIDE_PRICE_ZONE` — favourite odds are available but outside that range.
- `PRICE_UNAVAILABLE` — a usable favourite price is unavailable.

### Controlled Steam

Derived separately from favourite 1X2 and favourite AH movement:

- A market is considered controlled when its movement is from `-6%` through `-12%` inclusive.
- `CONTROLLED_BOTH` — both 1X2 and AH are in the controlled range.
- `CONTROLLED_1X2_ONLY` — only 1X2 is in the controlled range.
- `CONTROLLED_AH_ONLY` — only AH is in the controlled range.
- `NO_CONTROLLED_STEAM` — movement data exists, but neither market is in the controlled range.
- `STEAM_UNAVAILABLE` — both movement inputs are unavailable.

Movement beyond `-12%` is not labelled controlled steam.

### Draw Structure

Derived from the draw's 1X2 movement:

- `MILD_DRAW_SHORTENING` — draw movement is below 0% but greater than `-10%`.
- `STRONG_DRAW_COMPRESSION` — draw movement is `-10%` or stronger.
- `NO_DRAW_SHORTENING` — draw movement is 0% or positive.
- `DRAW_UNAVAILABLE` — draw movement cannot be calculated.

### Observation firewall

- Labels are generated only after v2.6.1 and A1 decisions are calculated.
- Label functions are not imported by either decision engine.
- Labels never change recommendation status, market, selection, odds, classification, confidence, CPI, consensus, red flags, or stake.
- Labels may be reviewed only as forward-trial evidence and may not trigger an additional wager during this tournament.

## Match workflow

### T-90 to T-60 minutes

- Capture confirmed line-ups when available.
- Record the latest favourite 1X2, draw 1X2, and favourite Asian Handicap prices.
- Confirm the opening/reference prices used for movement calculations.
- Record the data source and timestamp in Singapore time.

### T-30 to T-15 minutes

- Capture the final pre-match market snapshot.
- Run frozen v2.6.1.
- Run A1 only when v2.6.1 returns `PASS_INCOMPLETE_DATA`.
- Calculate the stake from the current combined bankroll.
- Derive and store all three observation labels.
- Record all inputs and decision reasons.

### Lock

- Lock both decisions and observation labels no later than 15 minutes before kickoff.
- Set `locked=TRUE` and record `locked_time_sgt`.
- Never alter the decision, selection, odds, stake, or observation labels after lock.
- A late market move after lock is recorded only in notes.

### Settlement

- Settle only after the match is completed.
- Store the final score, outcome, profit/loss, and resulting bankroll.
- Never change A1 thresholds based on a single match or during the tournament.

## Trial reporting

Maintain four result views:

1. Frozen v2.6.1 production lane.
2. A1 experimental lane.
3. Combined bankroll view.
4. Observation-label results, with no associated staking.

Minimum summary fields:

- matches reviewed;
- A1 qualifiers;
- wins, losses and pushes;
- hit rate;
- total staked;
- net profit;
- return on stakes;
- bankroll ROI;
- maximum drawdown;
- reasons for all A1 passes;
- counts and outcomes for each observation label.

## Integrity rules

- Every recommendation must be timestamped before kickoff.
- Every qualifying and non-qualifying match must be logged.
- Every match must contain all three observation-label fields, including explicit unavailable labels when needed.
- Missing data must produce PASS or an unavailable observation label, not an inferred value.
- The trial ledger is append-only after settlement, except for clearly documented corrections.
- Historical 82-match results remain separate from forward-trial results.

## Review point

The A1 lane and observation labels may be reviewed after the remaining World Cup matches are completed, or earlier only if a safety stop is triggered.

## Safety stop

Suspend new A1 stakes and continue shadow reporting when any condition occurs:

- three consecutive A1 losses;
- A1 forward-trial drawdown reaches 1.0% of starting trial bankroll;
- a material data-integrity problem is found;
- the implementation no longer reproduces the locked decision from stored inputs.

Observation labels continue to be recorded during an A1 safety stop because they carry no stake.
