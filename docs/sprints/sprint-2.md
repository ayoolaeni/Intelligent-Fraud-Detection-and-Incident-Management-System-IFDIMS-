# Sprint 2 — Best fraud model selected (US2)

## Built

- `ml/pipeline/common.py`: shared metrics (precision/recall/F1/FPR/ROC-AUC/
  PR-AUC), the 70/15/15 stratified split, threshold suggestion logic
  (Section 6.1 step 8), latency measurement.
- `ml/pipeline/train.py`: tunes Logistic Regression, Random Forest and
  XGBoost, each in two balancing variants (SMOTE vs class-weight/
  scale_pos_weight) via `RandomizedSearchCV` over `StratifiedKFold(5)`;
  trains an Isolation Forest for comparison; selects the best supervised
  model by validation PR-AUC (latency tie-break within 0.005); builds the
  SHAP explainer (`TreeExplainer` for tree models, `LinearExplainer` for
  LR) and saves the full model bundle, including a background sample so
  the backend can rebuild the same explainer at load time.
- `ml/pipeline/evaluate.py`: writes every Chapter Four artefact —
  `model_comparison.csv`/`.md`, confusion matrices, ROC/PR curves, SHAP
  summary and 3 example plots, `threshold_analysis.csv`,
  `fraud_type_recall.csv`.
- `ml/pipeline/register_model.py`, `ml/pipeline/benchmark_public.py`.

## Result on the smoke-scale dataset (300 customers / 30 days)

XGBoost (SMOTE variant) selected: validation PR-AUC 0.963, test PR-AUC
0.923, latency 34ms per prediction including SHAP — well under the 500ms
target. Random Forest and Logistic Regression trailed on PR-AUC; Isolation
Forest (unsupervised, reported only) trailed all supervised models, as
expected.

## Tests

`cd ml && pytest tests/test_pipeline_common.py` — metric computation,
threshold suggestion sanity, stratified split ratio preservation. The full
pipeline was also run end-to-end against a generated world as an
integration smoke test (not a pytest, since it takes real training time):
`build_features` -> `train` -> `evaluate`, producing all expected report
files.

**Done-when check**: `make train` (or the pipeline modules run directly)
trains all four model families, writes the reports, and registers a model
bundle; re-running with the same seed reproduces the same metrics (the
pipeline is deterministic given `RANDOM_STATE=42` throughout).
