# Gold Record Builder v1.0 Validation

## Status

**Status:** Pending raw reference fixtures

Gold Record Builder v1.0 has been added to the repository together with a reference comparison harness.

The 8-match reference batch is approved as the validation target, but the raw `.txt` fixtures and reviewed expected `.json` files are not yet stored in the repository. Until those fixtures are committed, the builder cannot be truthfully marked as fully validated by automated replay.

## Reference batch

The validation batch consists of these 8 matches:

| # | Date | Match | HT | FT | Pattern |
|---:|---|---|---:|---:|---|
| 1 | 2026-06-26 | Ecuador vs Germany | 1-1 | 2-1 | False Favourite Trap |
| 2 | 2026-06-26 | Japan vs Sweden | 0-0 | 1-1 | Balanced Draw |
| 3 | 2026-06-25 | Czech Republic vs Mexico | 0-0 | 0-3 | Elite Favourite Late Blowout |
| 4 | 2026-06-25 | South Africa vs Korea Republic | 0-0 | 1-0 | Low-Scoring False Favourite |
| 5 | 2026-06-25 | Morocco vs Haiti | 2-2 | 4-2 | High-Event Favourite With Resistance |
| 6 | 2026-06-25 | Scotland vs Brazil | 0-2 | 0-3 | Elite Favourite Complete Alignment |
| 7 | 2026-06-25 | Bosnia vs Qatar | 2-1 | 3-1 | Stable Favourite Execution |
| 8 | 2026-06-25 | Switzerland vs Canada | 0-0 | 2-1 | Balanced Market Home Edge |

## Required fixture layout

```text
validation/gold_builder_v1/raw/
  ecuador_vs_germany.txt
  japan_vs_sweden.txt
  czech_republic_vs_mexico.txt
  south_africa_vs_korea_republic.txt
  morocco_vs_haiti.txt
  scotland_vs_brazil.txt
  bosnia_vs_qatar.txt
  switzerland_vs_canada.txt

validation/gold_builder_v1/expected/
  WC2026-GRP-ECU-GER_v1.0.json
  WC2026-GRP-JPN-SWE_v1.0.json
  WC2026-GRP-CZE-MEX_v1.0.json
  WC2026-GRP-RSA-KOR_v1.0.json
  WC2026-GRP-MAR-HAI_v1.0.json
  WC2026-GRP-SCO-BRA_v1.0.json
  WC2026-GRP-BIH-QAT_v1.0.json
  WC2026-GRP-SUI-CAN_v1.0.json
```

## Validation commands

Generate builder output:

```bash
python tools/gold_record_builder.py \
  --input-dir validation/gold_builder_v1/raw \
  --out validation/gold_builder_v1/generated \
  --force
```

Compare generated output against reviewed expected records:

```bash
python tools/validate_gold_builder_reference.py \
  --expected validation/gold_builder_v1/expected \
  --generated validation/gold_builder_v1/generated
```

## Acceptance criteria

Gold Record Builder v1.0 may be tagged as validated when:

1. All 8 raw reference fixtures are committed.
2. All 8 expected reviewed JSON files are committed.
3. The builder generates all 8 records without error.
4. The validator returns exit code `0`.
5. Any intentional differences are documented in this file.

## Operational rule after validation

Once validated, all new SPWIN Atlas Gold records should be generated through `tools/gold_record_builder.py` unless a match has unusual formatting requiring manual intervention. Manual intervention must be documented in the record provenance.
