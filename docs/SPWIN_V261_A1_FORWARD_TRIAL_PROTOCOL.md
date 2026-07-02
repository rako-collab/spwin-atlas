# SPWIN v2.6.1-A1 Forward Trial Protocol

Date adopted: 2026-07-02

## Purpose

Run the A1 incomplete-data micro-stake lane on all remaining World Cup 2026 matches while keeping SPWIN v2.6.1 frozen.

## Engine status

- SPWIN v2.6.1 remains the production engine.
- A1 remains a separate experimental lane.
- No A1 result may change a v2.6.1 recommendation.
- No thresholds may be adjusted during the trial.

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

## Match workflow

### T-90 to T-60 minutes

- Capture confirmed line-ups when available.
- Record the latest 1X2 and Asian Handicap prices.
- Confirm the opening/reference prices used for movement calculations.
- Record the data source and timestamp in Singapore time.

### T-30 to T-15 minutes

- Capture the final pre-match market snapshot.
- Run frozen v2.6.1.
- Run A1 only when v2.6.1 returns `PASS_INCOMPLETE_DATA`.
- Calculate the stake from the current combined bankroll.
- Record all inputs and decision reasons.

### Lock

- Lock both decisions no later than 15 minutes before kickoff.
- Set `locked=TRUE` and record `locked_time_sgt`.
- Never alter the decision, selection, odds, or stake after lock.
- A late market move after lock is recorded only as an observation.

### Settlement

- Settle only after the match is completed.
- Store the final score, outcome, profit/loss, and resulting bankroll.
- Never change A1 thresholds based on a single match or during the tournament.

## Trial reporting

Maintain three result views:

1. Frozen v2.6.1 production lane.
2. A1 experimental lane.
3. Combined bankroll view.

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
- reasons for all A1 passes.

## Integrity rules

- Every recommendation must be timestamped before kickoff.
- Every qualifying and non-qualifying match must be logged.
- Missing data must produce PASS, not an inferred value.
- The trial ledger is append-only after settlement, except for clearly documented corrections.
- Historical 82-match results remain separate from forward-trial results.

## Review point

The A1 lane may be reviewed after the remaining World Cup matches are completed, or earlier only if a safety stop is triggered.

## Safety stop

Suspend new A1 stakes and continue shadow reporting when any condition occurs:

- three consecutive A1 losses;
- A1 forward-trial drawdown reaches 1.0% of starting trial bankroll;
- a material data-integrity problem is found;
- the implementation no longer reproduces the locked decision from stored inputs.
