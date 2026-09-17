"""SynapseChain Step 3: supplier disruption exposure and current-inventory screening.

Place beside build_supply_chain_graph.py and the dataset's data folder.
Install: python -m pip install pandas networkx
Run: python propagate_disruption.py --data data --supplier S037 --capacity-loss 80 --duration 10

This is NOT money calculation, optimization or a time-stepped simulator.
Potential exposure is not confirmed delay. Component inventory is reported, not
treated as factory stock: the dataset lacks factory/warehouse stock-access links.
Finished-stock screening assumes the unreserved snapshot is available for Pending
orders at their assigned warehouse. Other statuses never consume that stock again.
An absent warehouse/product inventory position is assumed to have zero stock;
this is a modeling assumption, not an inference from missing measurements.
"""
import argparse
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd

from build_supply_chain_graph import load_tables, build_graph, supplier_dependencies


def inventory_screen(graph, tables, exposed_products, start, end):
    """Allocate finished stock ONCE in deadline/priority order, without transfers.

    Process ALL Pending orders due by end, including non-exposed orders, to avoid
    promising the same stock to an exposed order after it has already been consumed.
    Exclude already dispatched orders: they no longer depend on future manufacturing
    at the supplier. No source CSV or graph attribute is changed.
    """
    stock = defaultdict(int)
    dates = set(tables['inventory']['last_updated_date'].astype(str))
    if dates != {start.isoformat()}:
        raise ValueError('Start must equal the single inventory snapshot date. '
                         'Historical replay requires inventory history, which is not available.')
    for row in tables['inventory'].to_dict('records'):
        if row['product_id']:
            stock[(row['warehouse_id'], row['product_id'])] += int(row['available_quantity'])
    # Any non-Planned outbound shipment protects its quantity from upstream capacity
    # loss starting at the snapshot. Partially dispatched orders retain an unstarted remainder.
    dispatched = defaultdict(int)
    for row in tables['shipments'].to_dict('records'):
        if row['order_id'] and row['shipment_status'] != 'Planned' and row['dispatch_date'] <= start.isoformat():
            dispatched[row['order_id']] += int(row['quantity'])
    priority = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    pending = []
    for row in tables['orders'].to_dict('records'):
        if row['order_status'] != 'Pending' or row['order_date'] > start.isoformat() or row['required_date'] > end.isoformat():
            continue
        if row['priority'] not in priority:
            raise ValueError(f"Unknown order priority: {row['priority']}")
        pending.append(row)
    pending.sort(key=lambda row: (row['required_date'], priority[row['priority']], row['order_id']))
    details = []
    for row in pending:
        key = (row['warehouse_id'], row['product_id'])
        qty = max(0, int(row['quantity']) - dispatched[row['order_id']])
        covered = min(qty, stock[key]); stock[key] -= covered
        if row['product_id'] not in exposed_products or qty == 0:
            continue
        remaining = qty - covered
        details.append(dict(order_id=row['order_id'], product_id=row['product_id'],
            factory_id=graph.nodes[row['product_id']]['factory_id'], warehouse_id=row['warehouse_id'],
            required_date=row['required_date'], outstanding_unstarted_units=qty,
            finished_stock_covered_units=covered, uncovered_units=remaining,
            status='Potential upstream risk' if remaining else 'Covered by finished stock',
            already_overdue=row['required_date'] < start.isoformat()))
    return details


def propagate(graph, tables, supplier, capacity_loss=80.0, duration=10, start=None):
    if not 0 <= capacity_loss <= 100:
        raise ValueError('Capacity loss must be a percentage between 0 and 100.')
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        raise ValueError('Duration must be a positive integer number of days.')
    snapshot = tables['inventory']['last_updated_date'].astype(str).unique()
    if len(snapshot) != 1:
        raise ValueError('Inventory must have exactly one snapshot date.')
    start = date.fromisoformat(snapshot[0]) if start is None else start
    # Half-open disruption interval [start, start + duration).
    end = start + timedelta(days=duration - 1)
    dep = supplier_dependencies(graph, supplier)
    inventory = tables['inventory']
    component_rows = []
    for cid in dep['components']:
        component = graph.nodes[cid]
        positions = inventory[inventory['component_id'].eq(cid)]
        daily = int(component['maximum_supply'])
        component_rows.append(dict(component_id=cid, normal_daily_capacity=daily,
            remaining_daily_capacity=round(daily * (1-capacity_loss/100),6),
            unavailable_capacity_over_window=round(daily * capacity_loss/100 * duration,6),
            available_component_stock=int(positions['available_quantity'].sum()),
            stock_above_safety=int(sum(max(0, int(x.available_quantity)-int(x.safety_stock))
                                      for x in positions.itertuples())),
            stocking_warehouses=int(positions['warehouse_id'].nunique())))
    # This screen has no future-replenishment schedule. Its uncovered quantity is
    # a risk flag, not a proven incremental disruption loss.
    orders = inventory_screen(graph, tables, set(dep['products']), start, end)
    potential = [o for o in orders if o['uncovered_units'] > 0] if capacity_loss > 0 else []
    return dict(supplier=supplier, capacity_loss_percent=capacity_loss, duration_days=duration,
        start_date=start.isoformat(), end_date_inclusive=end.isoformat(),
        exposure=dep, component_buffers=component_rows, eligible_orders=orders,
        potential_order_ids=[o['order_id'] for o in potential],
        baseline_uncovered_order_ids=[o['order_id'] for o in orders if o['uncovered_units'] > 0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data', help='CSV directory, dataset root, or corrected dataset ZIP')
    parser.add_argument('--supplier', default='S037')
    parser.add_argument('--capacity-loss', type=float, default=80.0)
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--start', help='ISO date; must equal the inventory snapshot date')
    args = parser.parse_args()
    tables = load_tables(args.data)
    graph = build_graph(tables)
    result = propagate(graph, tables, args.supplier, args.capacity_loss, args.duration,
                       date.fromisoformat(args.start) if args.start else None)
    print('\nDISRUPTION')
    print(f"Supplier: {result['supplier']}\nCapacity Loss: {result['capacity_loss_percent']:g}%\nDuration: {result['duration_days']} days")
    print(f"Window: {result['start_date']} to {result['end_date_inclusive']} (inclusive)")
    print('\nIMPACT PROPAGATION — graph exposure, not confirmed disruption effects')
    for field in ['components', 'products', 'factories', 'warehouses']:
        print(f"Exposed {field.title()}: {len(result['exposure'][field]):,}")
    print('Component IDs:', ', '.join(result['exposure']['components']))
    print(f"All linked orders (including history): {len(result['exposure']['orders']):,}")
    print('\nCOMPONENT CAPACITY AND INVENTORY')
    if result['component_buffers']:
        print(pd.DataFrame(result['component_buffers']).to_string(index=False))
    else: print('No supplied components found.')
    candidates = result['eligible_orders']
    print('\nCURRENT-STOCK SCREEN — only unstarted orders due by the window end')
    print(f'Eligible exposed orders: {len(candidates):,}')
    print(f"Covered completely by finished stock: {sum(o['uncovered_units']==0 for o in candidates):,}")
    print(f"Potentially affected orders: {len(result['potential_order_ids']):,}")
    print(f"Uncovered even without proving this disruption's effect: {len(result['baseline_uncovered_order_ids']):,}")
    print(f"Already overdue eligible orders: {sum(o['already_overdue'] for o in candidates):,}")
    if candidates: print('\nFirst 10 screened orders:\n'+pd.DataFrame(candidates[:10]).to_string(index=False))
    print('\nLIMITS: reduced capacity is not a count of lost production; capacity is not scheduled demand.')
    print('Component warehouse buffers are not credited as factory-accessible stock.')
    print('An absent warehouse/product inventory position is assumed to mean zero finished stock.')
    print('Potentially affected means exposed and not covered by current finished stock, not confirmed late.')
    print('Existing incoming finished-product shipments, manufacturing timing and future demand are not simulated.')
    print('No money, mitigation, optimization, ML, agents or dashboard has been calculated.')


if __name__ == '__main__':
    main()
