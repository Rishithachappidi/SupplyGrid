# SupplyGrid Step 6 v2

Joint end-to-end recovery optimization with dated procurement, factory material
balances, production slots and finished-product delivery. This is a bounded,
synthetic decision model, not a live enterprise execution system.

## Run

Requires Python 3.11+ (tested on Python 3.12). Extract these ZIP contents directly into your existing **Supplygrid** folder.
The three new Python files must sit beside your existing Step 2–6 scripts,
not inside a separate nested folder. Your screenshot names the existing CSV
folder `dataset`; the commands below use that name. If its actual location is
different, change `--data` accordingly. No earlier scripts or original CSVs
are included or overwritten.

```bash
python -m pip install -r requirements_v2.txt
```

First validate the existing extension files; this command performs no optimization:

```bash
python extend_dataset_v2.py --data dataset --output data_v2 --validate-only
```

Then solve and compare the same S037 scenario:

```bash
python optimize_mitigation_v2.py --data dataset --extensions data_v2 --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10 --route-capacity-mode single-batch --compare-v1
```

Run the deterministic tests:

```bash
python -m unittest -v test_v2
```

Add `--output my_plan.json` to save all selected transfers, production jobs,
procurement lots, material allocations and the independent audit. Existing
report files are not overwritten. The solver time limit defaults to 60 seconds;
`FEASIBLE` means an audited incumbent, not a proved optimum. Other unsuccessful
statuses produce no selected plan.

To regenerate the extension into a **new** directory:

```bash
python extend_dataset_v2.py --data dataset --output regenerated_data_v2 --days 31 --seed 20260918
```

The generator refuses to overwrite extension CSVs. It never edits originals.
If you instead merge the three extension CSVs into your original CSV folder,
point `--extensions` to that same folder. They need not be merged for the supplied commands.

## New tables and keys

| File | Rows | Columns | Primary key |
|---|---:|---:|---|
| `15_factory_component_inventory.csv` | 4,496 | 10 | `inventory_id`; unique factory/component |
| `16_factory_capacity_calendar.csv` | 620 | 8 | factory/date |
| `17_supplier_capacity_calendar.csv` | 15,500 | 12 | supplier/component/date |

Dates are ISO `YYYY-MM-DD`. The snapshot is **2027-01-01**, taken from the
original dataset, not today's date. Calendar coverage is 2027-01-01 through
2027-01-31 inclusive. Monetary values are USD. Table 17 repeats a supplier's
shared total across its component rows; that total must be counted **once**,
not summed across the repeated rows.

Validation reads the saved CSVs, checks actual row/column counts and rejects
NULL/blank required fields, duplicate keys, invalid foreign keys, fractional
quantities, balance inconsistencies, invalid dates, incomplete calendars,
unapproved BOM substitutions and invalid routes. SHA-256 checks confirm the
original 14 files remain unchanged. Missing inbound routes are valid absences,
not a reason to invent connectivity; affected procurement paths are unavailable.

## Synthetic assumptions

These are explicit additional modeling assumptions, not observed enterprise facts.
The extension is deterministic and is not calibrated to real distributions.

1. **Factory component positions.** Include exactly the original components and
   product-specific BOM-approved substitutes for products assigned to each
   factory. One physical factory/component balance is shared across all its
   products and orders. Warehouse component stock is never credited to a factory.
2. **Initial quantities.** For each position, let `r` be the largest per-unit BOM
   quantity associated with that position. Seeded generation assigns zero stock
   with probability 3%; otherwise on-hand stock is `r × uniform integer[12,40]`.
   Reserved quantity is at most `r × uniform integer[0,2]`; safety stock is at
   most `2r`, both capped by available stock. Usable = on-hand − reserved − safety.
   These are additional synthetic factory balances, not transfers inferred from
   warehouse inventory or historical shipments. Inventory valuation is reported
   separately and is not charged again as a new purchase.
3. **Recovery availability.** Usable material is ring-fenced for this recovery
   problem. Calendar commitments represent unrelated baseline work outside the
   affected-order recovery set. Their materials/replenishments are outside this
   model; it does not simulate every baseline order's future material consumption.
   The synthetic inventory and calendars are not reconstructed ERP histories.
4. **Factory calendar.** Nominal capacity comes from `production_capacity`.
   Committed slots are `floor(nominal × current_utilization)`, constant across
   the horizon. Available = nominal − committed. V2 conservatively interprets
   available units as concurrent unit slots in each dated 24-hour bucket.
   All units of an order batch occupy slots throughout its cycle. This is not
   a measured machine/shift schedule. No overtime or cross-factory reassignment.
5. **Production duration.** All units in a selected order batch run in parallel.
   Duration = `max(1, ceil(production_time_hours / 24))` days. Capacity is charged
   on each occupied day, not only the start day. Finish is start + duration.
   Products can be produced only at their existing assigned factory.
6. **Supplier calendar.** Component nominal capacity comes from `maximum_supply`;
   shared supplier capacity comes from `component_capacity`. Seeded unrelated
   component commitments are 20–60% of nominal, inclusive integer percentages,
   varying by component/date. Supplier commitment is the sum of its component
   commitments. These are reservation budgets, not measured release schedules.
7. **Disruption.** During the half-open disruption interval, nominal supplier
   and component reservation capacities are multiplied by the surviving
   fraction, rounded down. Existing commitments have priority: recovery capacity
   is `max(0, reduced nominal − committed)`. The optimizer does not claim to
   fulfill displaced baseline commitments. Existing factory stock is not destroyed.
8. **Procurement timing.** Capacity is reserved on the order-placement date.
   Dispatch = reservation + component lead time; arrival = dispatch + actual
   listed route transit. Capacity is a dated reservation budget, not an assertion
   that physical dispatch happens on the reservation date. Only actual supplier
   → assigned-factory routes may be used. Arrivals become usable at the beginning
   of their modeled arrival day. There are no unlisted transfer routes.
9. **MOQ.** Purchases are integer MOQ packs. An activated lot buys at least one
   full pack. Pack quantities cannot be resized into arbitrary smaller purchases.
   Multiple orders may share a procurement lot, and paid surplus remains as stock.
10. **Material allocation.** Every BOM requirement must be fully covered, one
    component unit for one approved substitute unit. Substitution approval is
    product-specific. Physical original/substitute stock is shared, not duplicated
    per requirement. Inventory carries forward; no future arrival can fund an
    earlier production start. No expiry within this short modeled horizon.
11. **Transportation.** `normal_transit_days` is deterministic. No handling time,
    cutoff hours, loading constraints, stochastic failure or final-mile delivery
    is added. Protection means arrival at the order's assigned warehouse no later
    than its required date. Air-route pricing already reflects that route; an
    additional expedite premium is not added again.
12. **Route capacity modes.** `single-batch` adds a conservative shared pool per
    route across the entire mitigation batch, including procurement and production
    shipments. This is an extra assumption, not a measured daily route budget.
    `per-consignment` preserves Step 5's original meaning: each individual
    consignment must fit, but no invented aggregate daily limit is imposed.
    V1 and V2 are compared using the same mode. Existing route commitments are unknown.
13. **Existing finished stock.** Retains Step 5's spare-stock definition after its
    all-product pending-order allocations and safety-stock deduction. No original
    stock record is altered. Orders outside that allocation window are not simulated.
14. **Financial exposure.** Unresolved orders retain the explicit assumed delay
    and illustrative daily penalty rate from Step 4. Default cancellation is zero;
    gross revenue is not added as a loss. An optional unresolved-unit service cost
    is zero by default and must be supplied explicitly. No causal savings claim.

The original network is sparse and many component lead times exceed this scenario's
deadlines. V2 deliberately preserves those limitations. The model is complete for
these specified recovery decisions, not a full factory scheduling/digital-twin model.

## Cost decomposition (no material double-counting)

V2 compares **incremental recovery cash costs**, not full accounting COGS:

- Existing finished stock and usable factory components are sunk inventory;
  their acquisition cost is not charged again. No inventory opportunity cost is assumed.
- New procurement pays component `unit_cost` for every purchased MOQ unit,
  including surplus, plus inbound route variable and fixed dispatch charges.
- Conversion operating expense is factory `operating_cost_per_unit`; labor is
  factory `labor_cost_per_unit`. For this synthetic convention, operating expense
  excludes both labor and materials. These are paid once per produced unit.
- Finished-product delivery pays outbound route variable and fixed dispatch charges.
- Unresolved orders pay assumed penalties and the optional explicit service cost.

The existing product `production_cost` is **not used in the v2 objective**: its
material/conversion breakdown is insufficient to safely add procurement to it.
Factory calendar columns expose conversion operating, labor and summed conversion
rates. Existing supplier-level `unit_cost` is not substituted for the component quote.

All objective coefficients are integer USD cents. Procurement material and
variable inbound transport invoices are rounded separately per MOQ pack, then
multiplied by pack count. One fixed fee is charged per activated procurement lot.
Conversion operating and labor invoices are separately rounded per production
job. Outbound transport is rounded per consignment. Step 5 finished-stock quotes
and Step 4 per-order penalty rounding are preserved. `estimated_transit_cost` is
treated as the fixed dispatch fee, consistent with Step 5's quoting convention.

## Optimization formulation

For order `o`, choose exactly one on-time full-uncovered-quantity recovery action,
one production job, or unresolved flag `y[o]`. Partial/late finished-stock options
and the two component-only Step 5 quotes are fixed to zero. V2 creates its own
dated procurement variables; it does not credit a component purchase as a product.

- Binary `x[action]`: finished-stock transfer.
- Binary `b[job]`: complete production batch with a chosen start and outbound route.
- Binary `a[lot]`, integer `k[lot]`: procurement activation and MOQ pack count.
- Integer `z[job, required_component, physical_component]`: BOM material allocation.

Constraints:

1. `sum(x for order) + sum(b for order) + y[order] = 1`.
2. Shared finished stock and selected route pool usage stay within their capacities.
3. Procurement pack count is zero if inactive, otherwise at least one and at most
   its supplier/component/consignment-derived bound.
4. All procurement quantities share supplier and component capacity by reservation date.
5. Production jobs share available factory slots on every occupied day.
6. Allocation to each requirement equals `order quantity × BOM coefficient × b[job]`.
7. Cumulative component consumption through each production-start date is at most
   initial usable factory stock plus procurement arrivals by that date.
8. Procurement ownership, routes, MOQ, production duration and on-time outbound
   arrival are enforced in enumeration and independently reconstructed afterward.

Minimize transfer + procurement + inbound + conversion + outbound costs, remaining
conditional penalties and explicitly requested service costs. All variables here
are integer/binary: this is an integer-linear special case of the MILP family,
solved with OR-Tools' SCIP backend. The optimum is only over these paths, routes,
dates, full-order decisions and stated assumptions. An all-unresolved plan is valid.

## Verified comparison

S037, 80% loss, 10 days; assumed unresolved delay 10 days; daily penalty 0.1%;
no additional service cost; shared single-batch route mode:

| Metric | V1 | V2 |
|---|---:|---:|
| Solver status | OPTIMAL | OPTIMAL |
| Orders protected | 36 | 36 |
| Stock-transfer orders | 36 | 36 |
| Production orders | 0 | 0 |
| Orders unresolved | 80 | 80 |
| Total modeled cost (USD) | 12,627.78 | 12,627.78 |

V2 enumerated 65 feasible production jobs but selected none at the default
penalty-only objective. No procurement lot could arrive in time using existing
routes, lead times and deadlines. That is a valid outcome, not evidence that the
procurement implementation was exercised by this particular scenario.

`step6_v2_reports/s037_comparison.json` records the full comparison and independent audit.
`step6_v2_reports/s037_service_cost_sensitivity.json` is a **separate, explicitly changed**
objective with USD 500 additional cost per unresolved unit. Under that assumption,
V1 protects 41 orders at USD 306,350.54; V2 protects 58 (41 stock, 17 production)
at USD 261,281.27. Both are optimal and audited. There is still no on-time new
procurement in S037. USD 500 is illustrative, not an inferred customer contract.
Do not substitute this sensitivity result for the default comparison.

Procurement is tested independently with a tiny controlled fixture: two orders
need 2 and 3 units; an approved alternate provides one five-unit MOQ lot; actual
inbound transit, a two-day production cycle, and outbound transit meet both
warehouse deadlines. Hand-calculated cost is USD 30.50:
materials 10 + inbound 4 + conversion 10 + outbound 6.50. With factory slots
limited to 3, only the three-unit order is selected. Further tests reject MOQ,
stock, timing, route, calendar, BOM, capacity and cost violations. Paid MOQ surplus
is tested separately and never counted as finished-product order coverage.

## Audit and reproducibility

`audit_plan()` reconstructs selected-plan inventory prefixes, BOM consumption,
supplier/component dated usage, occupied factory slots, route quantities, dates
and cost decomposition from source rows, without trusting solver coefficients.
It rejects double-use, early material consumption, late completion, unapproved
substitution, modified quotes or inconsistent costs before reporting a plan.
The reconstructed cost must reconcile with the solver objective in cents.

`step6_v2_reports/tests_v2.json` records tests actually executed. `SHA256SUMS_V2.json` identifies
package contents; `data_v2/validation_report_v2.json` identifies original dataset
bytes and actual extension file dimensions. Nothing executes shipments, uses ML,
calls an LLM or begins Step 7.

OR-Tools API reference: [Google's MIP solver guide](https://developers.google.com/optimization/mip/mip_example).
