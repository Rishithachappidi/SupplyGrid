"""SynapseChain Step 2: load all 14 CSVs, construct a typed supply-chain graph.

Install: python -m pip install pandas networkx
Run from your extracted dataset folder:
    python build_supply_chain_graph.py --data data --supplier S037
Or use the corrected dataset ZIP without extracting it:
    python build_supply_chain_graph.py --data SynapseChain_Master_Dataset_Corrected.zip

This is a reloadable snapshot graph, NOT disruption simulation or live event handling.
Research tables are loaded but not treated as operational dependencies. No prediction,
optimization, agents, dashboard, or financial-impact calculation is performed.
"""
import argparse
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

import networkx as nx
import pandas as pd

FILES = {
    'suppliers': '01_suppliers.csv', 'components': '02_components.csv',
    'bom': '03_product_components.csv', 'factories': '04_factories.csv',
    'products': '05_products.csv', 'warehouses': '06_warehouses.csv',
    'inventory': '07_inventory.csv', 'orders': '08_orders.csv',
    'shipments': '09_shipments.csv', 'routes': '10_routes.csv',
    'disruptions': '11_disruptions.csv', 'financial_impacts': '12_financial_impacts.csv',
    'mitigation_actions': '13_mitigation_actions.csv', 'scenarios': '14_scenarios.csv',
}


def load_tables(source):
    """Keep intentional blanks as empty strings. Reject absent/ambiguous files."""
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f'Dataset path not found: {source.resolve()}')
    tables = {}
    if source.is_file():
        with ZipFile(source) as archive:
            for table, filename in FILES.items():
                candidates = [n for n in archive.namelist()
                              if Path(n).name == filename and not n.endswith('/')]
                if len(candidates) != 1:
                    raise ValueError(f'Expected exactly one {filename} in ZIP; found {len(candidates)}')
                with archive.open(candidates[0]) as f:
                    tables[table] = pd.read_csv(f, keep_default_na=False)
    else:
        directory = source / 'data' if (source / 'data').is_dir() else source
        for table, filename in FILES.items():
            path = directory / filename
            if not path.is_file():
                raise FileNotFoundError(f'Missing required CSV: {path}')
            tables[table] = pd.read_csv(path, keep_default_na=False)
    return tables


def build_graph(tables):
    """MultiDiGraph retains separate inventory, route and shipment relationships."""
    graph = nx.MultiDiGraph()
    graph.graph.update(
        description='Typed supply-chain snapshot; potential dependency exposure only',
        loaded_row_counts={name: len(df) for name, df in tables.items()},
        research_tables_not_used_for_propagation=['disruptions', 'financial_impacts',
                                                'mitigation_actions', 'scenarios'],
    )
    for table, kind, id_column in [
        ('suppliers', 'Supplier', 'supplier_id'), ('components', 'Component', 'component_id'),
        ('products', 'Product', 'product_id'), ('factories', 'Factory', 'factory_id'),
        ('warehouses', 'Warehouse', 'warehouse_id'), ('orders', 'Order', 'order_id'),
        ('shipments', 'Shipment', 'shipment_id'), ('routes', 'Route', 'route_id'),
    ]:
        frame = tables[table]
        if id_column not in frame or frame[id_column].eq('').any() or frame[id_column].duplicated().any():
            raise ValueError(f'{table}: missing or duplicate {id_column}')
        for row in frame.to_dict('records'):
            node = row[id_column]
            if node in graph:
                raise ValueError(f'ID collision between entity tables: {node}')
            graph.add_node(node, entity_type=kind, **row)

    def link(origin, destination, relation, key, source_type=None, dest_type=None, **attrs):
        # NetworkX otherwise creates undeclared nodes silently: prohibit this.
        for node, expected in [(origin, source_type), (destination, dest_type)]:
            if node not in graph:
                raise ValueError(f'{relation}: unknown referenced ID {node!r}')
            if expected and graph.nodes[node]['entity_type'] != expected:
                raise ValueError(f'{relation}: {node} is not a {expected}')
        graph.add_edge(origin, destination, key=f'{relation}:{key}', relation=relation, **attrs)

    for row in tables['components'].to_dict('records'):
        link(row['supplier_id'], row['component_id'], 'SUPPLIES', row['component_id'], 'Supplier', 'Component')
    if tables['bom'].duplicated(['product_id', 'component_id']).any():
        raise ValueError('Duplicate product/component BOM pair')
    for row in tables['bom'].to_dict('records'):
        if int(row['quantity_required']) <= 0:
            raise ValueError('BOM quantity_required must be positive')
        key = f"{row['product_id']}:{row['component_id']}"
        link(row['component_id'], row['product_id'], 'REQUIRED_BY', key, 'Component', 'Product', **row)
        if row['substitute_component_id']:
            # Substitution is optional, not an automatic dependency.
            link(row['substitute_component_id'], row['component_id'], 'SUBSTITUTE_FOR', key,
                 'Component', 'Component', for_product_id=row['product_id'])
    for row in tables['products'].to_dict('records'):
        link(row['product_id'], row['factory_id'], 'MADE_AT', row['product_id'], 'Product', 'Factory')
    for row in tables['inventory'].to_dict('records'):
        if bool(row['component_id']) == bool(row['product_id']):
            raise ValueError(f"{row['inventory_id']}: inventory requires exactly one item ID")
        if int(row['available_quantity']) != int(row['quantity_on_hand']) - int(row['reserved_quantity']):
            raise ValueError(f"{row['inventory_id']}: inconsistent inventory balance")
        item = row['component_id'] or row['product_id']
        kind = 'Component' if row['component_id'] else 'Product'
        link(item, row['warehouse_id'], 'STOCKED_AT', row['inventory_id'], kind, 'Warehouse', **row)
    for row in tables['orders'].to_dict('records'):
        oid = row['order_id']
        link(row['product_id'], oid, 'ORDERED_IN', oid, 'Product', 'Order', quantity=row['quantity'])
        link(row['warehouse_id'], oid, 'ALLOCATED_TO', oid, 'Warehouse', 'Order')
    for row in tables['routes'].to_dict('records'):
        link(row['origin_id'], row['route_id'], 'ROUTE_FROM', row['route_id'], dest_type='Route')
        link(row['route_id'], row['destination_id'], 'ROUTE_TO', row['route_id'], source_type='Route')
    for row in tables['shipments'].to_dict('records'):
        shid = row['shipment_id']
        if bool(row['component_id']) == bool(row['product_id']):
            raise ValueError(f'{shid}: shipment requires exactly one item ID')
        if row['route_id'] not in graph or graph.nodes[row['route_id']]['entity_type'] != 'Route':
            raise ValueError(f'{shid}: invalid route_id')
        route = graph.nodes[row['route_id']]
        if any(row[c] != route[c] for c in ['origin_id', 'destination_id', 'transport_mode']):
            raise ValueError(f'{shid}: route endpoint/mode mismatch')
        link(row['origin_id'], shid, 'DISPATCHES', shid, dest_type='Shipment')
        link(shid, row['destination_id'], 'ARRIVES_AT', shid, source_type='Shipment')
        link(row['component_id'] or row['product_id'], shid, 'CARRIED_IN', shid,
             'Component' if row['component_id'] else 'Product', 'Shipment')
        link(row['route_id'], shid, 'USED_BY_SHIPMENT', shid, 'Route', 'Shipment')
        if row['order_id']:
            if row['order_id'] not in graph:
                raise ValueError(f'{shid}: unknown order_id')
            order = graph.nodes[row['order_id']]
            if row['product_id'] != order['product_id'] or row['destination_id'] != order['warehouse_id']:
                raise ValueError(f'{shid}: product/warehouse disagrees with order')
            link(shid, row['order_id'], 'ALLOCATED_SHIPMENT', shid, 'Shipment', 'Order')
    return graph


def targets(graph, nodes, relation):
    return {v for u in nodes for _, v, attrs in graph.out_edges(u, data=True)
            if attrs['relation'] == relation}


def supplier_dependencies(graph, supplier_id):
    """Product-specific query; never blindly traverse shared factory/warehouse hubs.

    Orders are potentially exposed, not confirmed delayed. Alternate suppliers,
    stock buffers, time and factory scheduling are NOT resolved in Step 2.
    """
    if supplier_id not in graph or graph.nodes[supplier_id]['entity_type'] != 'Supplier':
        raise ValueError(f'Unknown supplier: {supplier_id}')
    components = targets(graph, {supplier_id}, 'SUPPLIES')
    products = targets(graph, components, 'REQUIRED_BY')
    factories = targets(graph, products, 'MADE_AT')
    orders = targets(graph, products, 'ORDERED_IN')
    order_warehouses = {graph.nodes[o]['warehouse_id'] for o in orders}
    stocking_warehouses = targets(graph, components | products, 'STOCKED_AT')
    return {
        'components': sorted(components), 'products': sorted(products), 'factories': sorted(factories),
        'order_warehouses': sorted(order_warehouses),
        'stocking_warehouses': sorted(stocking_warehouses),
        'warehouses': sorted(order_warehouses | stocking_warehouses), 'orders': sorted(orders),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='data', help='CSV folder, extracted dataset root, or dataset ZIP')
    parser.add_argument('--supplier', default='S037')
    args = parser.parse_args()
    tables = load_tables(args.data)
    print('Actual loaded CSV row counts:')
    for name, df in tables.items(): print(f'  {FILES[name]}: {len(df):,}')
    graph = build_graph(tables)
    print(f'\nGraph: {graph.number_of_nodes():,} nodes, {graph.number_of_edges():,} directed edges')
    print('Node types:', dict(Counter(x['entity_type'] for _, x in graph.nodes(data=True))))
    result = supplier_dependencies(graph, args.supplier)
    print(f'\nPotential dependencies for {args.supplier}:')
    for category, ids in result.items():
        print(f'  {category}: {len(ids):,} | first 10: {", ".join(ids[:10]) or "none"}')
    print('\nPotential exposure only. No disruption impact, financial calculation or mitigation is inferred.')
    print('Factory and warehouse sharing alone does not make unrelated orders dependent.')


if __name__ == '__main__':
    main()
