# SupplyGrid

## Autonomous Supply Chain Disruption Mitigation and Optimization Platform

SupplyGrid is a research-oriented platform for analyzing supply-chain disruptions, tracing their propagation through a connected supply-chain network, estimating financial exposure, and eventually generating optimized mitigation and recovery strategies.

The project is being developed incrementally. This repository will be updated continuously as new modules are implemented and validated.

---

## Project Status

| Component | Status |
|---|---|
| Supply-chain dataset | ✅ Completed |
| Dataset validation | ✅ Completed |
| Supply-chain graph construction | ✅ Completed |
| Disruption propagation | ✅ Completed |
| Financial blast-radius calculation | ✅ Completed |
| Mitigation strategy generation | ⬜ Upcoming |
| Mathematical optimization | ⬜ Upcoming |
| ML-based prediction | ⬜ Upcoming |
| Multi-agent coordination | ⬜ Upcoming |
| Continuous simulation / replanning | ⬜ Upcoming |
| Control-tower dashboard | ⬜ Upcoming |
| Benchmarking and experiments | ⬜ Upcoming |

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

# 8. Current Architecture

```text
                  SUPPLYGRID
                      │
                      ▼
              14-Table Dataset
                      │
                      ▼
             Supply-Chain Graph
                      │
                      ▼
              Supplier Disruption
                      │
                      ▼
             Exposure Propagation
                      │
                      ▼
              Inventory Screening
                      │
                      ▼
          Financial Blast Radius
```

---

# 9. Current Project Structure

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
├── build_supply_chain_graph.py
├── propagate_disruption.py
├── financial_blast_radius.py
├── compatibility.json
├── event_context.json
├── validation_report.json
└── README.md
```

---

# 10. Technology Stack

## Current

- Python
- Pandas
- NetworkX

## Planned

- NumPy
- scikit-learn / XGBoost
- OR-Tools
- SimPy or custom simulation
- PostgreSQL
- FastAPI
- React / Next.js
- Plotly
- Docker

Additional AI/agent frameworks will only be introduced where they provide a clear technical purpose.

---

# 11. Development Roadmap

## Completed

- [x] Define SupplyGrid architecture
- [x] Design connected 14-table dataset
- [x] Generate master synthetic dataset
- [x] Validate dataset
- [x] Construct typed supply-chain graph
- [x] Test supplier dependency tracing
- [x] Implement supplier disruption propagation
- [x] Implement inventory screening
- [x] Implement conditional financial blast-radius calculation

## Upcoming

- [ ] Mitigation strategy generation
- [ ] Alternative supplier evaluation
- [ ] Inventory allocation strategies
- [ ] Route / logistics alternatives
- [ ] Mathematical optimization
- [ ] ML-based disruption prediction
- [ ] Multi-agent coordination
- [ ] Continuous disruption simulation
- [ ] Dynamic re-planning
- [ ] Explainable decision traces
- [ ] Control-tower dashboard
- [ ] Benchmark experiments
- [ ] Ablation studies
- [ ] Final research documentation

---

# 12. Research Direction

The central research direction of SupplyGrid is:

> Can a graph-aware, multi-agent optimization system reduce disruption recovery cost and time compared with conventional rule-based and centralized approaches?

The project will eventually evaluate:

- Recovery cost
- Recovery time
- Service level
- Orders delayed
- Revenue at risk
- Computational efficiency
- Robustness under cascading disruptions

Comparative experiments and ablation studies will be added after the complete decision and recovery pipeline is implemented.

---

# 13. Development Philosophy

SupplyGrid is being developed incrementally. Each module is implemented and tested before the next layer is added.

```text
Dataset
   ↓
Graph
   ↓
Disruption Propagation
   ↓
Financial Exposure
   ↓
Mitigation
   ↓
Optimization
   ↓
Prediction
   ↓
Multi-Agent Coordination
   ↓
Simulation
   ↓
Continuous Re-planning
   ↓
Dashboard
   ↓
Experiments
```

The repository will be updated continuously as each stage is implemented, tested, and documented.

---

## Current Status

**Current stage: Financial Blast Radius completed.**

**Next development stage: Mitigation Strategy Generation.**

---

## Project Note

SupplyGrid is an evolving research project. Results, architecture, experiments, implementation details, and documentation will be updated as development progresses.
