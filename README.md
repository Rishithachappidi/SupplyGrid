\# SupplyGrid



\## Autonomous Supply Chain Disruption Mitigation and Optimization Platform



SupplyGrid is a research-oriented platform for analyzing supply-chain disruptions, tracing their propagation through a connected supply-chain network, estimating financial exposure, generating mitigation strategies, optimizing recovery decisions, and developing predictive disruption intelligence.



The project is being developed incrementally. Each stage is implemented, validated, documented, and connected to the next stage before expanding the system.



The current development pipeline is:



```text

Supply-Chain Dataset

&#x20;       |

&#x20;       v

Supply-Chain Graph

&#x20;       |

&#x20;       v

Disruption Propagation

&#x20;       |

&#x20;       v

Financial Blast Radius

&#x20;       |

&#x20;       v

Mitigation Strategy Generation

&#x20;       |

&#x20;       v

Deterministic Optimization

&#x20;       |

&#x20;       v

Predictive Disruption Intelligence

&#x20;       |

&#x20;       v

Multi-Agent Coordination

&#x20;       |

&#x20;       v

Continuous Simulation and Replanning

&#x20;       |

&#x20;       v

Control-Tower / Decision Interface

&#x20;       |

&#x20;       v

Benchmarking and Research Evaluation

```



\---



\# Project Status



| Stage   | Component                                | Status                                                                             |

| ------- | ---------------------------------------- | ---------------------------------------------------------------------------------- |

| Step 1  | Integrated Supply-Chain Dataset          | Completed                                                                          |

| Step 2  | Supply-Chain Dependency Graph            | Completed                                                                          |

| Step 3  | Disruption Propagation                   | Completed                                                                          |

| Step 4  | Financial Blast Radius                   | Completed                                                                          |

| Step 5  | Mitigation Strategy Generation           | Completed                                                                          |

| Step 6  | V2 End-to-End Optimization               | Completed                                                                          |

| Step 7  | Predictive Disruption Intelligence       | Experiment completed; model artifact verification pending                          |

| Step 8  | Multi-Agent Coordination                 | Architecture implemented; Step 7 model loading must be resolved for full execution |

| Step 9  | Continuous Simulation and Replanning     | Planned                                                                            |

| Step 10 | Benchmarking and Comparative Experiments | Planned                                                                            |

| Step 11 | Decision Dashboard                       | Planned                                                                            |



\---



\# 1. System Overview



SupplyGrid models an electronics-manufacturing supply chain containing:



```text

Supplier

&#x20;   |

&#x20;   v

Component

&#x20;   |

&#x20;   v

Product

&#x20;   |

&#x20;   v

Factory

&#x20;   |

&#x20;   v

Warehouse

&#x20;   |

&#x20;   v

Customer Order

```



The system is designed to move from disruption detection and impact analysis toward optimized recovery decisions.



The core research direction is:



> Can a graph-aware, predictive, multi-agent optimization system reduce disruption recovery cost and time compared with conventional rule-based and centralized approaches?



The project is not intended to claim that a single algorithm automatically solves every supply-chain disruption. Instead, it decomposes the problem into measurable stages with explicit assumptions and constraints.



\---



\# 2. Integrated Supply-Chain Dataset



\## Objective



Step 1 establishes the connected synthetic supply-chain environment used by the rest of the project.



The dataset is intentionally represented as a connected relational system rather than as unrelated datasets.



This allows the system to trace relationships such as:



```text

Supplier

&#x20;  |

&#x20;  v

Component

&#x20;  |

&#x20;  v

Product

&#x20;  |

&#x20;  v

Factory

&#x20;  |

&#x20;  v

Warehouse

&#x20;  |

&#x20;  v

Order

```



The same entities can subsequently be connected to disruptions, financial impacts, mitigation actions, and scenarios.



\## Dataset Structure



The core dataset contains 14 CSV tables:



```text

dataset/

|

|-- 01\_suppliers.csv

|-- 02\_components.csv

|-- 03\_product\_components.csv

|-- 04\_factories.csv

|-- 05\_products.csv

|-- 06\_warehouses.csv

|-- 07\_inventory.csv

|-- 08\_orders.csv

|-- 09\_shipments.csv

|-- 10\_routes.csv

|-- 11\_disruptions.csv

|-- 12\_financial\_impacts.csv

|-- 13\_mitigation\_actions.csv

`-- 14\_scenarios.csv

```



\## Dataset Scale



| Table              | Records | Columns |

| ------------------ | ------: | ------: |

| Suppliers          |     100 |      19 |

| Components         |     500 |      13 |

| Product Components |   5,000 |       6 |

| Factories          |      20 |      14 |

| Products           |     100 |      11 |

| Warehouses         |      30 |      10 |

| Inventory          |   5,000 |      14 |

| Orders             | 100,000 |      11 |

| Shipments          | 150,000 |      16 |

| Routes             |   1,000 |      13 |

| Disruptions        |  20,000 |      14 |

| Financial Impacts  |  20,000 |      16 |

| Mitigation Actions |  30,000 |      16 |

| Scenarios          |   5,000 |      10 |



Total scale:



```text

Approximately 336,750 records across 14 tables.

```



Additional metadata files:



```text

compatibility.json

event\_context.json

validation\_report.json

```



The dataset is synthetic and is used to provide a controlled research environment. It should not be interpreted as real historical supply-chain data.



\---



\# 3. Step 1 — Dataset Validation



The dataset was generated as an integrated supply-chain dataset with explicit relationships between entities.



Validation covers:



\* Required identifiers

\* Duplicate identifiers

\* Foreign-key relationships

\* Inventory relationships

\* Inventory balances

\* BOM quantities

\* Shipment relationships

\* Route relationships

\* Product/order relationships

\* Numerical constraints



The validation evidence is stored in:



```text

validation\_report.json

```



The original 14-table dataset is preserved when additional V2 operational tables are introduced later.



\---



\# 4. Step 2 — Supply-Chain Dependency Graph



\## Objective



Step 2 converts the relational supply-chain data into a typed directed graph.



Implementation:



```text

build\_supply\_chain\_graph.py

```



Technologies:



```text

Python

Pandas

NetworkX

```



The graph is represented as a:



```text

NetworkX MultiDiGraph

```



\## Graph Nodes



The graph contains nodes representing:



```text

Supplier

Component

Product

Factory

Warehouse

Order

Shipment

Route

```



\## Graph Relationships



Important relationships include:



```text

SUPPLIES

REQUIRED\_BY

SUBSTITUTE\_FOR

MADE\_AT

STOCKED\_AT

ORDERED\_IN

ALLOCATED\_TO

ROUTE\_FROM

ROUTE\_TO

DISPATCHES

ARRIVES\_AT

CARRIED\_IN

USED\_BY\_SHIPMENT

ALLOCATED\_SHIPMENT

```



\## Command



Install dependencies:



```cmd

python -m pip install pandas networkx

```



Run the graph construction:



```cmd

python build\_supply\_chain\_graph.py --data dataset --supplier S037

```



\## Actual Graph Result



The S037 test produced:



```text

Graph: 251,750 nodes

915,624 directed edges

```



Node counts:



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



Potential dependencies identified for supplier `S037`:



```text

Components: 5

C037, C137, C237, C337, C437



Products: 44

Factories: 17

Warehouses: 30

Orders: 43,927

```



The 43,927 orders represent potential structural exposure. They are not confirmed delayed orders.



\## Current Graph Limitation



The current graph represents a supply-chain snapshot.



It does not itself perform continuous state evolution, real-time event handling, or continuous replanning.



Those capabilities are addressed in later stages.



\---



\# 5. Step 3 — Disruption Propagation



\## Objective



Step 3 introduces a hypothetical supplier disruption and screens its downstream exposure.



The standard test scenario is:



```text

Supplier: S037

Capacity loss: 80%

Duration: 10 days

Inventory snapshot: 2027-01-01

```



Implementation:



```text

propagate\_disruption.py

```



\## Command



```cmd

python propagate\_disruption.py --data dataset --supplier S037 --capacity-loss 80 --duration 10

```



\## Propagation Flow



```text

Supplier Disruption

&#x20;       |

&#x20;       v

Affected Components

&#x20;       |

&#x20;       v

Supplier Capacity Loss

&#x20;       |

&#x20;       v

Component Availability

&#x20;       |

&#x20;       v

Supply-Chain Dependencies

&#x20;       |

&#x20;       v

Finished-Product Inventory

&#x20;       |

&#x20;       v

Potentially Uncovered Orders

```



The system checks current finished-product inventory against pending orders and determines which exposed orders are not currently covered by available finished stock.



\## Modeling Principle



The propagation stage is an exposure-screening model.



It identifies:



```text

Potentially affected orders

Potential exposure

Orders not covered by current stock

```



It does not automatically claim:



```text

Confirmed delay

Confirmed lost sale

Confirmed disruption-caused financial loss

```



This distinction is maintained throughout the project.



\---



\# 6. Step 4 — Financial Blast Radius



\## Objective



Step 4 converts the exposed-order scenario into a conditional financial exposure estimate.



Implementation:



```text

financial\_blast\_radius.py

```



\## Command



```cmd

python financial\_blast\_radius.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10

```



\## Scenario



```text

Supplier: S037

Capacity loss: 80%

Duration: 10 days

Inventory snapshot: 2027-01-01

Assumed delay: 10 days

Cancellation rate: 0%

Daily penalty rate: 0.100%

```



The assumed delay is supplied explicitly. It is not automatically assumed to equal the supplier disruption duration.



\## Financial Model



For each uncovered order:



```text

Cancelled Units

=

floor(Uncovered Units x Cancellation Rate)

```



```text

Delayed Units

=

Uncovered Units - Cancelled Units

```



```text

Lost Contribution

=

Cancelled Units x (Unit Price - Production Cost)

```



```text

Late-Delivery Penalty

=

Delayed Units

x Unit Price

x Daily Penalty Rate

x Assumed Delay

```



```text

Conditional Scenario Cost

=

Lost Contribution + Late-Delivery Penalty

```



Lost revenue and deferred revenue are tracked separately and are not automatically treated as economic loss.



\## Actual Result



The S037 scenario produced:



```text

Evaluated uncovered orders: 116

Assumed cancelled units: 0

Assumed delayed units: 890

```



Financial result:



```text

Conditional scenario cost:

USD 16,172.30



Revenue at risk:

USD 1,617,230.41



Deferred revenue:

USD 1,617,230.41

```



\## Financial Modeling Limitation



The current stock-only screen does not contain a complete baseline-versus-disrupted delivery simulation.



Therefore:



```text

USD 16,172.30

```



is a conditional scenario cost, not a claim of confirmed economic loss caused by S037.



Likewise:



```text

USD 1,617,230.41

```



is revenue at risk under the stated assumptions, not confirmed lost revenue.



A future time-evolving simulation layer is required for more rigorous causal incremental-loss estimation.



\---



\# 7. Step 5 — Mitigation Strategy Generation



\## Objective



Step 5 generates locally screened mitigation candidates for exposed orders.



Implementation:



```text

generate\_mitigation\_strategies.py

```



The stage generates alternatives but does not select the final recovery plan.



\## Command



```cmd

python generate\_mitigation\_strategies.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10

```



\## Candidate Types



The current candidate generator supports:



```text

Reallocate\_Inventory

Expedite\_Inventory\_Transfer

Switch\_Supplier

```



\## Screening Constraints



Candidates are screened using information such as:



\* BOM-approved substitutions

\* Supplier/component compatibility

\* Alternate supplier availability

\* Supplier disruption status

\* Supplier and component capacity

\* Minimum order quantities

\* Supplier-to-factory routes

\* Route capacity

\* Finished-product spare stock

\* Safety-stock constraints

\* Warehouse transfer routes

\* Arrival timing

\* Implementation timing



\## S037 Result



For the standard S037 scenario:



```text

Uncovered exposed orders: 116

```



Generated candidates:



```text

Reallocate Inventory: 55

Expedite Inventory Transfer: 55

Switch Supplier: 2



Total locally screened candidates: 112

```



Coverage:



```text

Orders with at least one option: 42

Orders with complete finished-stock option: 41

```



\## Important Interpretation



The generated candidates are alternatives, not a final recovery plan.



Candidates can compete for shared resources such as:



```text

Warehouse inventory

Route capacity

Supplier capacity

Factory capacity

```



Therefore, candidate costs and resource requirements cannot simply be summed.



The global decision is delegated to the optimization stage.



\## Success Probability Proxy



Some candidates contain a `success\_probability\_proxy`.



This is an uncalibrated synthetic proxy.



It is not an empirical probability and should not be interpreted as a guaranteed real-world probability of successful recovery.



\---



\# 8. Step 6 — Deterministic Mitigation Optimization



Step 6 converts the locally generated mitigation candidates into a constrained optimization problem.



Two versions were developed.



\---



\# 8.1 Step 6 V1



V1 provides a deliberately constrained optimization baseline.



The optimizer chooses either:



```text

One feasible finished-product mitigation action

```



or:



```text

Unresolved order

```



for each exposed order.



The optimization uses:



```text

OR-Tools

SCIP

```



\## Command



```cmd

python optimize\_mitigation.py --data dataset --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10

```



\## Mathematical Formulation



For candidate action `a`:



```text

x\_a ∈ {0,1}

```



For unresolved order `o`:



```text

y\_o ∈ {0,1}

```



Each order must satisfy:



```text

sum(selected actions for order) + unresolved = 1

```



Shared resource constraints are enforced:



```text

sum(resource demand x selected action)

<=

resource capacity

```



The objective minimizes:



```text

Mitigation Cost

\+

Remaining Baseline Penalty

\+

Optional Unresolved Service Cost

```



\## S037 V1 Result



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

Service cost: USD 0



Objective: USD 12,627.78

No-action objective: USD 16,172.30

```



The optimization is optimal only with respect to the mathematical model and assumptions defined in V1.



\---



\# 8.2 Step 6 V2 — End-to-End Optimization



\## Motivation



V1 does not fully represent procurement and production.



The V2 extension adds explicit synthetic operational-state tables while preserving the original 14-table dataset.



Additional tables:



```text

15\_factory\_component\_inventory.csv

16\_factory\_capacity\_calendar.csv

17\_supplier\_capacity\_calendar.csv

```



Location:



```text

SupplyGrid\_Step6\_V2\_Only/data\_v2/

```



\## V2 Components



V2 introduces explicit modeling for:



\* Factory component inventory

\* Dated factory capacity

\* Dated supplier capacity

\* Component procurement

\* Production duration

\* Production capacity

\* Transportation

\* Order deadlines

\* Shared resources

\* MOQ constraints

\* End-to-end recovery paths



\## End-to-End Recovery Path



V2 can represent:



```text

Alternate Supplier

&#x20;       |

&#x20;       v

Component Procurement

&#x20;       |

&#x20;       v

Inbound Route

&#x20;       |

&#x20;       v

Factory Component Inventory

&#x20;       |

&#x20;       v

Production

&#x20;       |

&#x20;       v

Finished Product

&#x20;       |

&#x20;       v

Warehouse

&#x20;       |

&#x20;       v

Customer Order

```



It can also use existing finished-product inventory and warehouse transfers.



\## V2 Validation



The V2 package includes automated tests for:



\* Foreign-key relationships

\* BOM/substitute approval

\* Route validity

\* Inventory balances

\* Integer quantities

\* Calendar coverage

\* Supplier shared capacity

\* Factory capacity balances

\* Cost decomposition

\* Procurement-to-production paths

\* Production duration

\* Missing routes

\* Invalid substitutions

\* Supplier/component shared capacity

\* Supplier disruption capacity

\* Corrupted-plan rejection

\* Reproducibility



Validation result:



```text

17 expected tests

17 passed

0 skipped

```



The original 14 CSV tables were preserved unchanged.



\## S037 V1 vs V2



For the standard S037 scenario:



```text

V1:

36 orders protected

Objective: USD 12,627.78



V2:

36 orders protected

Objective: USD 12,627.78

```



The V2 model generated additional production-job candidates, but those additional pathways did not change the optimum under this particular scenario.



This result is treated as a scenario-specific experimental observation rather than evidence that V2 universally outperforms V1.



\---



\# 9. Step 7 — Predictive Disruption Intelligence



\## Objective



Step 7 introduces machine learning to forecast near-term supplier disruption risk.



The research objective is:



> Develop and validate a leakage-free machine-learning prediction system that forecasts near-term supplier disruption risk, ranks suppliers by predicted risk, provides calibrated probabilities and explanations, and supplies this predictive signal to the downstream SupplyGrid mitigation and optimization pipeline.



The prediction question is:



> Which supplier is likely to experience a disruption soon, and how confident is the system?



\---



\# 9.1 Prediction Target



At time `T`, the model uses information available up to `T`.



The prediction target is:



```text

1 = disruption begins during T+1 through T+7

0 = no disruption begins during T+1 through T+7

```



This creates a seven-day forward prediction horizon.



\---



\# 9.2 Temporal Dataset



The Step 7 temporal dataset contains:



```text

Historical sequence: 30 days

Prediction horizon: 7 days

Supervised samples: 66,095

Sequence: 30 days x 21 features

```



Chronological partitions:



```text

55% Training

15% Calibration

15% Validation

15% Benchmark

```



Temporal purging was applied to reduce future-window overlap.



Feature construction is designed to prevent future information from entering past predictors.



\---



\# 9.3 Model Selection



The final development model was selected based on temporal validation performance rather than being predetermined solely by algorithm name.



Selected model:



```text

XGBoost

max\_depth = 1

class weighting = none

```



Average Precision / PR-AUC was emphasized because the disruption target is imbalanced.



\---



\# 9.4 Development Validation Results



The selected model achieved:



```text

Average Precision: 0.1297

ROC-AUC: 0.5942

Precision: 0.1353

Recall: 0.0655

F1: 0.0882

Brier Score: 0.0905

False-Alert Rate: 4.72%

Accuracy: 86.27%

```



The development average-precision baseline was approximately:



```text

0.0878

```



Ranking results:



```text

Precision@10%: 13.30%

Recall@10%: 13.84%

Lift@10%: 1.31x



Precision@20%: 14.23%

Recall@20%: 29.61%

Lift@20%: 1.40x

```



These results indicate a measurable predictive signal in the synthetic development data, while also showing that the model is not a high-certainty disruption predictor.



\---



\# 9.5 Future-Test Protocol



A separate future-test package was created to evaluate the frozen model on a predeclared synthetic continuation.



Location:



```text

SupplyGrid\_Step7\_Future\_Test\_Only/

```



Important files include:



```text

protocol.json

run\_future\_test.py

validate\_test.py

README.md

SHA256SUMS.json

data/

results/

```



The future test is protected against reseeding and repeated testing.



Command:



```cmd

python run\_future\_test.py

```



If the fixed test has already been reserved/run, the package intentionally prevents another run.



\---



\# 9.6 Future-Test Validation



The validation package reported:



```text

software\_data\_integrity: PASS

```



Counts:



```text

forecast\_rows: 16428

prediction\_rows: 16428

new\_observation\_rows: 18000

new\_event\_rows: 252

```



Additional checks:



```text

all\_labels\_independently\_reconstructed: true

complete\_followup: true

model\_package\_unchanged: true

```



The validation also reports:



```text

predictive\_performance\_gate:

NOT CERTIFIED: no business acceptance limits supplied

```



and:



```text

real\_world\_validation:

false

```



This is expected because the experiment uses synthetic data and no external business acceptance thresholds were defined.



\---



\# 9.7 Step 7 Model Artifact Status



During Step 8 integration, the frozen Step 7 model artifact:



```text

SupplyGrid\_Step7/model/risk\_model.joblib

```



currently fails to deserialize in the installed XGBoost environment.



The observed error is:



```text

xgboost.\_c\_api.XGBoostError:

input stream corrupted

```



The same model-loading failure occurs when running:



```cmd

python test\_step7.py

```



The installed XGBoost version is:



```text

3.4.1

```



The model file exists and has a recorded SHA-256 checksum in:



```text

SupplyGrid\_Step7/SHA256SUMS.json

```



The model has not been silently retrained or replaced.



The issue is being treated as a model-artifact/environment compatibility problem and must be resolved before the full Step 7-to-Step 8 execution path can be considered operational.



\---



\# 10. Step 8 — Multi-Agent Coordination



Step 8 introduces a coordination architecture in which specialized software agents perform different stages of disruption analysis under a central orchestrator.



The agents are bounded tool-backed software components rather than unrestricted conversational agents.



The intended architecture is:



```text

&#x20;                   Orchestrator

&#x20;                        |

&#x20;      +-----------------+------------------+

&#x20;      |                 |                  |

&#x20;      v                 v                  v

&#x20;Risk Agent        Graph Impact Agent   Financial Agent

&#x20;      |                 |                  |

&#x20;      +-----------------+------------------+

&#x20;                        |

&#x20;                        v

&#x20;               Mitigation Agent

&#x20;                        |

&#x20;                        v

&#x20;               Optimization Agent

&#x20;                        |

&#x20;                        v

&#x20;                 Decision Trace

```



Specialized responsibilities include:



```text

Risk Prediction Agent

Graph Impact Agent

Financial Impact Agent

Mitigation Agent

Optimization Agent

Orchestrator

```



The architecture uses structured messages and explicit case state rather than unconstrained free-form agent communication.



The orchestrator enforces dependency ordering between stages.



\## Step 8 Safety and Integrity Principles



The coordination layer is designed not to:



\* Modify the original dataset

\* Bypass optimization constraints

\* Override the deterministic optimizer

\* Invent missing operational results

\* Claim that an action was executed when it was only recommended

\* Treat heuristic risk proxies as guaranteed probabilities



The architecture also includes validation and decision-trace mechanisms.



\## Current Step 8 Status



The Step 8 package itself is implemented and contains:



```text

adapters.py

agents/

common.py

experiments/

orchestrator/

schemas/

state/

tests/

run\_case.py

package\_step8.py

```



However, the full runtime integration currently stops at the Step 7 risk-model loading stage because of the model deserialization issue described above.



Therefore, Step 8 should currently be described as:



```text

Multi-agent coordination architecture implemented;

full integrated execution pending Step 7 model verification.

```



\---



\# 11. Current Architecture



The current SupplyGrid research architecture is:



```text

&#x20;                        SUPPLYGRID

&#x20;                            |

&#x20;                            v

&#x20;                  14-Table Dataset

&#x20;                            |

&#x20;                            v

&#x20;                 Supply-Chain Graph

&#x20;                            |

&#x20;             +--------------+--------------+

&#x20;             |                             |

&#x20;             v                             v

&#x20;      Historical State              Disruption Event

&#x20;             |                             |

&#x20;             v                             v

&#x20;     Predictive Risk              Impact Propagation

&#x20;             |                             |

&#x20;             +--------------+--------------+

&#x20;                            |

&#x20;                            v

&#x20;                 Financial Blast Radius

&#x20;                            |

&#x20;                            v

&#x20;              Mitigation Candidate Generation

&#x20;                            |

&#x20;                            v

&#x20;                 Deterministic Optimization

&#x20;                            |

&#x20;                            v

&#x20;                  Multi-Agent Coordination

&#x20;                            |

&#x20;                            v

&#x20;                 Continuous Replanning

&#x20;                            |

&#x20;                            v

&#x20;                   Research Evaluation

```



\---



\# 12. Repository Structure



```text

SupplyGrid/

|

|-- dataset/

|   |-- 01\_suppliers.csv

|   |-- 02\_components.csv

|   |-- 03\_product\_components.csv

|   |-- 04\_factories.csv

|   |-- 05\_products.csv

|   |-- 06\_warehouses.csv

|   |-- 07\_inventory.csv

|   |-- 08\_orders.csv

|   |-- 09\_shipments.csv

|   |-- 10\_routes.csv

|   |-- 11\_disruptions.csv

|   |-- 12\_financial\_impacts.csv

|   |-- 13\_mitigation\_actions.csv

|   `-- 14\_scenarios.csv

|

|-- build\_supply\_chain\_graph.py

|-- propagate\_disruption.py

|-- financial\_blast\_radius.py

|-- generate\_mitigation\_strategies.py

|-- optimize\_mitigation.py

|

|-- compatibility.json

|-- event\_context.json

|-- validation\_report.json

|

|-- SupplyGrid\_Step6\_V2\_Only/

|   |-- data\_v2/

|   |   |-- 15\_factory\_component\_inventory.csv

|   |   |-- 16\_factory\_capacity\_calendar.csv

|   |   `-- 17\_supplier\_capacity\_calendar.csv

|   |-- extend\_dataset\_v2.py

|   |-- optimize\_mitigation\_v2.py

|   |-- test\_v2.py

|   `-- step6\_v2\_reports/

|

|-- SupplyGrid\_Step7/

|   |-- data/

|   |-- model/

|   |-- results/

|   |-- train.py

|   |-- evaluate.py

|   |-- predict.py

|   |-- prepare\_data.py

|   |-- risk\_core.py

|   |-- test\_step7.py

|   `-- SHA256SUMS.json

|

|-- SupplyGrid\_Step7\_Future\_Test\_Only/

|   |-- data/

|   |-- results/

|   |-- protocol.json

|   |-- run\_future\_test.py

|   |-- validate\_test.py

|   `-- SHA256SUMS.json

|

|-- SupplyGrid\_Step8/

|   |-- agents/

|   |-- experiments/

|   |-- orchestrator/

|   |-- schemas/

|   |-- state/

|   |-- tests/

|   |-- adapters.py

|   |-- common.py

|   |-- package\_step8.py

|   `-- run\_case.py

|

|-- .gitignore

`-- README.md

```



\---



\# 13. Technology Stack



\## Current Technologies



```text

Python

Pandas

NumPy

NetworkX

scikit-learn

XGBoost

joblib

Google OR-Tools

SCIP

```



\## Planned Technologies



The remaining system may use technologies such as:



```text

Simulation framework or custom simulation

FastAPI

PostgreSQL

React / Next.js

Plotly

Docker

```



Additional AI or agent frameworks will only be introduced where they provide a clear technical purpose.



\---



\# 14. Research Evaluation Plan



The final system will eventually be evaluated using measurable research metrics.



Primary metrics include:



```text

Recovery Cost

Recovery Time

Service Level

Orders Delayed

Revenue at Risk

Optimization Objective

Computational Runtime

Robustness Under Cascading Disruptions

```



Predictive evaluation includes:



```text

Average Precision / PR-AUC

Recall

Precision

F1

ROC-AUC

Brier Score

Calibration

Precision@K

Recall@K

Lift@K

False-Alert Rate

```



Optimization evaluation will compare different decision strategies under controlled scenarios.



The final evaluation will also include ablation experiments to determine the contribution of major system components.



\---



\# 15. Research Hypotheses



The project is structured around the following hypotheses:



\### H1



Graph-based propagation improves identification of downstream disruption exposure.



\### H2



Financial blast-radius modeling improves prioritization of mitigation decisions.



\### H3



Constrained optimization reduces modeled disruption recovery cost compared with rule-based mitigation.



\### H4



Multi-agent decomposition provides a structured and auditable coordination architecture compared with a monolithic decision workflow.



\### H5



Continuous replanning improves recovery performance under sequential and cascading disruptions.



These hypotheses will be evaluated experimentally after the full pipeline is implemented.



\---



\# 16. Current Limitations



The current research prototype has several explicit limitations.



\## Synthetic Data



The primary dataset is synthetic.



Results therefore demonstrate the proposed methodology under controlled assumptions rather than proving real-world operational performance.



\## Static Supply-Chain Graph



The current graph represents a snapshot.



Continuous time evolution is planned for Step 9.



\## Conditional Financial Exposure



The current financial model does not establish complete causal incremental loss for a supplier disruption.



\## Synthetic Mitigation Proxies



Some mitigation success and risk quantities are synthetic proxies and are not empirically calibrated probabilities.



\## Alternate Supplier Generalization



The V2 optimization framework adds procurement and production modeling, but alternate-supplier sourcing is not yet generalized to every possible same-component supplier substitution.



\## Step 7 Model Artifact



The frozen Step 7 XGBoost model currently has a deserialization issue in the installed environment.



The artifact has not been replaced while this issue is investigated.



\## Real-World Validation



No real-world validation has been performed yet.



\---



\# 17. Development Roadmap



\## Completed



```text

1\. Define SupplyGrid architecture

2\. Design connected 14-table dataset

3\. Generate synthetic master dataset

4\. Validate dataset

5\. Construct typed supply-chain graph

6\. Test supplier dependency tracing

7\. Implement disruption propagation

8\. Implement inventory screening

9\. Implement conditional financial blast radius

10\. Generate mitigation candidates

11\. Implement deterministic optimization V1

12\. Implement end-to-end optimization V2

13\. Build temporal disruption prediction dataset

14\. Develop and validate predictive model

15\. Create protected future-test protocol

16\. Implement multi-agent coordination architecture

```



\## Current Work



```text

1\. Verify and resolve Step 7 model serialization/environment compatibility

2\. Complete full Step 7-to-Step 8 runtime integration

```



\## Upcoming



```text

1\. Continuous disruption simulation

2\. Dynamic state updates

3\. Continuous replanning

4\. Sequential disruption experiments

5\. Cascading disruption experiments

6\. Multi-agent evaluation

7\. Baseline comparisons

8\. Ablation studies

9\. Decision traces and explainability

10\. Control-tower dashboard

11\. Large-scale benchmarking

12\. Final research evaluation

13\. Final documentation and publication preparation

```



\---



\# 18. Development Philosophy



SupplyGrid is being developed incrementally.



Each stage has a defined responsibility and is connected to the next stage only after its assumptions and limitations are documented.



```text

Dataset

&#x20;  |

&#x20;  v

Graph

&#x20;  |

&#x20;  v

Propagation

&#x20;  |

&#x20;  v

Financial Exposure

&#x20;  |

&#x20;  v

Mitigation Candidates

&#x20;  |

&#x20;  v

Optimization

&#x20;  |

&#x20;  v

Prediction

&#x20;  |

&#x20;  v

Multi-Agent Coordination

&#x20;  |

&#x20;  v

Simulation

&#x20;  |

&#x20;  v

Continuous Replanning

&#x20;  |

&#x20;  v

Evaluation

```



The project follows several principles:



\### Explicit assumptions



Operational and financial assumptions are documented rather than hidden.



\### No false certainty



Potential exposure is not presented as confirmed disruption impact.



\### Constrained decision making



Mitigation selection is handled through explicit mathematical constraints rather than unconstrained generated recommendations.



\### Reproducibility



Seeds, validation reports, checksums, test suites, and protected future-test protocols are maintained.



\### Separation of responsibilities



Prediction, propagation, financial analysis, mitigation generation, and optimization remain separate modules.



\### Research transparency



Synthetic experimental results are not presented as real-world validation.



\---



\# 19. Project Status



Current implementation has progressed from the original 14-table supply-chain representation through graph analysis, disruption propagation, financial exposure, mitigation generation, end-to-end optimization, predictive disruption intelligence, and multi-agent coordination architecture.



The current system foundation is:



```text

Data

&#x20; |

&#x20; v

Graph

&#x20; |

&#x20; v

Disruption Propagation

&#x20; |

&#x20; v

Financial Blast Radius

&#x20; |

&#x20; v

Mitigation Generation

&#x20; |

&#x20; v

Optimization V2

&#x20; |

&#x20; v

Predictive Intelligence

&#x20; |

&#x20; v

Multi-Agent Coordination

```



The immediate technical task is to resolve the frozen Step 7 model artifact/environment compatibility issue before claiming that the complete Step 7-to-Step 8 runtime is operational.



The next major research stage is Step 9: continuous simulation and replanning.



\---



\# Project Note



SupplyGrid is an evolving research project.



Implementation details, experimental results, assumptions, validation evidence, and architecture will be updated continuously as each research stage is implemented and evaluated.



