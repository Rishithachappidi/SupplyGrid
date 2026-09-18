# SupplyGrid Step 7 — ONE-model Predictive Disruption Intelligence

This is the clean package to use for Step 7. It needs **none of the older Step 7 folders**.
Extract into Supplygrid; it creates only `SupplyGrid_Step7/`. Leave Steps 1–6 untouched.
One fitted calibrated model is saved at `model/risk_model.joblib`. Other candidates are
temporary tuning experiments, not extra deployed model files. This is best **within the
documented limited search**, not proof of the best possible algorithm.

## Use (Python 3.12, Windows)

```powershell
cd SupplyGrid_Step7
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest test_step7 -v
.venv\Scripts\python predict.py
```

Prepared data, fitted model, actual development results and supplier scores are included.
`prepare_data.py` rebuilds rolling features/labels from the included `source_history/`:
`python prepare_data.py --output regenerated_data`. No older Step 7 folders are required.
You do not need to retrain. To reproduce separately: `python train.py --output rerun`,
`python evaluate.py --root rerun`, and `python predict.py --root rerun --output rerun/results/supplier_risk_scores.csv`.
The original fitted artifact is never overwritten by training. Load only trusted joblib files.

## Task and provenance

At the end of day T, predict a new supplier disruption onset in T+1 through T+7 inclusive.
Currently disrupted suppliers are excluded. Incomplete future windows are not negative labels.
Included input is the existing SupplyGrid-linked synthetic supplier-day feature dataset:
100 suppliers, 730 simulated days from 2027-01-01. It is **not observed enterprise history**.
Supplier attributes and graph counts assume the static 2027 snapshot is known and unchanged.
Weather, congestion, demand and delay signals are synthetic, not live external conditions.

Raw static inputs derive from SupplyGrid suppliers, components, BOM, factories, products
and routes. Features include fixed reliability/risk/capacity/lead-time/graph counts,
current observed weather/congestion/demand/utilization, past-seven-day delays,
past-thirty-day onset counts, durations of previously completed events within the past
ninety-day onset window, and capped days since onset. No future duration, capacity loss,
order outcomes or financial impacts are predictors. No measured severity/daily geopolitical
conditions exist; those are not invented. Model input schema is explicit in `risk_core.py`.
Prepared input files preserve the existing label/feature construction; this release does
not change the generator to boost performance. Source hashes appear in `results/selection.json`.

The original synthetic process has persistent noisy operational signals and stochastic
event onsets; outages last 2–5 days. Repeated suppliers and overlapping labels are dependent.
These limitations prevent real-world accuracy claims and naive independent-row confidence intervals.

## Model selection and calibration

Two justified families: regularized logistic regression (simple/transparent for weak signal)
and shallow regularized XGBoost (nonlinear tabular alternative). Twelve fixed candidates:
LR C .01/.1/1 with no/full class weights; XGB depth 1/2 with no/mild/full weighting.
No temporal network is added merely for decoration; earlier results did not justify its
extra complexity on this data. Broader families might win a different experiment.

Select maximum mean Average Precision across **three expanding purged temporal folds
inside the old training period**. Scalers, encoders and class weights are fitted separately
within each fold. Fit the chosen configuration on training only; sigmoid calibration uses
the separate later calibration period. No final-test rows enter fitting or selection.
Existing historical periods were already examined in development; internal CV is a tuning
protocol, **not a new untouched final evaluation**.

Alert policy: maximize development-validation recall subject to a **provisional 5% false-alert
rate cap**. This prevents the earlier alert-everyone behavior. It is a research default requiring
business review, not a promise that future false-alert rate will stay at 5%. Change it only in
a separate declared experiment via `--max-false-alert-rate`. Lower alert volume can mean
very low recall; actual tradeoffs are retained. Accuracy never selects the winner.

## Outputs

- `supplier_risk_scores.csv`: supplier ID, date, seven-day probability, per-date risk rank,
  HIGH/LOW based on the single threshold, horizon and model version.
- `supplier_explanations.csv`: actual additive contributions to calibrated log-odds.
  LR uses fitted coefficient contributions; XGB uses built-in TreeSHAP contributions.
  These explain the fitted mathematical score, not causal effects. Baseline is a mathematical
  intercept/background; not a hypothetical real supplier. Contributions are not probability points.
- AP, ROC-AUC, precision, recall, F1, Brier, accuracy, false-alert and alert fraction.
- Precision@K, recall@K, lift over random ranking **within each forecast date**, micro-aggregated.
  These are supplier-day horizon outcomes, not counts of distinct disruption events.
- Supplier/month errors, high-confidence mistakes, calibration/confusion plots, train-to-development
  mean-shift diagnostics, permutation importance and input-sensitivity diagnostics.

Global importance/permutation and robustness perturbations are descriptive, not causal.
Single-class subgroups omit undefined AP/ROC. Repeated development inspection makes
these numbers unsuitable as the final reported generalization result.

## What remains honestly incomplete

Included single-model run: depth-1 XGBoost, no class weighting, selected from twelve
candidates by mean temporal CV AP 0.1097. Development AP 0.1297 vs prevalence 0.1015;
ROC-AUC 0.5942, Brier 0.0905. With the provisional false-alert cap, precision 0.1353,
recall 0.0655 and false-alert rate 0.04725. It misses many events and is **not deployment-ready**.
Daily ranking precision@10 is 0.1330 (lift 1.312), while top-1 lift is below one (0.915).
These are weak/modest development results, not proof of useful final performance.

Official explanation reference: [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html).

**Fresh future testing is still pending.** No available period is scientifically untouched.
Once a genuinely unseen later feature CSV with full seven-day labels is reserved, evaluate
the frozen model once using `python evaluate.py --data FUTURE.csv --final-future-test`.
Origins through 2028-12-30 are rejected; the evaluator refuses repeating a saved final test.
A date check cannot establish that you never inspected the future data: provenance still needs review.

Risk export is integration-ready, but **does not modify or execute Steps 1–6**. A probability
does not predict capacity loss or duration. Downstream propagation/mitigation must use explicit
reviewed what-if assumptions. HIGH does not mean certain disruption. Do not automate actions
until fresh testing shows the risk signal is useful under a business-approved alert policy.
