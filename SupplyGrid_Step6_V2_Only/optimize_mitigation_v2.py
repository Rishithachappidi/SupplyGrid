"""Step 6 v2: joint procurement, dated production and finished-stock recovery.

See README_V2.md for explicit synthetic assumptions and model limits.
Run: python optimize_mitigation_v2.py --data data --extensions data_v2 \
       --assumed-delay-days 10 --route-capacity-mode single-batch --compare-v1
"""
import argparse
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from build_supply_chain_graph import load_tables, build_graph
from propagate_disruption import propagate
from financial_blast_radius import calculate_financial_exposure, decimal, cents
from generate_mitigation_strategies import generate_options
from optimize_mitigation import prepare_input, solve_model, integer, money_cents
from extend_dataset_v2 import load_extension, validate_extension, original_hashes


def days_between(start, finish):
    return [start + timedelta(days=i) for i in range((finish-start).days)]


def production_days(hours):
    h = decimal(hours)
    if h <= 0:
        raise ValueError('Production duration must be positive.')
    return max(1, int((h / 24).to_integral_value(rounding='ROUND_CEILING')))


def effective_capacity(row, scope, event):
    """Commitments have priority after capacity loss; never reduce stock balances."""
    nominal = integer(row[f'{scope}_capacity_units'], 'Nominal capacity')
    committed = integer(row[f'{scope}_committed_units'], 'Committed capacity')
    if row['supplier_id'] == event['supplier'] and event['start_date'] <= row['date'] <= event['end_date_inclusive']:
        nominal = int(decimal(nominal) * (1-decimal(event['capacity_loss_percent'])/100))
    return max(0, nominal-committed)


class Context:
    def __init__(self, tables, ext, event, options, finance, route_mode):
        self.validation = validate_extension(tables, ext)
        self.tables, self.ext, self.event, self.options, self.finance = tables, ext, event, options, finance
        self.route_mode = route_mode
        self.start = date.fromisoformat(event['start_date'])
        self.dates = sorted({date.fromisoformat(x) for x in ext['factory_calendar']['date']})
        if self.start != self.dates[0] or date.fromisoformat(event['end_date_inclusive']) > self.dates[-1]:
            raise ValueError('Extension calendar does not cover the full disruption interval.')
        self.S = tables['suppliers'].set_index('supplier_id').to_dict('index')
        self.C = tables['components'].set_index('component_id').to_dict('index')
        self.P = tables['products'].set_index('product_id').to_dict('index')
        self.routes = tables['routes'].set_index('route_id').to_dict('index')
        self.route_pairs = defaultdict(list)
        for rid, r in self.routes.items():
            self.route_pairs[r['origin_id'],r['destination_id']].append((rid,r))
        self.bom = defaultdict(list)
        for b in tables['bom'].to_dict('records'):
            self.bom[b['product_id']].append(b)
        self.fc = {(r['factory_id'],r['date']):r for r in ext['factory_calendar'].to_dict('records')}
        self.sc = {(r['supplier_id'],r['component_id'],r['date']):r for r in ext['supplier_calendar'].to_dict('records')}
        self.stock = {(r['factory_id'],r['component_id']):integer(r['usable_quantity'],'Factory usable stock')
                      for r in ext['factory_inventory'].to_dict('records')}
        self.screened = {r['order_id']:r for r in event['eligible_orders']}
        self.fg_rows, self.orders, self.fg_capacities = prepare_input(event, options, tables, finance, route_mode)
        self.service_cost_cents = 0

    def procurement_cost(self, sid, cid, day, rid, packs):
        r = self.sc[sid,cid,day]; rt = self.routes[rid]
        moq = integer(r['minimum_order_qty'],'MOQ')
        # Procurement invoices are rounded per MOQ pack, with one route fixed fee per activated lot.
        material = money_cents(decimal(moq)*decimal(r['unit_cost_usd'])) * packs
        variable_transport = money_cents(decimal(moq)*decimal(rt['cost_per_unit'])) * packs
        fixed_transport = money_cents(rt['estimated_transit_cost']) if packs else 0
        return dict(procurement_material_cents=material, inbound_transport_cents=variable_transport+fixed_transport)

    def job_cost(self, fid, day, rid, quantity):
        r = self.fc[fid,day]; rt = self.routes[rid]
        operating = money_cents(decimal(quantity)*decimal(r['operating_cost_per_unit_usd']))
        labor = money_cents(decimal(quantity)*decimal(r['labor_cost_per_unit_usd']))
        shipping = money_cents(decimal(quantity)*decimal(rt['cost_per_unit'])+decimal(rt['estimated_transit_cost']))
        return dict(conversion_operating_cents=operating, conversion_labor_cents=labor,
                    finished_product_transport_cents=shipping)


def build_production_and_procurement(ctx):
    """Enumerate dates/routes, not material purchase quantities or final choices."""
    jobs = []; limits = Counter(); needs = defaultdict(set)
    for oid in ctx.orders:
        o = ctx.screened[oid]; pid = o['product_id']; fid = o['factory_id']
        due = date.fromisoformat(o['required_date']); qty = ctx.orders[oid]['quantity']
        duration = production_days(ctx.P[pid]['production_time_hours'])
        outgoing = ctx.route_pairs[fid,o['warehouse_id']]
        if not outgoing:
            limits['No factory-to-order-warehouse route'] += 1
        for rid,rt in outgoing:
            if qty > integer(rt['route_capacity'],'Outbound route capacity'):
                limits['Outbound consignment exceeds route capacity'] += 1; continue
            for start in ctx.dates:
                finish = start + timedelta(days=duration)
                arrival = finish + timedelta(days=integer(rt['normal_transit_days'],'Outbound transit'))
                if arrival > due:
                    continue
                occupied = days_between(start, finish)
                if any((fid,d.isoformat()) not in ctx.fc or qty > integer(ctx.fc[fid,d.isoformat()]['available_capacity_units'],'Factory availability') for d in occupied):
                    limits['Insufficient local production slots'] += 1; continue
                job = dict(job_id=f'J{len(jobs)+1:06d}', order_id=oid, product_id=pid,
                    factory_id=fid, quantity=qty, start_date=start.isoformat(), finish_date=finish.isoformat(),
                    arrival_date=arrival.isoformat(), outbound_route_id=rid)
                job['cost_breakdown_cents'] = ctx.job_cost(fid,start.isoformat(),rid,qty)
                jobs.append(job)
                for b in ctx.bom[pid]:
                    for cid in (b['component_id'],b['substitute_component_id']):
                        if cid:
                            needs[fid,cid].add(start.isoformat())
    lots = []
    for (fid,cid), need_dates in sorted(needs.items()):
        sid = ctx.C[cid]['supplier_id']
        latest = max(need_dates)
        for rid,rt in ctx.route_pairs[sid,fid]:
            for reservation in ctx.dates:
                day = reservation.isoformat(); row = ctx.sc[sid,cid,day]
                dispatch = reservation + timedelta(days=integer(row['lead_time_days'],'Procurement lead time'))
                arrival = dispatch + timedelta(days=integer(rt['normal_transit_days'],'Inbound transit'))
                if arrival.isoformat() > latest:
                    continue
                moq = integer(row['minimum_order_qty'],'MOQ')
                upper = min(effective_capacity(row,'supplier',ctx.event),
                            effective_capacity(row,'component',ctx.event), integer(rt['route_capacity'],'Inbound route capacity')) // moq
                if upper < 1:
                    limits['No MOQ-sized supplier/component/route availability'] += 1; continue
                lots.append(dict(lot_id=f'L{len(lots)+1:06d}', supplier_id=sid, component_id=cid,
                    factory_id=fid, reservation_date=day, dispatch_date=dispatch.isoformat(),
                    arrival_date=arrival.isoformat(), route_id=rid, moq=moq, maximum_packs=upper))
    incoming = defaultdict(list)
    for lot in lots:
        incoming[lot['factory_id'],lot['component_id']].append(lot)
    valid_jobs = []
    # Reject only provably impossible jobs; upper bounds may overestimate shared supply.
    for job in jobs:
        ok = True
        for b in ctx.bom[job['product_id']]:
            sources = [x for x in (b['component_id'],b['substitute_component_id']) if x]
            optimistic = sum(ctx.stock.get((job['factory_id'],cid),0) +
                sum(l['moq']*l['maximum_packs'] for l in incoming[job['factory_id'],cid] if l['arrival_date'] <= job['start_date']) for cid in sources)
            if optimistic < job['quantity']*integer(b['quantity_required'],'BOM coefficient'):
                ok = False; break
        if ok:
            valid_jobs.append(job)
        else:
            limits['BOM material impossible before production start'] += 1
    return valid_jobs, lots, limits


def audit_plan(ctx, plan, service_cost_cents=0):
    """Reconstruct timing, BOM, resources and costs from source rows, not model coefficients."""
    def require(ok,msg):
        if not ok:
            raise ArithmeticError(msg)
    require(service_cost_cents >= 0, 'Negative service cost')
    usage = defaultdict(int); caps = {}; received = defaultdict(int); consumed = defaultdict(int)
    cost = defaultdict(int); covered = {}; inventory_demands = defaultdict(int)
    source_actions = {r['candidate']['action_id']:r for r in ctx.fg_rows}
    for action in plan['finished_transfers']:
        aid = action['action_id']
        require(aid in source_actions, 'Unknown finished-stock action')
        source = source_actions[aid]
        normalized_action = dict(action)
        normalized_action['action_cost'] = decimal(action['action_cost'])
        require(source['enabled'] and normalized_action == source['candidate'], 'Disabled or modified finished-stock action')
        oid = action['order_id']
        require(oid not in covered, 'Order covered more than once')
        covered[oid] = 'finished_stock'
        qty = integer(action['recoverable_units'],'Transfer quantity')
        rt = ctx.routes[action['route_id']]
        quoted = money_cents(decimal(qty)*decimal(rt['cost_per_unit'])+decimal(rt['estimated_transit_cost']))
        require(quoted == money_cents(action['action_cost']), 'Finished transfer cost mismatch')
        expected_arrival = ctx.start + timedelta(days=integer(rt['normal_transit_days'],'Transfer transit'))
        require(expected_arrival.isoformat() == action['arrival_date'], 'Finished transfer timing mismatch')
        require(expected_arrival <= date.fromisoformat(ctx.screened[oid]['required_date']), 'Finished transfer late')
        cost['finished_stock_transport_cents'] += quoted
        k = f"stock:{action['source_location']}:{action['product_id']}"
        usage[k] += qty; caps[k] = ctx.fg_capacities[k]
        require(qty <= integer(rt['route_capacity'],'Route capacity'), 'Transfer consignment too large')
        k = 'route:' + action['route_id']; usage[k] += qty; caps[k] = integer(rt['route_capacity'],'Route capacity')
    lot_ids = set()
    for lot in plan['procurement_lots']:
        require(lot['lot_id'] not in lot_ids, 'Duplicate procurement lot')
        lot_ids.add(lot['lot_id'])
        sid,cid,fid,rid,day = [lot[k] for k in ('supplier_id','component_id','factory_id','route_id','reservation_date')]
        require(cid in ctx.C and sid == ctx.C[cid]['supplier_id'], 'Procurement supplier ownership mismatch')
        require((fid,cid) in ctx.stock and (sid,cid,day) in ctx.sc, 'Invalid procurement factory/component/date')
        rt = ctx.routes[rid]; row = ctx.sc[sid,cid,day]
        require((rt['origin_id'],rt['destination_id']) == (sid,fid), 'Inbound route endpoints mismatch')
        moq = integer(row['minimum_order_qty'],'MOQ'); packs = integer(lot['packs'],'Procurement packs')
        qty = integer(lot['quantity'],'Procurement quantity')
        require(packs > 0 and qty == packs*moq and lot['moq'] == moq, 'Procurement violates MOQ pack quantity')
        dispatch = date.fromisoformat(day)+timedelta(days=integer(row['lead_time_days'],'Lead time'))
        arrival = dispatch+timedelta(days=integer(rt['normal_transit_days'],'Inbound transit'))
        require(dispatch.isoformat() == lot['dispatch_date'] and arrival.isoformat() == lot['arrival_date'], 'Procurement timing mismatch')
        require(arrival <= ctx.dates[-1], 'Procurement arrives outside horizon')
        received[fid,cid,arrival.isoformat()] += qty
        for scope,item in [('supplier',sid),('component',cid)]:
            k = f'{scope}:{item}:{day}'; usage[k] += qty; caps[k] = effective_capacity(row,scope,ctx.event)
        k = 'route:' + rid; usage[k] += qty; caps[k] = integer(rt['route_capacity'],'Route capacity')
        require(qty <= caps[k], 'Inbound consignment exceeds route capacity')
        expected = ctx.procurement_cost(sid,cid,day,rid,packs)
        require(expected == lot['cost_breakdown_cents'], 'Procurement cost decomposition mismatch')
        for k,v in expected.items():
            cost[k] += v
    job_ids = set()
    for job in plan['production_jobs']:
        require(job['job_id'] not in job_ids, 'Duplicate production job')
        job_ids.add(job['job_id'])
        oid,pid,fid,rid = [job[k] for k in ('order_id','product_id','factory_id','outbound_route_id')]
        require(oid in ctx.orders and oid not in covered, 'Unknown or multiply-covered production order')
        o = ctx.screened[oid]
        require(pid == o['product_id'] and fid == ctx.P[pid]['factory_id'], 'Wrong production product/factory')
        qty = integer(job['quantity'],'Production quantity')
        require(qty == ctx.orders[oid]['quantity'], 'Production does not cover full uncovered order')
        start = date.fromisoformat(job['start_date'])
        finish = start+timedelta(days=production_days(ctx.P[pid]['production_time_hours']))
        rt = ctx.routes[rid]
        require((rt['origin_id'],rt['destination_id']) == (fid,o['warehouse_id']), 'Outbound production route mismatch')
        arrival = finish+timedelta(days=integer(rt['normal_transit_days'],'Outbound transit'))
        require(finish.isoformat() == job['finish_date'] and arrival.isoformat() == job['arrival_date'], 'Production completion/arrival mismatch')
        require(start >= ctx.start and arrival <= date.fromisoformat(o['required_date']), 'Production pathway misses timing/deadline')
        for d in days_between(start,finish):
            require((fid,d.isoformat()) in ctx.fc, 'Production outside calendar horizon')
            k = f'factory:{fid}:{d.isoformat()}'
            usage[k] += qty; caps[k] = integer(ctx.fc[fid,d.isoformat()]['available_capacity_units'],'Factory availability')
        required = {b['component_id']:b for b in ctx.bom[pid]}
        material_sums = defaultdict(int); seen_allocations = set()
        for alloc in job['materials']:
            req,cid = alloc['required_component_id'],alloc['physical_component_id']
            require(req in required, 'Material not in product BOM')
            require(cid in (req,required[req]['substitute_component_id']), 'Unapproved product-specific substitute')
            require((req,cid) not in seen_allocations, 'Duplicate BOM material allocation')
            seen_allocations.add((req,cid))
            q = integer(alloc['quantity'],'Allocated material quantity')
            require(q > 0, 'Zero material allocation')
            material_sums[req] += q; consumed[fid,cid,start.isoformat()] += q
            inventory_demands[fid,cid] += q
        for cid,b in required.items():
            require(material_sums[cid] == qty*integer(b['quantity_required'],'BOM coefficient'), 'BOM requirement not fully satisfied')
        k = 'route:' + rid; usage[k] += qty; caps[k] = integer(rt['route_capacity'],'Outbound route capacity')
        require(qty <= caps[k], 'Outbound consignment exceeds route capacity')
        expected = ctx.job_cost(fid,start.isoformat(),rid,qty)
        require(expected == job['cost_breakdown_cents'], 'Production cost decomposition mismatch')
        for k,v in expected.items():
            cost[k] += v
        covered[oid] = 'production'
    balances = {}
    material_keys = {(f,c) for f,c,_ in received} | {(f,c) for f,c,_ in consumed}
    for fid,cid in sorted(material_keys):
        opening = ctx.stock.get((fid,cid),0); balance = opening; total_in = 0; total_out = 0
        for d in ctx.dates:
            incoming = received[fid,cid,d.isoformat()]; outgoing = consumed[fid,cid,d.isoformat()]
            balance += incoming-outgoing; total_in += incoming; total_out += outgoing
            require(balance >= 0, f'Factory material shortage/double-use before start: {fid}/{cid}/{d}')
        balances[f'{fid}:{cid}'] = dict(opening_usable=opening, procured=total_in, consumed=total_out, closing_usable=balance)
    for key,q in usage.items():
        if key.startswith('route:') and ctx.route_mode == 'per-consignment':
            continue  # Individual consignments were checked above; no invented shared daily pool.
        require(q <= caps[key], f'Shared resource exceeded: {key}')
    unresolved = [oid for oid in ctx.orders if oid not in covered]
    cost['remaining_penalty_cents'] = sum(ctx.orders[oid]['penalty_cents'] for oid in unresolved)
    cost['unresolved_service_cents'] = sum(ctx.orders[oid]['quantity'] for oid in unresolved)*service_cost_cents
    return dict(status='PASSED', checks_passed=['finished-stock limits', 'route endpoints/capacity',
        'supplier dated capacity after disruption', 'component dated capacity after disruption',
        'MOQ and supplier ownership', 'factory dated occupied slots', 'BOM and product-specific substitutions',
        'cumulative factory inventory/no double-use', 'procurement arrival before material consumption',
        'production duration and order warehouse deadline', 'one full recovery path per order', 'cost decomposition'],
        cost_breakdown_cents=dict(cost), total_cost_cents=sum(cost.values()), orders_protected=len(covered),
        production_orders=sum(v == 'production' for v in covered.values()),
        finished_stock_orders=sum(v == 'finished_stock' for v in covered.values()),
        unresolved_order_ids=unresolved, unresolved_units=sum(ctx.orders[oid]['quantity'] for oid in unresolved),
        resource_utilization={k:dict(used=q,capacity=caps[k],scope='per-consignment; usage shown is aggregate only' if k.startswith('route:') and ctx.route_mode == 'per-consignment' else 'shared') for k,q in sorted(usage.items())},
        factory_material_balances=balances)


def optimize_v2(ctx, service_cost_cents=0, time_limit_seconds=60):
    from ortools.linear_solver import pywraplp
    service_cost_cents = integer(service_cost_cents,'Service cost cents')
    if time_limit_seconds <= 0:
        raise ValueError('Positive solver time limit required.')
    jobs,lots,limits = build_production_and_procurement(ctx)
    solver = pywraplp.Solver.CreateSolver('SCIP')
    if solver is None:
        raise RuntimeError('SCIP backend unavailable.')
    solver.SetTimeLimit(int(time_limit_seconds*1000)); solver.SetNumThreads(1)
    fg = {r['action_id']:solver.IntVar(0,int(r['enabled']),r['action_id']) for r in ctx.fg_rows}
    job_vars = {j['job_id']:solver.BoolVar(j['job_id']) for j in jobs}
    unresolved = {oid:solver.BoolVar('unresolved_'+oid) for oid in ctx.orders}
    pack_vars = {l['lot_id']:solver.IntVar(0,l['maximum_packs'],'packs_'+l['lot_id']) for l in lots}
    lot_vars = {l['lot_id']:solver.BoolVar('active_'+l['lot_id']) for l in lots}
    terms = defaultdict(list); capacities = dict(ctx.fg_capacities); by_order = defaultdict(list)
    objective = solver.Objective()
    for r in ctx.fg_rows:
        v = fg[r['action_id']]; by_order[r['order_id']].append(v)
        objective.SetCoefficient(v,r['cost_cents'])
        for key,qty in r['demands'].items():
            terms[key].append(qty*v)
    incoming = defaultdict(list)
    for lot in lots:
        lid = lot['lot_id']; pv = pack_vars[lid]; active = lot_vars[lid]; moq = lot['moq']
        solver.Add(pv <= lot['maximum_packs']*active); solver.Add(pv >= active)
        day,sid,cid = lot['reservation_date'],lot['supplier_id'],lot['component_id']
        row = ctx.sc[sid,cid,day]; rt = ctx.routes[lot['route_id']]
        for scope,item in [('supplier',sid),('component',cid)]:
            key = f'{scope}:{item}:{day}'; terms[key].append(moq*pv)
            capacities[key] = effective_capacity(row,scope,ctx.event)
        if ctx.route_mode == 'single-batch':
            key = f"route:{lot['route_id']}:consignment"; terms[key].append(moq*pv)
            capacities[key] = integer(rt['route_capacity'],'Route capacity')
        incoming[lot['factory_id'],cid].append((lot['arrival_date'],moq*pv))
        pack_cost = money_cents(decimal(moq)*decimal(row['unit_cost_usd'])) + money_cents(decimal(moq)*decimal(rt['cost_per_unit']))
        objective.SetCoefficient(pv,pack_cost)
        objective.SetCoefficient(active,money_cents(rt['estimated_transit_cost']))
    consumed = defaultdict(list); allocation_vars = {}
    for job in jobs:
        jid = job['job_id']; v = job_vars[jid]; fid = job['factory_id']; qty = job['quantity']
        by_order[job['order_id']].append(v)
        objective.SetCoefficient(v,sum(job['cost_breakdown_cents'].values()))
        for d in days_between(date.fromisoformat(job['start_date']), date.fromisoformat(job['finish_date'])):
            key = f'factory:{fid}:{d.isoformat()}'
            terms[key].append(qty*v); capacities[key] = integer(ctx.fc[fid,d.isoformat()]['available_capacity_units'],'Factory availability')
        if ctx.route_mode == 'single-batch':
            key = f"route:{job['outbound_route_id']}:consignment"; terms[key].append(qty*v)
            capacities[key] = integer(ctx.routes[job['outbound_route_id']]['route_capacity'],'Outbound route capacity')
        for b in ctx.bom[job['product_id']]:
            requirement = qty*integer(b['quantity_required'],'BOM coefficient')
            sources = list(dict.fromkeys(x for x in (b['component_id'],b['substitute_component_id']) if x))
            allocations = []
            for cid in sources:
                z = solver.IntVar(0,requirement,f"material_{jid}_{b['component_id']}_{cid}")
                allocation_vars[jid,b['component_id'],cid] = z
                allocations.append(z); consumed[fid,cid].append((job['start_date'],z))
            solver.Add(solver.Sum(allocations) == requirement*v)
    for oid in ctx.orders:
        solver.Add(solver.Sum(by_order[oid])+unresolved[oid] == 1)
        o = ctx.orders[oid]
        objective.SetCoefficient(unresolved[oid],o['penalty_cents']+o['quantity']*service_cost_cents)
    for key, expressions in terms.items():
        solver.Add(solver.Sum(expressions) <= capacities[key])
    for (fid,cid), material_terms in consumed.items():
        relevant_dates = sorted({day for day,_ in material_terms})
        for day in relevant_dates:
            lhs = solver.Sum(z for d,z in material_terms if d <= day)
            rhs = ctx.stock.get((fid,cid),0)+solver.Sum(z for d,z in incoming[fid,cid] if d <= day)
            solver.Add(lhs <= rhs)
    objective.SetMinimization()
    status = solver.Solve()
    names = {solver.OPTIMAL:'OPTIMAL',solver.FEASIBLE:'FEASIBLE',solver.INFEASIBLE:'INFEASIBLE',
             solver.UNBOUNDED:'UNBOUNDED',solver.ABNORMAL:'ABNORMAL',solver.NOT_SOLVED:'NOT_SOLVED'}
    result = dict(status=names.get(status,str(status)), solver=solver.SolverVersion(),
        original_step5_candidates=len(ctx.fg_rows), full_on_time_stock_candidates=sum(r['enabled'] for r in ctx.fg_rows),
        production_job_candidates=len(jobs), procurement_lot_candidates=len(lots),
        production_candidate_limits=dict(limits), variables=solver.NumVariables(), constraints=solver.NumConstraints(),
        route_capacity_mode=ctx.route_mode)
    if status not in (solver.OPTIMAL,solver.FEASIBLE):
        return result
    if not solver.VerifySolution(1e-7,True):
        raise ArithmeticError('Solver verification failed.')
    def solved_int(v):
        value = v.solution_value(); rounded = round(value)
        if abs(value-rounded) > 1e-6:
            raise ArithmeticError('Nonintegral incumbent.')
        return rounded
    selected_jobs = []
    for job in jobs:
        if solved_int(job_vars[job['job_id']]):
            item = dict(job); item['materials'] = []
            for (jid,req,cid),z in allocation_vars.items():
                if jid == job['job_id'] and solved_int(z):
                    item['materials'].append(dict(required_component_id=req,physical_component_id=cid,quantity=solved_int(z)))
            selected_jobs.append(item)
    selected_lots = []
    for lot in lots:
        packs = solved_int(pack_vars[lot['lot_id']])
        if packs:
            item = dict(lot); item.update(packs=packs,quantity=packs*lot['moq'],
                cost_breakdown_cents=ctx.procurement_cost(lot['supplier_id'],lot['component_id'],lot['reservation_date'],lot['route_id'],packs))
            selected_lots.append(item)
    plan = dict(finished_transfers=[r['candidate'] for r in ctx.fg_rows if solved_int(fg[r['action_id']])],
                production_jobs=selected_jobs, procurement_lots=selected_lots)
    audit = audit_plan(ctx,plan,service_cost_cents)
    if abs(objective.Value()-audit['total_cost_cents']) > 0.01:
        raise ArithmeticError('Independent cost audit does not match objective.')
    result.update(plan=plan,audit=audit,objective_value=Decimal(audit['total_cost_cents'])/100,
        best_bound_usd=objective.BestBound()/100,wall_time_ms=solver.WallTime(),
        original_candidate_decisions={aid:solved_int(v) for aid,v in fg.items()})
    return result


def run_comparison(tables, ext, supplier='S037', loss=80, duration=10, delay=10,
                   penalty_rate='0.001', service_cost='0', route_mode='single-batch', time_limit=60, compare=True):
    graph = build_graph(tables)
    event = propagate(graph,tables,supplier,loss,duration)
    options = generate_options(event,graph,tables,delay)
    finance = calculate_financial_exposure(event,tables,delay,daily_penalty_rate=penalty_rate)
    ctx = Context(tables,ext,event,options,finance,route_mode)
    result = dict(scenario=dict(supplier=supplier,capacity_loss_percent=loss,duration_days=duration,
        assumed_delay_days=delay,daily_penalty_rate=penalty_rate,unresolved_unit_service_cost_usd=service_cost,
        route_capacity_mode=route_mode,snapshot=event['start_date']), extension_validation=ctx.validation)
    unit_cost = money_cents(service_cost)
    if compare:
        result['v1'] = solve_model(ctx.fg_rows,ctx.orders,ctx.fg_capacities,unit_cost,time_limit)
    result['v2'] = optimize_v2(ctx,unit_cost,time_limit)
    if compare and result['v1']['status'] == 'OPTIMAL' and result['v2']['status'] == 'OPTIMAL':
        if result['v2']['objective_value'] > result['v1']['objective_value']:
            raise ArithmeticError('V2 rejected a feasible v1 plan or cost scope differs.')
        result['comparison_scope'] = 'Same exposed orders, penalty assumptions and route mode; v2 adds synthetic factory/procurement resources. Not evidence of universal superiority.'
    return result


def json_default(value):
    if isinstance(value,Decimal):
        return str(value)
    raise TypeError(f'Unsupported JSON type: {type(value)}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default='data'); ap.add_argument('--extensions',default='data_v2')
    ap.add_argument('--supplier',default='S037'); ap.add_argument('--capacity-loss',type=float,default=80)
    ap.add_argument('--duration',type=int,default=10); ap.add_argument('--assumed-delay-days',type=int,required=True)
    ap.add_argument('--daily-penalty-rate',default='0.001'); ap.add_argument('--uncovered-unit-cost',default='0')
    ap.add_argument('--route-capacity-mode',choices=['single-batch','per-consignment'],default='single-batch')
    ap.add_argument('--time-limit-seconds',type=int,default=60); ap.add_argument('--compare-v1',action='store_true')
    ap.add_argument('--output',help='Optional JSON plan and independent audit report')
    a = ap.parse_args()
    before = original_hashes(a.data)
    tables = load_tables(a.data); ext = load_extension(a.extensions)
    # Data validation must pass before a solver is constructed.
    validation = validate_extension(tables,ext)
    print('NEW DATA VALIDATION:',validation['status'],validation['actual_row_counts'],flush=True)
    result = run_comparison(tables,ext,a.supplier,a.capacity_loss,a.duration,a.assumed_delay_days,
        a.daily_penalty_rate,a.uncovered_unit_cost,a.route_capacity_mode,a.time_limit_seconds,a.compare_v1)
    after = original_hashes(a.data)
    if before != after:
        raise ArithmeticError('Original CSV bytes changed.')
    result['original_files_unchanged'] = True
    print('\nSUPPLYGRID STEP 6 V2 — CONDITIONAL END-TO-END MODEL (USD)')
    print('Scenario:',result['scenario'])
    if a.route_capacity_mode == 'single-batch':
        print('ASSUMPTION: route capacity is one shared pool for this entire mitigation batch, not measured daily availability.')
    for version in ('v1','v2'):
        if version not in result:
            continue
        r = result[version]; print(f'\n{version.upper()} STATUS: {r["status"]}')
        if version == 'v1' and 'objective_value' in r:
            print(f"Orders protected: {r['orders_protected']}; unresolved: {len(r['unresolved_order_ids'])}; modeled cost: USD {r['objective_value']:,.2f}")
        elif version == 'v2':
            print(f"Stock candidates: {r['original_step5_candidates']}; production candidates: {r['production_job_candidates']}; procurement candidates: {r['procurement_lot_candidates']}")
            if 'audit' not in r:
                print('No selected plan available.'); continue
            audit = r['audit']
            print(f"Protected: {audit['orders_protected']} (stock {audit['finished_stock_orders']}, production {audit['production_orders']}); unresolved: {len(audit['unresolved_order_ids'])}")
            print(f"Selected procurement lots: {len(r['plan']['procurement_lots'])}; modeled cost: USD {r['objective_value']:,.2f}")
            print('INDEPENDENT PLAN AUDIT:',audit['status'])
            for key,v in audit['cost_breakdown_cents'].items():
                print(f'  {key.removesuffix("_cents")}: USD {Decimal(v)/100:,.2f}')
            for j in r['plan']['production_jobs']:
                print(f"  {j['job_id']} | {j['order_id']} | produce {j['quantity']} {j['product_id']} at {j['factory_id']} | {j['start_date']} to {j['finish_date']} | warehouse arrival {j['arrival_date']}")
            for l in r['plan']['procurement_lots']:
                print(f"  {l['lot_id']} | procure {l['quantity']} {l['component_id']} from {l['supplier_id']} | {l['route_id']} to {l['factory_id']} | arrival {l['arrival_date']}")
    print('\nNo execution, prediction or real-world optimality claimed. Factory stock is separate from warehouse stock.')
    if a.output:
        path = Path(a.output)
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite existing report: {path}')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2,default=json_default)+'\n')
        print('Report:',path)


if __name__ == '__main__':
    main()
