# Step 7 — new future synthetic test ONLY

This add-on creates a new fixed 180-day synthetic continuation, then evaluates your one
finalized model once. Extract beside `SupplyGrid_Step7/`. No older attempts are needed.
The current model package and Steps 1–6 are left unchanged; no model is copied into this ZIP.

The test has already been run. Read `results/final_test_metrics.json` and the prediction/ranking
CSVs. The generated observation/event files and leakage-free feature CSV are included.
`protocol.json` records the fixed seed, period, frozen model hash/threshold and metrics,
written before generation and scoring. The script refuses a repeated run if protocol exists.
The original model package still says final testing is pending because it has intentionally
not been edited; this add-on's completed-test report records the subsequent evaluation.

If recreating this experiment from source in a new empty add-on directory with no prior
protocol/results: use the existing model environment and `python run_future_test.py`.
Do not reseed, alter the generator or retest this period in pursuit of better metrics.
The supplied source is for reproducibility, not an invitation to call repeated testing untouched.

Assumptions: same suppliers/static graph; same synthetic mechanism as training, initialized
from each supplier's last observed state. New independent pseudorandom innovations use seed
20260920. AR(1) rho .9, noise std .07, seasonal weather sine amplitude .08/period 90;
weather/congestion/demand baseline .35/.35/.45. The original logistic onset hazard depends
on those states, reliability, financial risk, graph breadth and previous-thirty-day onset counts.
Outages last 2–5 days, cannot overlap, and delay observations reflect active outages.
Past ongoing outages persist until their simulated end. Completed duration features include
only events finished by forecast origin; future seven-day labels are never model inputs.
Origins cover new dates only, excluding already disrupted suppliers and incomplete label windows.
The last seven observation days provide label follow-up, not negative-labeled forecasts.

This is a new **synthetic** test, not real enterprise observations or unseen suppliers, and
not robustness to a new simulator. The seed/protocol were fixed before examining this period.
Repeated forecast windows have correlated outcomes; no iid confidence intervals are reported.

Software/integrity checks can pass even when predictions are weak. No business acceptance
thresholds were supplied, so this package does not manufacture a predictive PASS. A completed
research experiment is not deployment certification. No real shipments or optimization are executed.
