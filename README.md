# SupplyGrid

## Autonomous Supply Chain Disruption Mitigation and Optimization Platform

SupplyGrid is a research-oriented platform for analyzing supply-chain disruptions, tracing their propagation through a connected supply-chain network, estimating financial exposure, and eventually generating optimized mitigation and recovery strategies.

The project is being developed incrementally. This repository will be updated continuously as new modules are implemented and validated.

---

## Project Status

| Component | Status |
|---|---|
| Supply-chain dataset | Completed |
| Dataset validation | Completed |
| Supply-chain graph construction | Completed |
| Disruption propagation | Completed |
| Financial blast-radius calculation | Completed |
| Mitigation strategy generation | Completed |
| Mathematical optimization — V1 | Completed |
| Mathematical optimization — V2 | Completed |
| ML-based disruption prediction | Completed* |
| Multi-agent coordination | Implemented* |
| Continuous simulation / replanning | Upcoming |
| Control-tower dashboard | Upcoming |
| Benchmarking and experiments | Upcoming |

### Current Status Notes

**Step 5 — Mitigation Strategy Generation:** Completed and tested with 112 locally screened candidates.

**Step 6 — Mathematical Optimization:** V1 and the end-to-end V2 optimizer are completed. V2 passed 17/17 automated tests.

**Step 7 — ML Prediction:** The temporal prediction dataset, model-selection pipeline, validation, explainability, robustness checks, and future-test protocol are completed. The frozen model currently has an XGBoost artifact-loading compatibility issue, which is being treated as an environment/model-artifact verification issue.

**Step 8 — Multi-Agent Coordination:** The specialized-agent architecture, orchestrator, structured schemas, case state, decision trace, validation, and integration tests are implemented. Full runtime integration is currently blocked by the Step 7 model-loading issue.

**Step 9 — Continuous Simulation / Replanning:** This is the next development stage.

---

# 1. System Overview

The current SupplyGrid pipeline is:

```text
Supply-Chain Dataset
        │
        ▼
Supply-Chain Graph
        │
        ▼
Disruption Propagation
        │
        ▼
Financial Blast Radius
        │
        ▼
Mitigation
        │
        ▼
Optimization
        │
        ▼
Simulation / Continuous Replanning
        │
        ▼
Control-Tower Dashboard
```

The first four stages have currently been implemented and tested.

---

# 2. Dataset

SupplyGrid uses a connected synthetic master dataset consisting of 14 relational CSV tables.

The dataset represents an electronics-manufacturing supply chain containing suppliers, components, products, factories, warehouses, inventory, orders, shipments, routes, disruptions, financial impacts, mitigation actions, and scenarios.

## Dataset Structure

```text
dataset/
│
├── 01_suppliers.csv
├── 02_components.csv
├── 03_product_components.csv
├── 04_factories.csv
├── 05_products.csv
├── 06_warehouses.csv
├── 07_inventory.csv
├── 08_orders.csv
├── 09_shipments.csv
├── 10_routes.csv
├── 11_disruptions.csv
├── 12_financial_impacts.csv
├── 13_mitigation_actions.csv
└── 14_scenarios.csv
```

## Dataset Scale

| Table | Records | Columns |
|---|---:|---:|
| Suppliers | 100 | 19 |
| Components | 500 | 13 |
| Product Components | 5,000 | 6 |
| Factories | 20 | 14 |
| Products | 100 | 11 |
| Warehouses | 30 | 10 |
| Inventory | 5,000 | 14 |
| Orders | 100,000 | 11 |
| Shipments | 150,000 | 16 |
| Routes | 1,000 | 13 |
| Disruptions | 20,000 | 14 |
| Financial Impacts | 20,000 | 16 |
| Mitigation Actions | 30,000 | 16 |
| Scenarios | 5,000 | 10 |

**Total: approximately 336,750 records across 14 tables.**

Additional metadata files include `compatibility.json`, `event_context.json`, and `validation_report.json`.

---

# 3. Step 1 — Dataset Validation

The dataset was generated as a connected supply-chain dataset rather than as unrelated independent CSV files.

Validation includes checks for:

- Missing required identifiers
- Duplicate identifiers
- Invalid relationships
- Invalid inventory balances
- Invalid BOM quantities
- Invalid shipment relationships
- Route inconsistencies
- Product/order inconsistencies
- Invalid numerical values

The validation report is maintained in:

```text
validation_report.json
```

---

# 4. Step 2 — Supply-Chain Graph

The Supply-Chain Graph converts the relational CSV tables into a typed directed graph using:

- Python
- Pandas
- NetworkX

Implementation:

```text
build_supply_chain_graph.py
```

## Graph Structure

```text
Supplier
   │
   │ SUPPLIES
   ▼
Component
   │
   │ REQUIRED_BY
   ▼
Product
   │
   │ MADE_AT
   ▼
Factory
   │
   ▼
Warehouse
   │
   ▼
Order
```

Additional relationships include:

```text
SUPPLIES
REQUIRED_BY
SUBSTITUTE_FOR
MADE_AT
STOCKED_AT
ORDERED_IN
ALLOCATED_TO
ROUTE_FROM
ROUTE_TO
DISPATCHES
ARRIVES_AT
CARRIED_IN
USED_BY_SHIPMENT
ALLOCATED_SHIPMENT
```

## Graph Test

Supplier dependency tracing was tested using:

```text
Supplier: S037
```

Result:

```text
251,750 nodes
915,624 directed edges
```

### Node Types

```text
Supplier: 100
Component: 500
Product: 100
Factory: 20
Warehouse: 30
Order: 100,000
Shipment: 150,000
Route: 1,000
```

For supplier `S037`, the graph identified:

```text
Components: 5
Products: 44
Factories: 17
Warehouses: 30
Orders: 43,927
```

These orders represent **potential exposure**, not confirmed disruption effects.

## Command

```bash
python -m pip install pandas networkx
python build_supply_chain_graph.py --data dataset --supplier S037
```

---

# 5. Step 3 — Disruption Propagation

Implementation:

```text
propagate_disruption.py
```

This module introduces a hypothetical supplier disruption and propagates its potential exposure through the supply-chain graph.

## Test Scenario

```text
Supplier: S037
Capacity loss: 80%
Duration: 10 days
```

## Command

```bash
python propagate_disruption.py --data dataset --supplier S037 --capacity-loss 80 --duration 10
```

## Propagation Logic

```text
Supplier
   ↓
Components
   ↓
Products
   ↓
Factories
   ↓
Warehouses
   ↓
Orders
```

The module also performs current finished-stock screening to determine whether available inventory can cover exposed orders.

### Modeling Principle

Potential exposure is **not** treated as confirmed delay.

The current implementation does not perform:

- Financial calculation
- Optimization
- Machine-learning prediction
- Multi-agent coordination
- Time-stepped simulation
- Live event handling

These are later stages.

---

# 6. Step 4 — Financial Blast Radius

Implementation:

```text
financial_blast_radius.py
```

This module takes potentially affected orders from disruption propagation and calculates a conditional financial exposure scenario.

## Command

```bash
python financial_blast_radius.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10
```

## Current Test Scenario

```text
Supplier: S037
Capacity loss: 80%
Duration: 10 days
Inventory snapshot: 2027-01-01
Assumed delay: 10 days
Cancellation rate: 0%
Daily penalty rate: 0.100%
```

## Current Result

```text
Evaluated uncovered orders: 116
Assumed cancelled units: 0
Assumed delayed units: 890
```

### Financial Exposure

```text
Conditional scenario cost:
USD 16,172.30

Revenue at risk:
USD 1,617,230.41

Deferred revenue:
USD 1,617,230.41
```

The current scenario cost consists of the modeled late-delivery penalty because cancellation, recovery, expediting, alternative sourcing, transport, holding, and stockout costs are not yet modeled at this stage.

---

# 7. Financial Modeling Limitation

The current financial calculation is deliberately described as:

> Conditional scenario exposure, NOT identified disruption-caused loss.

The current dataset contains a stock-only baseline rather than complete baseline-versus-disrupted delivery outcomes.

Therefore, the USD 16,172.30 result is **not claimed as definitive economic loss caused by S037**.

It should be interpreted as:

```text
Potential exposure under stated assumptions
```

rather than:

```text
Confirmed economic loss caused by the disruption
```

A future simulation/replanning layer will provide the basis for estimating incremental disruption effects more rigorously.

---

# 8. Step 5 — Mitigation Strategy Generation

Step 5 generates locally feasible mitigation candidates without selecting a final recovery plan.

Implementation:

```text
generate_mitigation_strategies.py
```

## Command

```cmd
python generate_mitigation_strategies.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10
```

## Candidate Types

```text
Reallocate_Inventory
Expedite_Inventory_Transfer
Switch_Supplier
```

The generator checks:

- Approved component substitutions
- Supplier compatibility
- Alternate supplier availability
- Supplier capacity
- Component MOQ
- Transportation routes
- Route capacity
- Warehouse inventory
- Safety stock
- Arrival timing
- Shared resource requirements
- Order coverage

## Produced Result — S037

```text
Reallocate_Inventory: 55
Expedite_Inventory_Transfer: 55
Switch_Supplier: 2

Total locally screened candidates: 112
Orders with at least one option: 42
Orders with complete finished-stock option: 41
```

Step 5 generates alternatives only. It does not select the final plan, reserve resources, guarantee production, or claim empirical success probabilities. Shared-resource conflicts are resolved by Step 6.

---

# 9. Step 6 — Deterministic Mitigation Optimization

Step 6 converts mitigation candidates into a constrained mathematical optimization problem.

## 9.1 Step 6 V1 — Candidate-Level Optimization

V1 uses binary decision variables for mitigation actions and unresolved orders.

```text
x_a = whether mitigation action a is selected
y_o = whether order o remains unresolved
```

Each order is assigned either one selected action or remains unresolved. Shared resource constraints prevent competing actions from exceeding available capacity.

The objective minimizes:

```text
Mitigation Cost
+ Remaining Penalty
+ Optional Unresolved-Service Cost
```

## Command

```cmd
python optimize_mitigation.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10
```

## V1 Result — S037

```text
Candidates evaluated: 112
Eligible candidates: 107
Solver status: OPTIMAL

Selected actions: 36
Orders protected: 36
Unresolved orders: 80
Unresolved units: 595

Mitigation cost: USD 1,512.89
Remaining penalty: USD 11,114.89
Service cost: USD 0.00

Objective: USD 12,627.78
No-action objective: USD 16,172.30
```

The optimality claim applies only to the explicitly defined V1 mathematical model.

## 9.2 Step 6 V2 — End-to-End Optimization

V2 extends the optimizer with separate synthetic operational-state tables without modifying the original 14-table dataset.

Additional tables:

```text
15_factory_component_inventory.csv
16_factory_capacity_calendar.csv
17_supplier_capacity_calendar.csv
```

Additional assumptions are documented in:

```text
V2_MODEL_ASSUMPTIONS.md
```

### End-to-End Path

```text
Alternate Supplier
       ↓
Component Procurement
       ↓
Inbound Transportation
       ↓
Factory Component Inventory
       ↓
Production
       ↓
Finished Product
       ↓
Warehouse
       ↓
Customer Order
```

V2 incorporates:

- Factory component inventory
- Supplier dated capacity
- Factory dated production capacity
- BOM quantities
- Production duration
- Procurement
- Transportation
- Order deadlines
- Route capacity
- Shared resources
- Explicit cost components

### V2 Validation

The V2 validation suite covers procurement-to-production paths, MOQ constraints, shared factory capacity, factory inventory consumption, production duration, route failures, substitution validation, supplier capacity, disruption capacity, corrupted plans, invalid data, and reproducibility.

```text
17 tests expected
17 tests passed
0 tests skipped
```

The original 14 dataset tables were preserved unchanged.

### S037 Comparison

```text
V1 protected orders: 36
V2 protected orders: 36

V1 objective: USD 12,627.78
V2 objective: USD 12,627.78
```

The additional V2 pathways did not change the optimum under this particular scenario. This is treated as an experimental result, not as evidence of universal superiority.

---

# 10. Step 7 — Predictive Disruption Intelligence

Step 7 introduces machine-learning-based supplier disruption prediction.

## Objective

The predictive question is:

> Which supplier is likely to face a disruption soon, and how confident are we?

At time `T`, only information available up to `T` is used. The target is `1` when a disruption begins during `T+1` through `T+7`, otherwise `0`.

This temporal definition is designed to prevent future information leakage.

## 10.1 Temporal Dataset

```text
66,095 supervised samples
30-day historical sequence
21 features
7-day future disruption window
```

Chronological partitions:

```text
55% Train
15% Calibration
15% Validation
15% Benchmark
```

Temporal purging is used to prevent overlapping future windows from leaking information across partitions.

## 10.2 Model Selection

The development model was selected using temporal evaluation rather than fixing an algorithm in advance.

Selected model:

```text
XGBoost
Depth: 1
Class weighting: None
```

Mean temporal cross-validation Average Precision:

```text
0.1097
```

Model artifact:

```text
SupplyGrid_Step7/model/risk_model.joblib
```

## 10.3 Development Validation

```text
Average Precision: 0.1297
ROC-AUC:            0.5942
Precision:          0.1353
Recall:             0.0655
F1:                 0.0882
Brier Score:        0.0905
False-Alert Rate:   4.72%
Accuracy:           86.27%
```

Ranking metrics:

```text
Precision@10%: 13.30%
Recall@10%:    13.84%
Lift@10%:       1.31×

Precision@20%: 14.23%
Recall@20%:    29.61%
Lift@20%:       1.40×
```

The signal is described as modest and is not presented as deployment-ready.

## 10.4 Future-Test Protocol

The reserved future-test package is:

```text
SupplyGrid_Step7_Future_Test_Only/
```

Command:

```cmd
python run_future_test.py
```

The fixed test is intentionally protected against reseeding or repeated retesting.

If it has already been reserved/run, the program reports:

```text
FileExistsError:
This fixed test has already been reserved/run.
Read its saved results; no reseeding or retesting.
```

## 10.5 Future-Test Validation

```text
software_data_integrity: PASS

forecast_rows:        16,428
prediction_rows:      16,428
new_observation_rows: 18,000
new_event_rows:          252

all_labels_independently_reconstructed: true
complete_followup: true
model_package_unchanged: true
```

The validator also reports:

```text
predictive_performance_gate:
NOT CERTIFIED: no business acceptance limits supplied

real_world_validation: false
```

Technical integrity therefore passed, while no external business acceptance threshold was supplied. Real-world validation is false because the experimental data is synthetic.

## 10.6 Current Model Artifact Issue

The frozen model currently has an environment compatibility issue during loading:

```text
xgboost._c_api.XGBoostError:
input stream corrupted
```

The current environment reports:

```text
XGBoost 3.4.1
```

The frozen artifact should not be casually retrained or replaced because doing so would change the validated Step 7 model.

---

# 11. Step 8 — Multi-Agent Coordination

Step 8 implements a dependency-ordered multi-agent coordination architecture.

The agents are specialized software components rather than unrestricted conversational agents.

## Specialized Agents

### Risk Prediction Agent

Uses Step 7 and produces supplier disruption probability, risk ranking, and prediction metadata.

### Graph Impact Agent

Uses Steps 2–3 and produces affected components, products, factories, warehouses, and potentially exposed orders.

### Financial Impact Agent

Uses Step 4 and produces conditional exposure, penalty estimates, revenue-at-risk information, and financial assumptions.

### Mitigation Agent

Uses Step 5 and produces feasible mitigation candidates, costs, resource requirements, and feasibility information. It does not select the final plan.

### Optimization Agent

Uses Step 6 V2 and produces selected actions, objective value, resource usage, protected orders, and unresolved orders.

### Orchestrator

Coordinates the agents in dependency order and maintains case state, structured messages, validation results, and the decision trace.

## 11.1 Architecture

```text
                    ORCHESTRATOR
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
       Risk Agent    Graph Agent   Financial Agent
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                 Mitigation Agent
                         │
                         ▼
                Optimization Agent
                         │
                         ▼
                  Decision Trace
```

Agents communicate using structured messages and schemas. The orchestration layer preserves the deterministic constraints of the earlier stages.

## 11.2 Evaluation

For the S037 demonstration:

```text
Orders protected: 36
Orders unresolved: 80
Objective: USD 12,627.78
```

Observed runtime:

```text
Centralized workflow: 4.5–4.8 seconds
Multi-agent workflow:  8.8–10.0 seconds
```

The multi-agent implementation therefore does not currently claim faster optimization or a better objective. Its contribution at this stage is modular coordination, structured decision tracing, and separation of specialized functions.

## 11.3 Runtime Command

From the Step 8 directory:

```cmd
python run_case.py --project-root .. --data ..\dataset --v2-root ..\SupplyGrid_Step6_V2_Only --extensions ..\SupplyGrid_Step6_V2_Only\data_v2 --risk-root ..\SupplyGrid_Step7 --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10 --daily-penalty-rate 0.001 --uncovered-unit-cost-cents 0 --route-capacity-mode per-consignment --snapshot-what-if --output results\s037_run.json
```

Full runtime integration is currently blocked by the Step 7 frozen-model loading issue.

---

# 12. Integrated Architecture

```text
                         SUPPLYGRID
                             │
                             ▼
                  14-Table Supply Dataset
                             │
                             ▼
                  Typed Supply-Chain Graph
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
      Disruption Prediction          Disruption Event
              │                             │
              └──────────────┬──────────────┘
                             ▼
                  Impact Propagation
                             │
                             ▼
                  Financial Exposure
                             │
                             ▼
              Mitigation Candidate Generation
                             │
                             ▼
              Deterministic Optimization
                             │
                             ▼
                  Multi-Agent Orchestrator
                             │
                             ▼
                Simulation / Replanning
```

---

# 13. Repository Structure

```text
SupplyGrid/
│
├── dataset/
│   ├── 01_suppliers.csv
│   ├── 02_components.csv
│   ├── 03_product_components.csv
│   ├── 04_factories.csv
│   ├── 05_products.csv
│   ├── 06_warehouses.csv
│   ├── 07_inventory.csv
│   ├── 08_orders.csv
│   ├── 09_shipments.csv
│   ├── 10_routes.csv
│   ├── 11_disruptions.csv
│   ├── 12_financial_impacts.csv
│   ├── 13_mitigation_actions.csv
│   └── 14_scenarios.csv
│
├── SupplyGrid_Step6_V2_Only/
│   ├── data_v2/
│   ├── optimize_mitigation_v2.py
│   ├── test_v2.py
│   └── validation_report_v2.json
│
├── SupplyGrid_Step7/
│   ├── model/
│   ├── data/
│   ├── results/
│   ├── train.py
│   ├── predict.py
│   └── test_step7.py
│
├── SupplyGrid_Step7_Future_Test_Only/
│   ├── data/
│   ├── results/
│   ├── protocol.json
│   ├── run_future_test.py
│   └── validate_test.py
│
├── SupplyGrid_Step8/
│   ├── agents/
│   ├── orchestrator/
│   ├── schemas/
│   ├── state/
│   ├── experiments/
│   ├── tests/
│   ├── adapters.py
│   ├── common.py
│   └── run_case.py
│
├── build_supply_chain_graph.py
├── propagate_disruption.py
├── financial_blast_radius.py
├── generate_mitigation_strategies.py
├── optimize_mitigation.py
├── compatibility.json
├── event_context.json
├── validation_report.json
├── .gitignore
└── README.md
```

---

# 14. Technology Stack

## Current

- Python
- Pandas
- NumPy
- NetworkX
- scikit-learn
- XGBoost
- OR-Tools
- JSON-based structured interfaces
- Automated testing

## Planned

- SimPy or custom discrete-event simulation
- PostgreSQL
- FastAPI
- React / Next.js
- Plotly
- Docker

Additional AI or agent frameworks will only be introduced where they provide a clear technical purpose.

---

# 15. Research Hypotheses

### H1 — Graph Propagation

Graph-aware dependency propagation improves identification of downstream disruption exposure compared with isolated table-level analysis.

### H2 — Financial Blast Radius

Quantified financial exposure improves mitigation prioritization compared with disruption-only severity measures.

### H3 — Optimization

Deterministic constrained optimization reduces modeled recovery cost compared with rule-based mitigation.

### H4 — Multi-Agent Coordination

Specialized agent decomposition can preserve decision quality while improving modularity and traceability compared with a monolithic workflow.

### H5 — Continuous Replanning

Continuous state updates and replanning improve recovery performance under sequential and cascading disruptions.

These are research hypotheses to be experimentally evaluated, not assumed conclusions.

---

# 16. Planned Step 9 — Continuous Simulation and Replanning

The next major stage is:

```text
Step 9 — Continuous Simulation & Dynamic Replanning
```

The objective is to move from static disruption analysis toward a time-evolving operational state.

Planned flow:

```text
Initial State
     ↓
Disruption
     ↓
State Update
     ↓
Impact Recalculation
     ↓
Mitigation
     ↓
Execution Simulation
     ↓
New State
     ↓
Re-evaluation
     ↓
Replanning
```

This stage will address limitations of snapshot-based calculations and enable experiments with sequential and cascading disruptions.

---

# 17. Research Evaluation Plan

After the complete pipeline is implemented, SupplyGrid will evaluate:

- Recovery cost
- Recovery time
- Service level
- Orders delayed
- Revenue at risk
- Computational efficiency
- Robustness under cascading disruptions
- Resource utilization
- Replanning frequency
- Decision stability

Planned comparisons include:

```text
Rule-Based Baseline
        vs
Centralized Optimization
        vs
Multi-Agent Optimization
```

Additional experiments will include ablation studies, stress tests, cascading disruptions, sequential disruptions, capacity shocks, route failures, supplier failures, inventory shortages, and sensitivity analysis.

---

# 18. Current Limitations

SupplyGrid is currently a controlled research prototype.

1. The primary supply-chain dataset is synthetic.
2. Step 3 identifies potential exposure rather than guaranteed causal delay.
3. Step 4 financial values are conditional scenario estimates.
4. Step 5 success proxies are synthetic and uncalibrated.
5. Step 6 is optimal only within its explicitly modeled mathematical formulation.
6. Step 6 V2 uses additional synthetic operational-state assumptions.
7. Alternate supplier sourcing is not yet fully generalized across every same-component supplier substitution pathway.
8. Step 7 predictive performance is based on synthetic temporal data.
9. Step 7 currently has a model-artifact/XGBoost environment compatibility issue.
10. Step 8 full runtime integration is therefore currently blocked by Step 7 model loading.
11. Real-world execution and physical supply-chain actions are not performed.
12. Continuous time-evolving simulation is not yet implemented.

These limitations are intentionally documented rather than hidden.

---

# 19. Reproducibility

SupplyGrid uses fixed synthetic data, explicit scenario assumptions, validation reports, model manifests, automated tests, and checksums where applicable.

Key principles:

- The original 14-table dataset is preserved.
- Step 6 V2 extensions are separate from the original dataset.
- Step 7 uses chronological data partitioning.
- The future-test data is reserved and protected from casual regeneration.
- Step 7 model artifacts are checksum-tracked.
- Step 8 verifies important upstream artifacts before orchestration.
- Automated tests are included for major stages.

---

# 20. Development Philosophy

SupplyGrid follows a layered research architecture:

```text
Dataset
   ↓
Graph
   ↓
Disruption Propagation
   ↓
Financial Exposure
   ↓
Mitigation Candidates
   ↓
Optimization
   ↓
Prediction
   ↓
Multi-Agent Coordination
   ↓
Simulation
   ↓
Continuous Replanning
   ↓
Decision Support
   ↓
Research Evaluation
```

Each layer has a defined responsibility and explicit assumptions.

The project separates:

```text
Observed / Generated Data
        ↓
Model Output
        ↓
Scenario Assumption
        ↓
Optimization Decision
        ↓
Simulated Outcome
```

This separation is central to reproducible research.

---

# 21. Current Project Status

```text
Step 1  Dataset Validation                  COMPLETE
Step 2  Supply-Chain Graph                 COMPLETE
Step 3  Disruption Propagation             COMPLETE
Step 4  Financial Blast Radius             COMPLETE
Step 5  Mitigation Generation              COMPLETE
Step 6  Deterministic Optimization V2      COMPLETE
Step 7  Predictive Intelligence             COMPLETE*
Step 8  Multi-Agent Coordination             COMPLETE*
Step 9  Continuous Simulation               NEXT
```

`*` Step 7 and Step 8 have implementation and validation artifacts, but full runtime verification is currently blocked by the frozen Step 7 model-loading compatibility issue.

---

# 22. Project Note

SupplyGrid is an evolving research project. The repository is updated continuously as new stages are implemented, tested, audited, and documented.

The project prioritizes:

```text
Correctness
Reproducibility
Explicit assumptions
Deterministic constraints
Traceability
Experimental validation
Honest reporting of limitations
```

The goal is not simply to build a large software system, but to develop a scientifically testable framework for disruption-aware supply-chain decision making.
