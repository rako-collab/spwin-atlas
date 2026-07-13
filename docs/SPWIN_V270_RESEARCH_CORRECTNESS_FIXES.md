# SPWIN v2.7 Research — Correctness Fixes

## Status

SPWIN v2.7 is a **research-only branch**. SPWIN v2.6.1 remains frozen and unchanged as the production and historical benchmark.

## Scope

This branch fixes implementation defects identified in the v2.6.1 CriticMode audit. It deliberately does **not** attempt the larger methodology redesign around probability calibration, vig removal, cross-bookmaker consensus, or expected-value modelling.

## Correctness fixes

### 1. Tournament stage classification

v2.6.1 awarded `+3` only when `stage == "Round of 32"`. Every other stage fell into the `else` branch and received `+5` labelled as group-stage context.

v2.7 explicitly normalises stages:

- Group stages: `+5`
- Knockout stages, including Round of 32, Round of 16, quarter-finals, semi-finals, final, and third-place playoff: `+3`
- Unknown stages: `+0`

### 2. Main Asian Handicap is authoritative

v2.6.1 selected the strongest shortening across both `AH` and `HANDICAP_ALT`. This could let a lower-liquidity alternate handicap override a non-confirming primary line.

v2.7 uses only the primary `AH` market for:

- Consensus
- CPI
- AH red flags
- Market completeness

`HANDICAP_ALT` remains visible as an observation-only field.

### 3. HT partial confirmation threshold

v2.6.1 awarded five CPI points whenever the favourite was the strongest HT selection, even with negligible or zero shortening.

v2.7 requires favourite-aligned HT movement of at least `-3%` before awarding partial confirmation. The existing thresholds remain:

- HT consensus: `-5%`
- Strong HT CPI confirmation: `-8%`

### 4. Signal score naming

The uncalibrated CPI-derived output previously labelled `confidence` is renamed `signal_score`. It must not be interpreted as a probability.

### 5. Current versus closing price labelling

Replay output now uses `price` plus `price_type`:

- Completed Gold records default to `closing`
- Pre-match records default to `current_snapshot`
- An explicit record-level snapshot type overrides the default

The existing Gold schema field `closing_odds` remains readable for backward compatibility, but research output no longer automatically describes every input price as a verified close.

## Preserved v2.6.1 rules

The following remain unchanged so the research branch isolates correctness effects:

- CPI admission threshold: `80`
- Consensus requirement: `3 of 4`
- Any red flag causes PASS
- CPI 80–84 stake: `0.75%`
- CPI 85+ stake: `1.25%`
- Production selection remains favourite 1X2

## Known limitations not fixed here

- Correlation and double-counting between market channels
- Raw decimal-odds movement rather than vig-normalised probability movement
- No liquidity weighting
- No expected-value or fair-price model
- Small and potentially contaminated historical calibration sample
- Single-source bookmaker consensus

These belong to later v2.7 research modules and must be evaluated separately from this correctness patch.

## Run

```bash
python3 -m unittest discover -s tests -v
python3 tools/run_spwin_v270_research_replay.py
```

Default outputs are written to:

```text
reports/research/spwin_v2_7_correctness/
```
