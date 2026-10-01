# ml

Shared feature definitions plus the synthetic data generator and training
pipeline (Sections 4-6 of the build specification).

## Setup

```bash
pip install -r requirements.txt   # installs fraud_core in editable mode too
```

## fraud_core

`fraud_core/features.py` is the **single source of truth** for the 23
model features. `compute_features_online` (used by the backend) and
`compute_features_batch` (used here for training) share arithmetic via a
private `_compute_from_primitives` helper, and must always agree — proved
by `tests/test_features.py::test_batch_matches_online_small_scenario` here
and by the full database-backed parity test in
`backend/tests/test_feature_parity.py`.

## Generating data

```bash
python -m generator.generate_synthetic --out ../data/synthetic/train \
    --customers 5000 --days 90 --seed 42 --fraud-rate 0.005 --label-noise-rate 0.02
python -m generator.generate_synthetic --out ../data/synthetic/demo \
    --customers 1000 --days 60 --seed 7 --fraud-rate 0.02
```

Everything is seeded from `numpy.random.default_rng(seed)`, so the same
arguments always produce byte-identical CSVs.

## Training

```bash
python -m pipeline.build_features --in ../data/synthetic/train --out ../data/processed/train_features.parquet
python -m pipeline.train --features ../data/processed/train_features.parquet --meta ../data/processed/feature_meta.json --out-dir ../models
python -m pipeline.evaluate --model-dir ../models/<version> --reports-dir ../reports
python -m pipeline.register_model --path ../models/<version> --activate --database-url <postgres-url>
```

`benchmark_public.py` compares model families on the public Kaggle datasets
(European credit card, PaySim) for the Chapter Four benchmark table; it
skips a dataset cleanly if the CSV isn't present under `data/raw/`.

## Tests

```bash
pytest
```
