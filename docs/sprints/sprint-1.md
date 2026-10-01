# Sprint 1 — Data ready for modelling (US1)

## Built

- Repository skeleton matching Section 3, `.gitignore`, `.env.example`.
- `ml/fraud_core`: `constants.py` (enums, the 23-column `FEATURE_NAMES`,
  human-readable `FEATURE_LABELS`), `features.py` (`compute_features_online`,
  `compute_features_batch`, `describe_factor`, `merge_hour_factors`,
  `risk_band`), `names.py` (108 first names, 103 last names).
- `ml/generator/generate_synthetic.py`: full synthetic Nigerian transaction
  world generator — customer segments, accounts, legitimate transaction
  simulation (hour-of-day distribution, hard negatives, travelling
  transactions), all four fraud scenarios, mule/new-account targeting,
  label noise, `summary.json`.
- `ml/pipeline/build_features.py`.

## Bug found and fixed during this sprint

The first generator draft let account balances collapse toward zero within
days (Poisson rate x lognormal amount, applied literally per Section 4.3,
implies expected spend that exceeds "5-60x segment median" starting
balances), forcing >60% of transactions into an unrealistic clipped-floor
amount. Fixed by scaling replenishment inflows to the segment's actual
throughput and by capping any single transaction at the account's real
current balance instead of a fixed floor. See `docs/DECISIONS.md` D17.

## Tests

`cd ml && pytest tests/test_features.py tests/test_generator.py` — 19
tests: feature edge cases (no history, zero balance, midnight, caps),
risk-band boundaries at 0.3999/0.40/0.70/0.7001, `describe_factor` /
`merge_hour_factors`, a batch-vs-online parity check on a hand-built
6-transaction scenario, generator reproducibility (identical seed -> byte
identical CSVs; different seed -> different output), fraud-share and
label-noise counts within tolerance. All passing.

**Done-when check**: `python -m generator.generate_synthetic` produces the
training and demo worlds and `build_features.py` turns them into a feature
table; fraud share and scenario mix land within the configured rate/weights
within a small sample's natural variance (see `docs/DECISIONS.md` D14 on
why the literal Section 4.3 rates yield more than "about 500,000" rows at
full scale — a sizing note, not a pass/fail gate).
