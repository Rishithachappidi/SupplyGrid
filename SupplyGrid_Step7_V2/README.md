# SupplyGrid Step 7 V2 — corrected native-model experiment

This independent folder preserves the original `SupplyGrid_Step7/` and Steps 1–6. It supplies a calibrated supplier risk model and stable prediction interface; it **does not** claim strong predictive performance. The model uses the original synthetic supplier history; no real enterprise outcome records became available during the rebuild.

**Measured result:** Development validation AP 0.1291 versus base event rate 0.1015, recall 0.0687. The newly generated 2029-06-29 onward synthetic future test yields AP 0.1209 versus base event rate 0.0988, recall 0.0845, ROC-AUC 0.5706, Brier 0.0888, false-alert rate 0.0555, and precision@10 of 0.1416. This is not an adequate basis for autonomous disruption decisions. These figures describe a different synthetic future from the archived Step 7 test; comparing their scores is descriptive, not a paired model-improvement experiment. See `readiness_assessment.json`.

## Run on Windows (Python 3.12)

From `Supplygrid` (the directory that contains the original Step 7 and this V2 folder):

```powershell
py -3.12 -m venv .venv_step7_v2
.venv_step7_v2\Scripts\python -m pip install -r SupplyGrid_Step7_V2\requirements.txt
.venv_step7_v2\Scripts\python -m unittest discover -s SupplyGrid_Step7_V2 -p test_v2.py -v
.venv_step7_v2\Scripts\python SupplyGrid_Step7_V2\predict_v2.py --model-root SupplyGrid_Step7_V2 --features SupplyGrid_Step7\data\inference_features.csv --output SupplyGrid_Step7_V2\my_scores.csv
```

The last command writes a CSV with `supplier_id,risk_date,risk_probability,risk_level,model_version,risk_rank`. For Python callers, load `predict_suppliers(model_root, features)` from `predict_v2.py`, after putting the V2 folder on `sys.path`. Its output contains primitive values only, no XGBoost object. `risk_date` is forecast origin T, and `risk_probability` forecasts any new onset during T+1 through T+7. It does not forecast severity or recovery actions.

## Serialization and reproducibility

`model/xgboost_model.json` uses native XGBoost Booster serialization. Separate `preprocessor.joblib` and `calibrator.joblib` contain only fitted scikit-learn components. `model_metadata.json` contains the model SHA-256, checksums for all three pieces, complete software versions, random seed, feature list, target, historical split dates, selected hyperparameters, calibration and threshold policy. Loading checks every checksum and rejects corruption. Exact supported environment is in `requirements.txt`; the model was trained under Python 3.12. Never deserialize untrusted joblib files.

Use `python SupplyGrid_Step7_V2/train_v2.py --data SupplyGrid_Step7/data --output NEW_EMPTY_TRAINING_DIRECTORY` to reproduce a separate model; it refuses to replace an existing artifact. Eight predeclared shallow XGBoost configurations are ranked by average precision across three expanding purged train folds. Fit is on train only, sigmoid calibration on the later calibration split, alert threshold on later validation at a provisional 5% false alert cap. The archived `test` split and previously inspected 2028–2029 future test are not claimed as fresh untouched tests. Days with an ongoing disruption are excluded from onset prediction. Historical source feature dates and their seven-day label ends are checked for overlaps between splits.

## Later synthetic future evaluation

After training/serialization/threshold selection, `sealed_future.py` generated 180 days beginning **2029-06-29**, beyond the earlier exposed future period ending 2029-06-28. Its seed, duration and cutoff were fixed before generation. Labels were independently reconstructed from supplier onset events during T+1 through T+7, with old observed days used only for historical feature windows. `sealed_future_result/protocol.json` stores the protocol; `data/` contains only the **newly simulated** observations/events and evaluation rows; `future_metrics.json` and `test_predictions.csv` contain the result. To independently reconstruct those labels, retain the original Step 7 `source_history/` and the previously produced `Step7_Future_Test/data/` as chronological context. This is **another synthetic realization using the same simulator**, not independent real-world validation. Correlated windows and repeated suppliers limit statistical generalization.

`test_v2.py` verifies the saved native model, checksums, round-trip probabilities, ISO input, partition embargo, independent future-label reconstruction, and recomputed development/future metrics. The package does not bundle or overwrite historical Step 7 files.

## Research limits and Step 8

The stable prediction contract makes it practical to update the Step 8 risk adapter. **The previously supplied Step 8 ZIP still expects the original `risk_core` and `risk_model.joblib`; it is not automatically compatible.** Do not point its `--risk-root` at this V2 folder without an explicit adapter change and validation. The original Step 8's historical 2027 operational snapshot is also incompatible with 2029 forecasts; the what-if flag only labels a demonstration, not a current decision.

There is no defensible `expected disruption cost` because observed counterfactual disruption losses and contemporaneous business costs are absent. No 2029 downstream mitigation comparison was run against the 2027 snapshot. These fields are explicitly recorded as unavailable. A model's 5% validation alert cap is not a service-level guarantee on new data. No supplier purchases, shipments or operational actions are executed.
