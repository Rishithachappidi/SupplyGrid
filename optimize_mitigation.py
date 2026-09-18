"""SupplyGrid Step 6: OR-Tools/SCIP binary linear mitigation optimization.

Keep beside Steps 2-5. Install: python -m pip install pandas networkx ortools
Run: python optimize_mitigation.py --data data --assumed-delay-days 10

Scope: one on-time finished-product action per order, or leave its uncovered
quantity unresolved. Partial/late actions and component-only sourcing are fixed
to zero, not credited as completed orders. Thus supplier capacity/MOQ cannot be
violated, but production/procurement optimization is NOT implemented in v1.
All candidates receive binary variables, including disabled candidates.

Objective in integer USD cents: transport quotes + assumed baseline penalties
on unresolved orders + optional explicit service cost per unresolved unit.
No cancellations, lost sales, calibrated probabilities or causal savings claimed.
Deadline refers to delivery to the order's warehouse, not final customer delivery.

Default route mode is per-consignment (Step 5's documented capacity meaning).
--route-capacity-mode single-batch instead assumes each listed route capacity
is a SHARED pool for this entire mitigation batch. This conservative additional
assumption is not measured daily availability. Existing route commitments are
unknown. Warehouse stock is spare snapshot stock from Step 5, above safety stock
after its existing order allocations. Handling/cutoffs remain unmodeled.

Formulation: x_a binary; y_o binary unresolved flag.
sum(x_a for order o) + y_o = 1.
sum(resource_demand[a,r] * x_a) <= capacity[r].
min sum(quote[a] * x_a) + sum(baseline_penalty[o] * y_o)
    + service_cost_per_unit * sum(uncovered_units[o] * y_o).
An all-unresolved plan is valid; cost minimization does not force protection.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from build_supply_chain_graph import load_tables, build_graph
from propagate_disruption import propagate
from financial_blast_radius import calculate_financial_exposure, decimal, cents
from generate_mitigation_strategies import generate_options


def money_cents(value):
    value = decimal(value)
    if value < 0:
        raise ValueError('Costs cannot be negative.')
    return int(cents(value) * 100)


def integer(value, name):
    d = decimal(value)
    if d < 0 or d != d.to_integral_value():
        raise ValueError(f'{name} must be a nonnegative integer.')
    return int(d)


def prepare_input(event, options, tables, finance, route_mode='per-consignment'):
    """Validate candidate coverage and construct independent shared capacity map."""
    if route_mode not in ('per-consignment', 'single-batch'):
        raise ValueError('Unknown route capacity mode.')
    screened = {o['order_id']: o for o in event['eligible_orders']}
    financial = {o['order_id']: o for o in finance['detail']}
    orders = {}
    for oid in event['potential_order_ids']:
        o = screened[oid]
        orders[oid] = dict(quantity=integer(o['uncovered_units'], 'Order quantity'),
                           penalty_cents=money_cents(financial[oid]['penalty_usd']))
    capacities = {f'stock:{w}:{p}': integer(q, 'Spare stock')
                  for (w, p), q in options['spare_finished_stock'].items()}
    routes = tables['routes'].set_index('route_id').to_dict('index')
    if tables['routes']['route_id'].duplicated().any():
        raise ValueError('Duplicate route IDs.')
    rows = []
    for c in options['candidates']:
        oid = c['order_id']
        if oid not in orders:
            raise ValueError('Candidate references an unexposed order.')
        q = integer(c['recoverable_units'], 'Candidate quantity')
        cost = money_cents(c['action_cost'])
        if c['currency'] != 'USD' or q == 0:
            raise ValueError('Invalid currency or zero candidate quantity.')
        reason = None
        demands = {}
        if c['quantity_basis'] != 'finished product units':
            reason = 'Component-only action: material readiness and production not validated'
        else:
            o = screened[oid]
            rt = routes[c['route_id']]
            if (rt['origin_id'], rt['destination_id']) != (c['source_location'], c['destination_location']):
                raise ValueError('Candidate route endpoints disagree.')
            if c['product_id'] != o['product_id'] or c['destination_location'] != o['warehouse_id']:
                raise ValueError('Candidate delivers wrong product or warehouse.')
            stock_key = f"stock:{c['source_location']}:{c['product_id']}"
            route_key = f"route:{c['route_id']}:consignment"
            expected = {stock_key: q, route_key: q}
            if c['resource_demands'] != expected:
                raise ValueError('Candidate resource demands disagree with quantity.')
            if stock_key not in capacities:
                raise ValueError('Missing stock capacity.')
            cap = integer(rt['route_capacity'], 'Route capacity')
            arrival = date.fromisoformat(c['arrival_date'])
            if arrival < date.fromisoformat(event['start_date']):
                raise ValueError('Arrival predates decision snapshot.')
            if not c['feasible']:
                reason = 'Step 5 marks infeasible'
            elif q != orders[oid]['quantity']:
                reason = 'Partial quantity: v1 requires one full uncovered-quantity action'
            elif arrival > date.fromisoformat(o['required_date']):
                reason = 'Arrival after required warehouse-delivery date'
            elif q > cap:
                reason = 'Exceeds per-consignment route capacity'
            demands[stock_key] = q
            if route_mode == 'single-batch':
                capacities[route_key] = cap
                demands[route_key] = q
        rows.append(dict(action_id=c['action_id'], order_id=oid, cost_cents=cost,
                         enabled=reason is None, exclusion_reason=reason,
                         demands=demands, candidate=c))
    return rows, orders, capacities


def solve_model(rows, orders, capacities, service_cost_cents=0, time_limit_seconds=60):
    """Solve and independently audit returned incumbent; never execute actions."""
    from ortools.linear_solver import pywraplp
    if time_limit_seconds <= 0:
        raise ValueError('Solver time limit must be positive.')
    service_cost_cents = integer(service_cost_cents, 'Service cost cents')
    if len({r['action_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate action IDs.')
    for r in rows:
        if r['order_id'] not in orders:
            raise ValueError('Unknown order ID.')
        integer(r['cost_cents'], 'Cost cents')
        for key, qty in r['demands'].items():
            integer(qty, 'Resource demand')
            if key not in capacities:
                raise ValueError(f'Missing resource capacity: {key}')
    for cap in capacities.values():
        integer(cap, 'Resource capacity')
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if solver is None:
        raise RuntimeError('SCIP backend unavailable; install the official ortools wheel.')
    solver.SetTimeLimit(int(time_limit_seconds * 1000))
    solver.SetNumThreads(1)
    x = {r['action_id']: solver.IntVar(0, int(r['enabled']), r['action_id']) for r in rows}
    y = {oid: solver.BoolVar('unresolved_' + oid) for oid in orders}
    by_order = defaultdict(list)
    by_resource = defaultdict(list)
    for r in rows:
        by_order[r['order_id']].append(x[r['action_id']])
        for key, qty in r['demands'].items():
            by_resource[key].append(qty * x[r['action_id']])
    for oid in orders:
        solver.Add(solver.Sum(by_order[oid]) + y[oid] == 1)
    for key, terms in by_resource.items():
        solver.Add(solver.Sum(terms) <= capacities[key])
    objective = solver.Objective()
    for r in rows:
        objective.SetCoefficient(x[r['action_id']], r['cost_cents'])
    for oid, o in orders.items():
        integer(o['quantity'], 'Order quantity')
        integer(o['penalty_cents'], 'Penalty cents')
        objective.SetCoefficient(y[oid], o['penalty_cents'] + service_cost_cents * o['quantity'])
    objective.SetMinimization()
    status = solver.Solve()
    names = {solver.OPTIMAL: 'OPTIMAL', solver.FEASIBLE: 'FEASIBLE',
             solver.INFEASIBLE: 'INFEASIBLE', solver.UNBOUNDED: 'UNBOUNDED',
             solver.ABNORMAL: 'ABNORMAL', solver.NOT_SOLVED: 'NOT_SOLVED'}
    result = dict(status=names.get(status, str(status)), solver=solver.SolverVersion(),
                  candidates_evaluated=len(rows), eligible_candidates=sum(r['enabled'] for r in rows),
                  exclusions=Counter(r['exclusion_reason'] for r in rows if not r['enabled']))
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        return result
    if not solver.VerifySolution(1e-7, True):
        raise ArithmeticError('Solver solution verification failed.')
    chosen = [r for r in rows if x[r['action_id']].solution_value() > 0.5]
    protected = {r['order_id'] for r in chosen}
    if len(protected) != len(chosen) or any(not r['enabled'] for r in chosen):
        raise ArithmeticError('Duplicate protection or disabled candidate selected.')
    unresolved = [oid for oid in orders if oid not in protected]
    usage = defaultdict(int)
    for r in chosen:
        for key, qty in r['demands'].items():
            usage[key] += qty
    if any(qty > capacities[key] for key, qty in usage.items()):
        raise ArithmeticError('Shared resource capacity violated.')
    mitigation = sum(r['cost_cents'] for r in chosen)
    penalty = sum(orders[oid]['penalty_cents'] for oid in unresolved)
    service = sum(orders[oid]['quantity'] for oid in unresolved) * service_cost_cents
    total = mitigation + penalty + service
    if abs(objective.Value() - total) > 0.01:
        raise ArithmeticError('Objective does not reconcile in cents.')
    baseline = sum(o['penalty_cents'] + service_cost_cents * o['quantity'] for o in orders.values())
    result.update(selected_actions=[r['candidate'] for r in chosen],
                  decisions={aid: int(v.solution_value() > 0.5) for aid, v in x.items()},
                  orders_protected=len(protected), unresolved_order_ids=unresolved,
                  unresolved_units=sum(orders[oid]['quantity'] for oid in unresolved),
                  mitigation_cost=Decimal(mitigation)/100, remaining_penalty=Decimal(penalty)/100,
                  uncovered_service_cost=Decimal(service)/100, objective_value=Decimal(total)/100,
                  no_action_objective=Decimal(baseline)/100,
                  resource_utilization={k: dict(used=q, capacity=capacities[k]) for k, q in sorted(usage.items())},
                  best_bound_usd=objective.BestBound()/100, wall_time_ms=solver.WallTime())
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', default='data')
    ap.add_argument('--supplier', default='S037')
    ap.add_argument('--capacity-loss', type=float, default=80)
    ap.add_argument('--duration', type=int, default=10)
    ap.add_argument('--assumed-delay-days', type=int, required=True)
    ap.add_argument('--daily-penalty-rate', default='0.001')
    ap.add_argument('--uncovered-unit-cost', default='0', help='Explicit additional service cost in USD; default zero')
    ap.add_argument('--route-capacity-mode', choices=['per-consignment', 'single-batch'], default='per-consignment')
    ap.add_argument('--time-limit-seconds', type=int, default=60)
    a = ap.parse_args()
    if a.assumed_delay_days < 0 or a.time_limit_seconds <= 0:
        ap.error('Delay must be nonnegative and time limit positive.')
    tables = load_tables(a.data)
    graph = build_graph(tables)
    event = propagate(graph, tables, a.supplier, a.capacity_loss, a.duration)
    options = generate_options(event, graph, tables, a.assumed_delay_days)
    finance = calculate_financial_exposure(event, tables, a.assumed_delay_days,
                                          daily_penalty_rate=a.daily_penalty_rate)
    rows, orders, capacities = prepare_input(event, options, tables, finance, a.route_capacity_mode)
    result = solve_model(rows, orders, capacities, money_cents(a.uncovered_unit_cost), a.time_limit_seconds)
    print('\nSUPPLYGRID — STEP 6 OPTIMIZATION (USD)')
    print(f'Disruption: {a.supplier}; loss {a.capacity_loss:g}%; duration {a.duration} days')
    print(f"Candidates evaluated: {result['candidates_evaluated']} | eligible: {result['eligible_candidates']}")
    print('Route capacity mode:', a.route_capacity_mode)
    if a.route_capacity_mode == 'single-batch':
        print('ADDITIONAL ASSUMPTION: each route has one shared capacity pool for the whole mitigation batch.')
    print('Disabled candidate reasons:', dict(result['exclusions']))
    print('Solver status:', result['status'])
    if 'selected_actions' not in result:
        print('No usable solution returned. No selected plan reported.')
        return
    print(f"Selected actions: {len(result['selected_actions'])} | orders protected: {result['orders_protected']}")
    print(f"Orders unresolved: {len(result['unresolved_order_ids'])} | unresolved units: {result['unresolved_units']}")
    for key in ('mitigation_cost', 'remaining_penalty', 'uncovered_service_cost', 'objective_value', 'no_action_objective'):
        print(f"{key}: USD {result[key]:,.2f}")
    print(f"Assumed delay for unresolved orders: {a.assumed_delay_days} days; protected orders: on-time warehouse arrival")
    print(f"Best objective bound: USD {result['best_bound_usd']:,.2f}")
    for c in result['selected_actions']:
        print(f"{c['action_id']} | {c['action_type']} | {c['order_id']} | {c['recoverable_units']} product units | USD {c['action_cost']:,.2f} | arrival {c['arrival_date']}")
    print('\nRESOURCE UTILIZATION (used / available):')
    for key, v in result['resource_utilization'].items():
        print(f"{key}: {v['used']} / {v['capacity']}")
    print('\nOptimality applies only to this bounded model. No shipments executed; component-only sourcing disabled.')
    print('Risk proxies are informational. Remaining quantities are unresolved, not proven lost sales.')


if __name__ == '__main__':
    main()
