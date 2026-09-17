"""SynapseChain Step 4: conditional financial exposure, not causal loss attribution.

Place beside build_supply_chain_graph.py and propagate_disruption.py.
Install: python -m pip install pandas networkx
Run:
 python financial_blast_radius.py --data data --supplier S037 --capacity-loss 80 --duration 10 --assumed-delay-days 10

Dataset currency is USD. The REQUIRED delay assumption is not inferred from the
duration of supplier capacity loss. Cancellation rate defaults to zero and penalty
rate defaults to an illustrative 0.001 of delayed order value per day (not a real
contract). Both can be changed. No mitigation is selected, quoted or executed.

Formulas per uncovered order:
 cancelled units = floor(uncovered units * assumed cancellation rate)
 delayed units = uncovered units - cancelled units
 lost contribution = cancelled units * (order unit price - product production cost)
 lost revenue = cancelled units * order unit price [INFORMATIONAL, not summed again]
 deferred revenue = delayed units * order unit price [not an economic loss]
 penalty = delayed units * unit price * daily penalty rate * assumed delay days
 total scenario cost = lost contribution + penalty

Production_loss_cost is a legacy label for lost contribution, not shutdown cost.
Canceled orders assume unstarted production and avoided production cost. No sunk
cost, cancellation fee, penalty cap, tax or discounting is modeled. Lost contribution
can be negative for a loss-making sale: do not silently clamp it to zero.

The Step 3 uncovered orders are also uncovered in its stock-only baseline. Thus
this engine DOES NOT prove that its scenario cost is caused by supplier disruption.
Counterfactual incremental loss is not estimable until baseline and disrupted
delivery outcomes exist. Do not subtract identical stock-only screens as if they
were complete delivery outcomes.
"""
import argparse
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR

from build_supply_chain_graph import load_tables, build_graph
from propagate_disruption import propagate

ZERO = Decimal('0.00')
CENT = Decimal('0.01')


def decimal(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Financial inputs must be finite numbers.')
    return result


def cents(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_financial_exposure(propagation, tables, assumed_delay_days,
                                 cancellation_rate='0', daily_penalty_rate='0.001'):
    """Pure calculation: does not change graph, source CSVs or propagation results.

    Returns Decimal currency values and per-order calculations so every total
    can be traced. It counts each uncovered order exactly once, irrespective
    of how many disrupted components that product requires.
    """
    if isinstance(assumed_delay_days, bool) or not isinstance(assumed_delay_days, int) or assumed_delay_days < 0:
        raise ValueError('Assumed delay must be a nonnegative integer number of days.')
    cancel = decimal(cancellation_rate); rate = decimal(daily_penalty_rate)
    if not ZERO <= cancel <= 1:
        raise ValueError('Cancellation rate must be between 0 and 1.')
    if not ZERO <= rate <= 1:
        raise ValueError('Daily penalty rate must be between 0 and 1.')
    products = tables['products'].set_index('product_id').to_dict('index')
    orders = tables['orders'].set_index('order_id').to_dict('index')
    if tables['products']['product_id'].duplicated().any() or tables['orders']['order_id'].duplicated().any():
        raise ValueError('Duplicate product or order IDs.')
    eligible = {}
    for row in propagation['eligible_orders']:
        oid = row['order_id']
        if oid in eligible:
            raise ValueError(f'Duplicate screened order: {oid}')
        eligible[oid] = row
    selected = propagation['potential_order_ids']
    if len(selected) != len(set(selected)):
        raise ValueError('Duplicate potentially affected order IDs.')
    detail = []
    for oid in selected:
        if oid not in eligible or oid not in orders:
            raise ValueError(f'Unknown or unscreened order: {oid}')
        row = eligible[oid]; order = orders[oid]
        if row['product_id'] != order['product_id'] or row['warehouse_id'] != order['warehouse_id']:
            raise ValueError(f'{oid}: screened product/warehouse disagrees with source order.')
        raw_qty = decimal(row['uncovered_units'])
        if raw_qty != raw_qty.to_integral_value() or raw_qty <= 0:
            raise ValueError(f'{oid}: uncovered units must be positive integers.')
        qty = int(raw_qty)
        if qty > int(order['quantity']):
            raise ValueError(f'{oid}: uncovered quantity exceeds ordered quantity.')
        price = decimal(order['unit_price'])
        cost = decimal(products[order['product_id']]['production_cost'])
        if price < 0 or cost < 0:
            raise ValueError('Prices and production costs cannot be negative.')
        cancelled = int((raw_qty * cancel).to_integral_value(rounding=ROUND_FLOOR))
        delayed = qty - cancelled
        contribution = cents(cancelled * (price - cost))
        lost_revenue = cents(cancelled * price)
        deferred = cents(delayed * price)
        penalty = cents(delayed * price * rate * assumed_delay_days)
        detail.append(dict(order_id=oid, product_id=order['product_id'],
            warehouse_id=order['warehouse_id'], uncovered_units=qty, cancelled_units=cancelled,
            delayed_units=delayed, unit_price_usd=price, production_cost_per_unit_usd=cost,
            lost_contribution_usd=contribution, lost_revenue_usd=lost_revenue,
            deferred_revenue_usd=deferred, penalty_usd=penalty,
            total_scenario_cost_usd=cents(contribution+penalty)))
    def total(field):
        return cents(sum((row[field] for row in detail), ZERO))
    contribution = total('lost_contribution_usd'); penalty = total('penalty_usd')
    # Recovery costs are not modeled yet. Numeric zero is a scope convention,
    # never an assertion that an actual recovery plan would be free.
    breakdown = dict(production_loss_cost=contribution, lost_revenue=total('lost_revenue_usd'),
        expedite_cost=ZERO, alternative_supplier_cost=ZERO, additional_transport_cost=ZERO,
        inventory_holding_cost=ZERO, stockout_cost=ZERO, penalty_cost=penalty,
        recovery_cost=ZERO, total_cost=cents(contribution+penalty),
        revenue_at_risk=total('lost_revenue_usd')+total('deferred_revenue_usd'),
        recoverable_value=ZERO, net_financial_impact=cents(contribution+penalty))
    if breakdown['total_cost'] != total('total_scenario_cost_usd'):
        raise ArithmeticError('Order-level totals do not reconcile with the summary.')
    return dict(currency='USD', scope='Conditional scenario exposure, NOT identified disruption-caused loss',
        assumed_delay_days=assumed_delay_days, assumed_cancellation_rate=cancel,
        assumed_daily_penalty_rate=rate, evaluated_orders=len(detail),
        cancelled_units=sum(row['cancelled_units'] for row in detail),
        delayed_units=sum(row['delayed_units'] for row in detail),
        deferred_revenue=total('deferred_revenue_usd'), breakdown=breakdown,
        incremental_disruption_loss=None, detail=detail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data', help='CSV directory, dataset root, or corrected dataset ZIP')
    parser.add_argument('--supplier', default='S037')
    parser.add_argument('--capacity-loss', type=float, default=80)
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--assumed-delay-days', required=True, type=int,
                        help='Scenario assumption, NOT automatically equal to disruption duration')
    parser.add_argument('--cancellation-rate', default='0', help='Assumed fraction of uncovered units cancelled, 0 to 1')
    parser.add_argument('--daily-penalty-rate', default='0.001', help='Illustrative contractual daily rate, 0 to 1')
    args = parser.parse_args()
    if args.assumed_delay_days < 0 or not 0 <= decimal(args.cancellation_rate) <= 1 or not 0 <= decimal(args.daily_penalty_rate) <= 1:
        parser.error('Invalid delay, cancellation rate or penalty rate.')
    tables = load_tables(args.data)
    graph = build_graph(tables)
    propagation = propagate(graph, tables, args.supplier, args.capacity_loss, args.duration)
    result = calculate_financial_exposure(propagation, tables, args.assumed_delay_days,
                                         args.cancellation_rate, args.daily_penalty_rate)
    print(f"\nDISRUPTION: {args.supplier}\nCapacity loss: {args.capacity_loss:g}%\nDuration: {args.duration} days")
    print(f"Inventory snapshot: {propagation['start_date']}")
    print(f"Evaluated uncovered orders: {result['evaluated_orders']:,}")
    print(f"ASSUMPTIONS: {args.assumed_delay_days} delay days; {result['assumed_cancellation_rate']:.2%} cancellation rate; "
          f"{result['assumed_daily_penalty_rate']:.3%} daily penalty rate")
    print('Cancellation rounding: down to integer units separately for each order.')
    print('\nFINANCIAL BLAST RADIUS — CONDITIONAL SCENARIO (USD)')
    labels = [('production_loss_cost','Lost contribution (production-loss field)'),
              ('lost_revenue','Lost revenue [informational; not added]'),
              ('expedite_cost','Expedite cost [not modeled]'),
              ('alternative_supplier_cost','Alternative supplier cost [not modeled]'),
              ('additional_transport_cost','Extra transport cost [not modeled]'),
              ('inventory_holding_cost','Extra holding cost [not modeled]'),
              ('stockout_cost','Stockout cost [not modeled]'),
              ('penalty_cost','Assumed late-delivery penalty'),
              ('recovery_cost','Recovery cost [not modeled]')]
    for field, label in labels:
        print(f"{label:48} USD {result['breakdown'][field]:>14,.2f}")
    print(f"TOTAL CONDITIONAL SCENARIO COST: USD {result['breakdown']['total_cost']:,.2f}")
    print(f"Revenue at risk [not added to cost]: USD {result['breakdown']['revenue_at_risk']:,.2f}")
    print(f"Deferred revenue [not lost revenue]: USD {result['deferred_revenue']:,.2f}")
    print(f"Assumed cancelled units: {result['cancelled_units']}; assumed delayed units: {result['delayed_units']}")
    print('\nFirst 5 order calculations:')
    for row in result['detail'][:5]:
        print(f"{row['order_id']} | uncovered={row['uncovered_units']} | cancelled={row['cancelled_units']} | "
              f"delayed={row['delayed_units']} | contribution={row['lost_contribution_usd']:.2f} | "
              f"penalty={row['penalty_usd']:.2f} | total={row['total_scenario_cost_usd']:.2f} USD")
    print('\nIncremental loss attributable to S037 disruption: NOT ESTIMABLE from the current stock-only screen.')
    print('These orders are also uncovered in that baseline; delays and cancellations above are assumptions.')
    print('Zero recovery fields mean not modeled, not a free recovery. No mitigation has been selected.')
    print('12_financial_impacts.csv is loaded but its unrelated scenario totals are NOT copied or added.')


if __name__ == '__main__':
    main()
