# SupplyGrid Step 8 — Multi-Agent Coordination (standalone add-on)

Five structured, tool-backed agents and one dependency-ordered orchestrator coordinate your existing Steps 2–7. This package **does not replace, copy, retrain or modify those tools, the original dataset, the V2 extension data, or the frozen Step 7 model**. No LLM, credentials or external service is required.

## What is implemented

| Agent | Existing deterministic capability | Responsibility |
|---|---|---|
| Risk | Frozen Step 7 model | Calibrated probability, same-date supplier ranking, threshold classification, actual model contributions |
| Graph impact | Steps 2/3 | Supplier-dependent entities and inventory-screened order exposure under explicit scenario assumptions |
| Financial | Step 4 | Conditional financial exposure; incremental causal disruption loss remains unknown |
| Mitigation | Step 5 | Competing locally feasible candidates, not a selected plan |
| Optimization | Step 6 V2 | Finished-stock and procurement/production pathways using the unchanged SCIP MILP, followed by independent plan audit |

The orchestrator validates typed scenario inputs and JSON Schema outputs, verifies handoff identity/dependencies, gates analysis on the model's actual threshold, records evidence/timings/hashes, persists case state, fails closed, and verifies both file and in-memory input immutability. Messages remain exact original tool payloads internally; Decimal monetary values are serialized as strings. Conditional costs are not multiplied by risk and presented as identified expected losses.

These are bounded **software/tool agents**, not conversational LLM agents or autonomous commercial execution. Coordination architecture is implemented; agent superiority is not assumed or established.

## Important date and model limitations

Your operational snapshot and V2 calendars describe **2027-01-01**, whereas the included Step 7 inference features describe **2028-12-30**. The orchestrator rejects this mismatch unless you explicitly supply `--snapshot-what-if`. That flag permits an **academic demonstration combining a later risk signal with a historical operational snapshot**; it does not make the dates contemporaneous and does not create a deployable current recovery recommendation.

The risk model predicts onset within the next seven days. It does **not** predict capacity loss, duration or delay. You must supply those scenario assumptions explicitly. Step 3's exposed orders are inventory-screened conditional exposures, not proven incremental supplier-caused losses. The preserved V2 objective is mitigation/procurement/conversion/transport costs plus unresolved-order penalties and optional user-specified service cost. It is not the sum of every financial exposure measure.

The previous new-future synthetic evaluation of Step 7 reported approximately AP 0.1183, recall 0.0651 and Brier 0.0860 at its frozen threshold. Its predictive signal is weak, and validation is synthetic rather than real enterprise validation. Human review is mandatory; a LOW result is not proof of safety. Step 8 does not improve or revalidate that model. It uses the existing inference features by default, not the separately packaged future-test data.

All returned plans are recommendations. `actions_executed` is always false. Original assumptions (including route capacity mode, dated resource calendars, BOM eligibility and cost decomposition) remain unchanged. No actual shipments, purchases, database operations or source-state mutations occur.

## Installation and folder placement

Extract `SupplyGrid_Step8` alongside your existing root scripts, `dataset`, `SupplyGrid_Step7`, and your V2 folder. Do not move or overwrite the old steps.

Use Python 3.12 and a separate virtual environment. The pinned prediction dependencies match the model serialization environment. Install:

```powershell
python -m venv .venv_step8
.\.venv_step8\Scripts\Activate.ps1
python -m pip install -r SupplyGrid_Step8/requirements.txt
```

Only load your own trusted frozen model: joblib files can execute code when deserialized.

`--v2-root` must point to the directory **directly containing** `optimize_mitigation_v2.py` and `extend_dataset_v2.py`. Some previous ZIPs contain a wrapper folder; use the inner directory if necessary. `--extensions` points directly to CSVs 15–17. `--data` accepts the corrected 14-CSV folder or corrected ZIP. `--risk-root` points to the directory containing `risk_core.py`, `model/risk_model.joblib` and `results/selection.json`. Absolute paths also work. Run a fresh Python process to avoid module shadowing.

## Run the S037 historical what-if demonstration

From your existing Supplygrid root, adjust the V2 paths if necessary:

```powershell
python SupplyGrid_Step8/run_case.py --project-root . --data dataset --v2-root SupplyGrid_Step6_V2_Only --extensions SupplyGrid_Step6_V2_Only/data_v2 --risk-root SupplyGrid_Step7 --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10 --snapshot-what-if --analyze-low-risk-reason "Academic historical snapshot demonstration for S037; manually reviewed" --output SupplyGrid_Step8/results/my_s037_case
```

The low-risk review flag is explicit operator authorization to analyze that supplier even if its predicted classification is LOW. It does not change its probability, class or rank. Remove the flag to use ordinary risk gating: LOW skips downstream analysis; HIGH proceeds under the supplied what-if assumptions. Remove `--snapshot-what-if` for contemporaneous operation; mismatched dates then stop the pipeline.

Each run needs a **new output directory**; previous cases are never overwritten. To change a scenario or re-evaluate, run a new case. Persistent state supports audit and reruns but automated event monitoring/replanning belongs to Step 9, not this package.

Optional switches: `--risk-features PATH`, `--daily-penalty-rate 0.001`, `--uncovered-unit-cost-cents 0`, `--route-capacity-mode single-batch`, `--time-limit-seconds 60`. A positive uncovered-unit cost is an additional stated service-cost sensitivity, not an observed loss. Both workflows must use identical settings for comparisons.

## Outputs

Each completed case has `risk.json`, `impact.json`, `financial.json`, `mitigation.json`, `optimization.json`, `case_state.json`, `source_manifest.json`, and `decision_trace.jsonl`. Failed cases retain the successful stages and an explicit failure event/state. Skipped cases retain only risk and the gate decision. Traces record UTC time, stage duration, input/output hashes, evidence and the operator's assumptions/review override. Case IDs isolate different scenarios.

The optimization payload includes actual selected transfers, production jobs and procurement lots, solver status, objective, independent audit, unresolved orders, resource utilization and factory material balances. `FEASIBLE` is not relabelled `OPTIMAL`. A solver failure never yields a fabricated plan.

## Tests and same-optimizer comparison

```powershell
python -m unittest discover -s SupplyGrid_Step8/tests -v
python SupplyGrid_Step8/experiments/compare_workflows.py --project-root . --data dataset --v2-root SupplyGrid_Step6_V2_Only --extensions SupplyGrid_Step6_V2_Only/data_v2 --risk-root SupplyGrid_Step7 --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10 --snapshot-what-if --analyze-low-risk-reason "Academic paired workflow comparison; manually reviewed" --output SupplyGrid_Step8/results/my_comparison --repetitions 2
```

The centralized baseline directly calls the **same adapters and unchanged optimizer** with identical inputs. Comparisons alternate execution order, use a warm frozen model and shared preloaded graph, and include agent validation/trace/serialization/immutability overhead in agent timings. Outcome comparison checks status, objective cents, protected orders, unresolved IDs and independent audit. Equivalent optima may have different selected action IDs; action identity is not treated as proof of quality.

The included experiment is an equivalence/integration check, not statistically sufficient evidence of agent superiority or general scalability. Both approaches can generate valid plans; trace completeness is a designed instrumentation property. Use additional dated snapshots and scenario batches for broader research. No false claim that agents necessarily reduce objective cost, and no model-generated operational facts are invented.

## Package scope

Only new Step 8 source, schemas, tests, documentation and actual demonstration/comparison reports are included. Dependencies, the 14 original CSVs, CSVs 15–17, Steps 1–7 scripts and the trained model are **not bundled**. Keep your existing folders. Results contain the actual local evidence paths/hashes from generation; rerunning on your machine creates your own provenance manifest.

## Verified runs shipped here

- 25 automated tests passed, including real recorded-message validation, duplicate-candidate rejection, objective tampering, dependency order, cross-case isolation, nonfinite probabilities, temporal guards, failure persistence and in-memory mutation detection.
- S037: actual frozen risk 0.0759423, LOW, rank 67 among 98 suppliers with latest inference features. Explicit manual what-if review: OPTIMAL, 36 protected orders, 80 unresolved, conditional objective USD 12,627.78.
- S095: actual frozen risk 0.164469, HIGH, rank 1; ordinary risk gate without a LOW override: OPTIMAL, 27 protected orders, 73 unresolved, conditional objective USD 10,544.46.
- Four real integration checks passed: date mismatch blocks downstream tools; LOW skips downstream tools; audit rejects a duplicated selected path; production-path sensitivity passes the unchanged V2 independent audit. The sensitivity's explicit extra unresolved-service cost is USD 500 per unit.
- Two paired S037 comparisons returned identical audited objective/protection/unresolved-order outcomes. Measured centralized times were about 4.83/4.51 seconds and agent times 10.03/8.77 seconds under the documented overhead-inclusive conditions. These runs do not show a speed advantage for the agent wrapper.

All demonstrations explicitly acknowledge the historical forecast/snapshot mismatch. Audit logs confirm unchanged source files and operational inputs, with no executed actions. The intentionally FAILED date-mismatch case in `results/integration_checks` is evidence that the guard works, not an uncompleted successful run.

To run the optional integration checks on your own existing data, use the same command arguments as `run_case.py`, with `python SupplyGrid_Step8/tests/integration_checks.py` and a fresh `--output`. This check expects the documented S037 snapshot and actual LOW model classification; it is not a universal invariant for other scenarios/models.
