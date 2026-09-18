"""SupplyGrid/SynapseChain Step 5: generate locally screened candidates, never select a plan.

Place beside your Step 2, 3 and 4 Python files and the data folder.
Install: python -m pip install pandas networkx
Run:
 python generate_mitigation_strategies.py --data data --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10

Currency: USD. Cost is a transport or procurement quote, NOT a complete recovery
outcome or proven savings. Time saved compares candidate arrival to required_date
plus the explicitly assumed baseline delay from Step 4. No causal baseline delivery
model exists yet. A positive saving is conditional, not an observed improvement.

Supplier alternatives require the specific product's BOM-approved substitute and
an actual supplier-to-factory route. Component MOQ and dispatch capacity are checked.
They are component-only candidates: other components/production readiness remain
unverified. Inventory transfers use finished products, real warehouse routes, and
stock remaining after Step 3's ALL-product pending-order allocations, above safety.
Local feasibility permits partial coverage and lateness if better than the assumed
baseline. Distinguish full_order_quantity_covered from local feasibility.

No candidate is executed, ranked as optimal, or reserved. Options compete for shared
resources. Summing their capacities, costs or time savings is invalid. Step 6 must
enforce those capacities jointly. route_capacity is per consignment; supplier/component
capacity is daily. Inventory is a snapshot. Handling hours and contractual shipping
cutoffs are absent: arrival is an optimistic quote based on listed transit days.

success_probability_proxy is an uncalibrated independence approximation from synthetic
reliability/risk attributes. It is NOT an empirical or guaranteed success probability.
Risk proxy = 1 - success proxy. Factory stock access, other-BOM readiness, manufacturing
slots and live stock availability are not established by this screening.
"""
import argparse
import math
from collections import Counter, defaultdict
from datetime import date, timedelta

from build_supply_chain_graph import load_tables, build_graph
from propagate_disruption import propagate, inventory_screen
from financial_blast_radius import calculate_financial_exposure, decimal, cents


def generate_options(propagation, graph, tables, assumed_delay_days):
    """Return candidate dictionaries and explicit rejections; no mutation or selection."""
    if isinstance(assumed_delay_days, bool) or not isinstance(assumed_delay_days, int) or assumed_delay_days < 0:
        raise ValueError('Assumed baseline delay must be a nonnegative integer.')
    start = date.fromisoformat(propagation['start_date'])
    end = date.fromisoformat(propagation['end_date_inclusive'])
    supplier = propagation['supplier']
    S={r['supplier_id']:r for r in tables['suppliers'].to_dict('records')}
    C={r['component_id']:r for r in tables['components'].to_dict('records')}
    P={r['product_id']:r for r in tables['products'].to_dict('records')}
    W={r['warehouse_id']:r for r in tables['warehouses'].to_dict('records')}
    routes=defaultdict(list)
    for r in tables['routes'].to_dict('records'): routes[r['origin_id'],r['destination_id']].append(r)
    bom=defaultdict(list)
    for b in tables['bom'].to_dict('records'):
        if b['component_id'] not in C: raise ValueError('Unknown BOM component')
        if C[b['component_id']]['supplier_id']==supplier: bom[b['product_id']].append(b)
    # Account for existing ALL-product allocations before considering spare finished stock.
    stock=defaultdict(int); safety=defaultdict(int)
    for r in tables['inventory'].to_dict('records'):
        if r['product_id']:
            key=(r['warehouse_id'],r['product_id'])
            stock[key]+=int(r['available_quantity']); safety[key]+=int(r['safety_stock'])
    allocated=inventory_screen(graph,tables,set(P),start,end)
    for o in allocated: stock[o['warehouse_id'],o['product_id']]-=o['finished_stock_covered_units']
    spare={key:max(0,qty-safety[key]) for key,qty in stock.items()}
    screened={o['order_id']:o for o in propagation['eligible_orders']}
    ids=propagation['potential_order_ids']
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate potentially affected orders')
    candidates=[]; rejected=[]
    def reject(oid,typ,reason,cid=''):
        rejected.append(dict(order_id=oid,action_type=typ,component_id=cid,reason=reason))
    def append(candidate):
        candidate['action_id']=f"MG{len(candidates)+1:06d}"
        candidate['currency']='USD'
        candidate['success_probability_proxy']=round(candidate['success_probability_proxy'],6)
        candidate['risk_score_proxy']=round(1-candidate['success_probability_proxy'],6)
        candidates.append(candidate)
    def proxy(rt,first,last=1):
        vals=[first,last,1-float(rt['weather_risk']),1-float(rt['congestion_risk']),1-float(rt['geopolitical_risk'])]
        if any(not 0<=v<=1 for v in vals): raise ValueError('Reliability and risk inputs must be between 0 and 1')
        return math.prod(vals)
    for oid in ids:
        if oid not in screened: raise ValueError('Unscreened order ID')
        o=screened[oid]; pid=o['product_id']; fid=o['factory_id']; dest=o['warehouse_id']; need=int(o['uncovered_units'])
        if need<=0: raise ValueError('Mitigation requires positive uncovered quantity')
        due=date.fromisoformat(o['required_date']); baseline=due+timedelta(days=assumed_delay_days)
        # Finished product stock bypasses the disrupted component dependency.
        found_transfer=False
        for (source,item),available in sorted(spare.items()):
            if item!=pid or source==dest or available<=0: continue
            direct=routes[source,dest]
            if not direct:
                reject(oid,'Reallocate_Inventory','Spare product stock exists, but no direct delivery route from '+source)
                continue
            for rt in direct:
                qty=min(need,available,int(rt['route_capacity']))
                arrival=start+timedelta(days=int(rt['normal_transit_days']))
                saved=(baseline-arrival).days
                if qty<=0 or saved<=0:
                    reject(oid,'Reallocate_Inventory','No dispatch capacity or no improvement versus assumed baseline')
                    continue
                found_transfer=True
                quote=cents(decimal(qty)*decimal(rt['cost_per_unit'])+decimal(rt['estimated_transit_cost']))
                append(dict(order_id=oid,product_id=pid,action_type='Expedite_Inventory_Transfer' if rt['transport_mode']=='Air' else 'Reallocate_Inventory',
                    component_id='',supplier_id='',factory_id=fid,route_id=rt['route_id'],source_location=source,destination_location=dest,
                    available_capacity=available,recoverable_units=qty,quantity_basis='finished product units',
                    action_cost=quote,cost_basis='Transport-only quote: variable cost plus fixed dispatch fee',
                    implementation_time=int(rt['normal_transit_days']),arrival_date=arrival.isoformat(),time_saved_days=saved,
                    timing_basis='Finished-stock arrival improvement versus assumed baseline',
                    remaining_late_days=max(0,(arrival-due).days),success_probability_proxy=proxy(rt,float(W[source]['reliability_score']),float(W[dest]['reliability_score'])),
                    feasible=True,feasibility_scope='Local finished-product transfer; handling time and joint commitments not modeled',
                    full_order_quantity_covered=qty==need,
                    resource_demands={f'stock:{source}:{pid}':qty,f'route:{rt["route_id"]}:consignment':qty},
                    assumptions=['Spare unreserved stock above safety after existing allocations','Direct listed route','No additional handling time']))
        if not found_transfer:
            reject(oid,'Reallocate_Inventory','No locally feasible direct finished-product transfer found')
        # Each BOM-approved alternative is a COMPONENT candidate, not a full plan.
        for b in bom[pid]:
            cid=b['component_id']; alternative=b['substitute_component_id']
            if not alternative:
                reject(oid,'Switch_Supplier','No BOM-approved substitute for this product',cid)
                continue
            if alternative not in C: raise ValueError('Invalid substitute ID')
            alt=C[alternative]; sid=alt['supplier_id']
            if sid not in S: raise ValueError('Invalid alternate supplier ID')
            if sid==supplier or alt['category']!=C[cid]['category']:
                reject(oid,'Switch_Supplier','Substitute is not category-compatible or uses disrupted supplier',cid)
                continue
            direct=routes[sid,fid]
            if not direct:
                reject(oid,'Switch_Supplier','No listed alternate-supplier-to-factory route',cid)
                continue
            units_required=need*int(b['quantity_required']); moq=int(alt['minimum_order_qty'])
            if moq<=0: raise ValueError('Minimum order quantity must be positive')
            purchase=math.ceil(units_required/moq)*moq
            for rt in direct:
                cap=min(int(alt['maximum_supply']),int(S[sid]['component_capacity']),int(rt['route_capacity']))
                lead=int(alt['lead_time_days'])+int(rt['normal_transit_days'])
                # Arrival of this component only; no unverified manufacturing schedule is invented.
                arrival=start+timedelta(days=lead)
                latest=baseline-timedelta(days=math.ceil(float(P[pid]['production_time_hours'])/24))
                outbound=routes[fid,dest]
                if not outbound:
                    reject(oid,'Switch_Supplier','No factory-to-order-warehouse route',cid);continue
                latest-=timedelta(days=min(int(x['normal_transit_days']) for x in outbound))
                saved=(latest-arrival).days
                if purchase>cap or saved<=0:
                    reject(oid,'Switch_Supplier','MOQ-adjusted quote exceeds capacity or arrives too late for optimistic recovery window',cid)
                    continue
                quote=cents(decimal(purchase)*decimal(alt['unit_cost'])+decimal(purchase)*decimal(rt['cost_per_unit'])+decimal(rt['estimated_transit_cost']))
                append(dict(order_id=oid,product_id=pid,action_type='Switch_Supplier',component_id=alternative,
                    replaces_component_id=cid,supplier_id=sid,factory_id=fid,route_id=rt['route_id'],source_location=sid,destination_location=fid,
                    available_capacity=cap,recoverable_units=purchase,required_component_units=units_required,
                    surplus_component_units=purchase-units_required,quantity_basis='component units',action_cost=quote,
                    cost_basis='Full MOQ-adjusted component purchase plus inbound transport; not incremental premium',
                    implementation_time=lead,arrival_date=arrival.isoformat(),time_saved_days=saved,remaining_late_days=None,
                    timing_basis='Component-arrival slack before optimistic latest-needed date; NOT proven order time saved',
                    success_probability_proxy=proxy(rt,float(S[sid]['reliability_score']),float(S[sid]['quality_rate'])),
                    feasible=True,feasibility_scope='Local component procurement ONLY; no product-production guarantee',
                    full_order_quantity_covered=False,
                    resource_demands={f'component:{alternative}:day':purchase,f'supplier:{sid}:day':purchase,f'route:{rt["route_id"]}:consignment':purchase},
                    assumptions=['Product-specific BOM approval','MOQ respected','Other components and manufacturing slots unverified','Daily capacity uncommitted in local quote']))
            # Warehouse components cannot be credited unless a return route to factory exists.
        reject(oid,'Use_Component_Inventory','Warehouse component inventory is not factory stock; factory access and inbound allocation are not modeled')
        reject(oid,'Adjust_Production','Missing factory component balances and scheduled production slots; cannot establish material-ready capacity')
        reject(oid,'Reroute_Original_Supply','No shipment-specific disruption/alternate original-supply path established; warehouse transfers are separate candidates')
    return dict(candidates=candidates,rejections=rejected,spare_finished_stock=spare,
        baseline_assumed_delay_days=assumed_delay_days,selected_plan=None)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',default='data')
    ap.add_argument('--supplier',default='S037')
    ap.add_argument('--capacity-loss',type=float,default=80)
    ap.add_argument('--duration',type=int,default=10)
    ap.add_argument('--assumed-delay-days',required=True,type=int)
    ap.add_argument('--show',type=int,default=10,help='Number of options printed; all remain in the returned result')
    a=ap.parse_args()
    if a.assumed_delay_days<0 or a.show<0: ap.error('Delay and display count cannot be negative')
    tables=load_tables(a.data);graph=build_graph(tables)
    event=propagate(graph,tables,a.supplier,a.capacity_loss,a.duration)
    finance=calculate_financial_exposure(event,tables,a.assumed_delay_days)
    result=generate_options(event,graph,tables,a.assumed_delay_days)
    print(f'\nDISRUPTION: {a.supplier} | capacity loss {a.capacity_loss:g}% | {a.duration} days')
    print(f"Snapshot: {event['start_date']} | uncovered exposed orders: {len(event['potential_order_ids'])}")
    print(f"Step 4 conditional cost: USD {finance['breakdown']['total_cost']:,.2f} (assumed delay, not causal loss)")
    print('\nMITIGATION OPTIONS — LOCAL SCREENING ONLY')
    print('Counts:',dict(Counter(c['action_type'] for c in result['candidates'])))
    print(f"Locally screened options: {len(result['candidates'])}")
    print(f"Orders with at least one option: {len({c['order_id'] for c in result['candidates']})}")
    print(f"Orders with a complete-quantity finished-stock option: {len({c['order_id'] for c in result['candidates'] if c['full_order_quantity_covered']})}")
    for c in result['candidates'][:a.show]:
        print(f"\n{c['action_id']} — {c['action_type']} — {c['order_id']} / {c['product_id']}")
        print(f"  Source: {c['source_location']} -> {c['destination_location']} | Route: {c['route_id']}")
        print(f"  Quantity: {c['recoverable_units']} {c['quantity_basis']} | Cost: USD {c['action_cost']:,.2f}")
        print(f"  Cost basis: {c['cost_basis']}")
        print(f"  Arrival: {c['arrival_date']} | Implementation: {c['implementation_time']} days | Conditional time saved: {c['time_saved_days']} days")
        print(f"  Timing basis: {c['timing_basis']}")
        print(f"  Risk proxy: {c['risk_score_proxy']:.3f} | Uncalibrated success proxy: {c['success_probability_proxy']:.1%}")
        print(f"  Feasible locally: {c['feasible']} | Full order quantity covered: {c['full_order_quantity_covered']}")
        print(f"  Scope: {c['feasibility_scope']}")
        print(f"  Shared resource demands: {c['resource_demands']}")
    print('\nREJECTION/LIMIT SUMMARY:')
    for (typ,reason),count in Counter((r['action_type'],r['reason']) for r in result['rejections']).items():
        print(f'  {typ}: {reason} ({count})')
    print('\nNO FINAL PLAN SELECTED. Costs and time savings belong to alternatives, not additive commitments.')
    print('Same stock/capacity may appear in multiple candidates; Step 6 must resolve shared resources.')
    print('Production guarantees and disruption-attributable financial savings are NOT established.')
    print('13_mitigation_actions.csv is loaded, but unrelated scenario actions and their feasible flags are not blindly reused.')


if __name__=='__main__': main()
