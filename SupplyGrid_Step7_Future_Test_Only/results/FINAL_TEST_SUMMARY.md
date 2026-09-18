# SupplyGrid Step 7 — frozen-model future synthetic test

**The two requested tasks are complete:** a new future synthetic period was created,
and the already finalized XGBoost model was evaluated once without retraining,
recalibration or threshold changes. The existing model package remains unchanged.

Observation period: 2028-12-31 through 2029-06-28.
Eligible forecast origins: 2028-12-31 through 2029-06-21.
Final seven observation days provide full seven-day outcome follow-up.
16,428 forecast rows; 1,568 positive supplier-day horizon labels.

| Metric | Result |
|---|---:|
| Average Precision | 0.1183 |
| Prevalence/AP baseline | 0.0954 |
| ROC-AUC | 0.5718 |
| Precision | 14.17% |
| Recall | 6.51% |
| F1 | 0.0892 |
| Brier score | 0.0860 |
| False-alert rate | 4.16% |
| Accuracy | 87.31% |
| No-alert baseline accuracy | 90.46% |
| Daily precision@10 | 12.25% |
| Daily ranking lift@10 | 1.285 |

102 true-positive forecast rows, 618 false alerts, 14,242 true negatives and
1,466 false-negative forecast rows. These are overlapping supplier-day outcomes,
**not distinct disruption-event counts**.

The research evaluation is finished. Ranking is modestly above random, but most positive
windows are missed at the unchanged alert threshold. This does **not** establish a strong
or deployment-ready detector. No business performance acceptance limits were supplied,
so no artificial predictive PASS is declared. Software/data integrity is checked separately.

This is new stochastic synthetic history under the same simulator assumptions and for
the same suppliers. It is not real enterprise validation or evidence of robustness to a
different generating mechanism. No naive iid confidence intervals are reported.

Keep these results as the fixed experiment's outcome. Do not tune against this final test
and keep calling it untouched. Future improvements require a new declared experiment
and separately reserved evaluation. Downstream SupplyGrid integration is not performed.
