"""Generate ONLY three v2 CSVs and validate files actually read from disk.

No original CSV is edited. Run:
 python extend_dataset_v2.py --data data --output data_v2
 python extend_dataset_v2.py --data data --output data_v2 --validate-only
"""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from build_supply_chain_graph import FILES, load_tables
from financial_blast_radius import decimal, cents
from optimize_mitigation import integer

SCHEMAS = {
    'factory_inventory': ('15_factory_component_inventory.csv', [
        'inventory_id', 'factory_id', 'component_id', 'quantity_on_hand', 'reserved_quantity',
        'safety_stock', 'available_quantity', 'usable_quantity', 'snapshot_date', 'unit_cost_usd']),
    'factory_calendar': ('16_factory_capacity_calendar.csv', [
        'factory_id', 'date', 'nominal_capacity_units', 'committed_capacity_units',
        'available_capacity_units', 'operating_cost_per_unit_usd', 'labor_cost_per_unit_usd',
        'conversion_cost_per_unit_usd']),
    'supplier_calendar': ('17_supplier_capacity_calendar.csv', [
        'supplier_id', 'component_id', 'date', 'supplier_capacity_units',
        'supplier_committed_units', 'supplier_available_units', 'component_capacity_units',
        'component_committed_units', 'component_available_units', 'unit_cost_usd',
        'lead_time_days', 'minimum_order_qty']),
}


def original_hashes(source):
    source = Path(source)
    hashes = {}
    if source.is_file():
        with ZipFile(source) as z:
            for filename in FILES.values():
                names = [n for n in z.namelist() if Path(n).name == filename]
                if len(names) != 1:
                    raise ValueError('Missing/ambiguous source CSV.')
                hashes[filename] = hashlib.sha256(z.read(names[0])).hexdigest()
    else:
        root = source / 'data' if (source / 'data').is_dir() else source
        for filename in FILES.values():
            hashes[filename] = hashlib.sha256((root / filename).read_bytes()).hexdigest()
    return hashes


def factory_component_pairs(tables):
    """Explicit physical inventory positions: original and BOM-approved substitutes."""
    products = tables['products'].set_index('product_id').to_dict('index')
    pairs = defaultdict(int)
    for b in tables['bom'].to_dict('records'):
        fid = products[b['product_id']]['factory_id']
        q = integer(b['quantity_required'], 'BOM quantity')
        for cid in (b['component_id'], b['substitute_component_id']):
            if cid:
                pairs[fid, cid] = max(pairs[fid, cid], q)
    return pairs


def generate_extension(tables, output, days=31, seed=20260918):
    if days < 1:
        raise ValueError('Calendar horizon must be positive.')
    snapshot = set(tables['inventory']['last_updated_date'].astype(str))
    if len(snapshot) != 1:
        raise ValueError('Expected one base inventory snapshot.')
    start = date.fromisoformat(next(iter(snapshot)))
    components = tables['components'].set_index('component_id').to_dict('index')
    suppliers = tables['suppliers'].set_index('supplier_id').to_dict('index')
    def rng(key):
        return random.Random(int.from_bytes(hashlib.sha256(f'{seed}:{key}'.encode()).digest()[:8], 'big'))
    records = {k: [] for k in SCHEMAS}
    for i, ((fid, cid), ratio) in enumerate(sorted(factory_component_pairs(tables).items()), 1):
        r = rng(f'stock:{fid}:{cid}')
        on_hand = 0 if r.random() < 0.03 else ratio * r.randint(12, 40)
        reserved = min(on_hand, ratio * r.randint(0, 2))
        safety = min(on_hand - reserved, ratio * 2)
        records['factory_inventory'].append(dict(inventory_id=f'FI{i:06d}', factory_id=fid,
            component_id=cid, quantity_on_hand=on_hand, reserved_quantity=reserved,
            safety_stock=safety, available_quantity=on_hand-reserved,
            usable_quantity=max(0, on_hand-reserved-safety), snapshot_date=start.isoformat(),
            unit_cost_usd=str(cents(decimal(components[cid]['unit_cost'])))))
    for f in sorted(tables['factories'].to_dict('records'), key=lambda x:x['factory_id']):
        fid = f['factory_id']; nominal = integer(f['production_capacity'], 'Factory nominal capacity')
        for d in range(days):
            day = (start + timedelta(days=d)).isoformat()
            # A constant utilization-derived commitment, NOT an inferred real schedule.
            committed = int(decimal(nominal) * decimal(f['current_utilization']))
            records['factory_calendar'].append(dict(factory_id=fid, date=day,
                nominal_capacity_units=nominal, committed_capacity_units=committed,
                available_capacity_units=nominal-committed,
                operating_cost_per_unit_usd=str(cents(decimal(f['operating_cost_per_unit']))),
                labor_cost_per_unit_usd=str(cents(decimal(f['labor_cost_per_unit']))),
                conversion_cost_per_unit_usd=str(cents(decimal(f['operating_cost_per_unit'])+decimal(f['labor_cost_per_unit'])))))
    by_supplier = defaultdict(list)
    for cid, c in components.items():
        by_supplier[c['supplier_id']].append((cid,c))
    for sid, comps in sorted(by_supplier.items()):
        nominal_supplier = integer(suppliers[sid]['component_capacity'], 'Supplier capacity')
        for d in range(days):
            day = (start + timedelta(days=d)).isoformat()
            rows = []
            for cid, c in sorted(comps):
                nominal = integer(c['maximum_supply'], 'Component capacity')
                percent = rng(f'commit:{sid}:{cid}:{day}').randint(20,60)
                committed = nominal * percent // 100
                rows.append(dict(supplier_id=sid, component_id=cid, date=day,
                    component_capacity_units=nominal, component_committed_units=committed,
                    component_available_units=nominal-committed,
                    unit_cost_usd=str(cents(decimal(c['unit_cost']))), lead_time_days=c['lead_time_days'],
                    minimum_order_qty=c['minimum_order_qty']))
            committed_supplier = sum(x['component_committed_units'] for x in rows)
            if committed_supplier > nominal_supplier:
                raise ValueError('Generated component commitments exceed supplier total.')
            for row in rows:
                row.update(supplier_capacity_units=nominal_supplier,
                    supplier_committed_units=committed_supplier,
                    supplier_available_units=nominal_supplier-committed_supplier)
                records['supplier_calendar'].append(row)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    # Only derived data are written. Refuse overwriting any existing extension.
    if any((output / name).exists() for name,_ in SCHEMAS.values()):
        raise FileExistsError('Extension CSVs already exist; use --validate-only or a new output directory.')
    for key, (filename, columns) in SCHEMAS.items():
        pd.DataFrame(records[key], columns=columns).to_csv(output / filename, index=False)


def load_extension(directory):
    directory = Path(directory)
    return {k: pd.read_csv(directory / filename, keep_default_na=False, dtype=str)
            for k, (filename, _) in SCHEMAS.items()}


def validate_extension(tables, ext):
    """Fail closed on unknown keys, invalid numbers, balances, dates and semantics."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    for key, (_, columns) in SCHEMAS.items():
        df = ext[key]
        require(list(df.columns) == columns, f'{key}: schema mismatch')
        require(not df.empty and not df.isna().any().any() and not df.eq('').any().any(), f'{key}: empty/NULL cells')
    S = tables['suppliers'].set_index('supplier_id').to_dict('index')
    C = tables['components'].set_index('component_id').to_dict('index')
    F = tables['factories'].set_index('factory_id').to_dict('index')
    P = tables['products'].set_index('product_id').to_dict('index')
    W = set(tables['warehouses']['warehouse_id'])
    for key,col in [('suppliers','supplier_id'),('components','component_id'),('factories','factory_id'),('products','product_id')]:
        require(not tables[key][col].duplicated().any(), f'{key}: duplicate IDs')
    require(not tables['bom'].duplicated(['product_id','component_id']).any(), 'Duplicate BOM requirement')
    for c in C.values():
        require(c['supplier_id'] in S, 'Invalid component supplier')
        require(integer(c['minimum_order_qty'],'MOQ') > 0, 'Zero MOQ')
        require(integer(c['lead_time_days'],'Lead time') >= 0, 'Negative lead time')
    for p in P.values():
        require(p['factory_id'] in F, 'Invalid product factory')
        require(decimal(p['production_time_hours']) > 0, 'Nonpositive production duration')
    for b in tables['bom'].to_dict('records'):
        require(b['product_id'] in P and b['component_id'] in C, 'Invalid BOM reference')
        require(integer(b['quantity_required'],'BOM quantity') > 0, 'Zero BOM quantity')
        alt = b['substitute_component_id']
        if alt:
            require(alt in C and alt != b['component_id'], 'Invalid substitute ID')
            require(C[alt]['category'] == C[b['component_id']]['category'], 'Substitute category mismatch')
    entities = set(S)|set(F)|W
    require(not tables['routes']['route_id'].duplicated().any(), 'Duplicate route IDs')
    route_types = defaultdict(int)
    for r in tables['routes'].to_dict('records'):
        origin, dest = r['origin_id'], r['destination_id']
        require(origin in entities and dest in entities and origin != dest, 'Invalid route endpoint')
        require((origin in S and dest in F) or (origin in F and dest in W) or (origin in W and dest in W), 'Unsupported route type')
        integer(r['normal_transit_days'], 'Route transit days'); integer(r['route_capacity'], 'Route capacity')
        require(decimal(r['cost_per_unit']) >= 0 and decimal(r['estimated_transit_cost']) >= 0, 'Negative route quote')
        route_types['supplier_to_factory' if origin in S else 'factory_to_warehouse' if origin in F else 'warehouse_to_warehouse'] += 1
    snapshots = set(tables['inventory']['last_updated_date'].astype(str))
    require(len(snapshots) == 1, 'Base inventory snapshot mismatch')
    snapshot = date.fromisoformat(next(iter(snapshots)))
    inv = ext['factory_inventory']
    require(not inv['inventory_id'].duplicated().any(), 'Duplicate factory inventory ID')
    require(not inv.duplicated(['factory_id','component_id']).any(), 'Duplicate factory component position')
    require(set(zip(inv['factory_id'],inv['component_id'])) == set(factory_component_pairs(tables)), 'Factory inventory must cover exactly original/approved-substitute BOM positions')
    stored = defaultdict(int)
    for r in inv.to_dict('records'):
        require(r['factory_id'] in F and r['component_id'] in C, 'Unknown inventory factory/component')
        require(date.fromisoformat(r['snapshot_date']) == snapshot, 'Factory snapshot mismatch')
        q, reserved, safety, available, usable = [integer(r[k],k) for k in ('quantity_on_hand','reserved_quantity','safety_stock','available_quantity','usable_quantity')]
        require(reserved <= q and safety <= q-reserved and available == q-reserved and usable == available-safety, 'Factory inventory balance mismatch')
        require(decimal(r['unit_cost_usd']) == cents(decimal(C[r['component_id']]['unit_cost'])), 'Inventory valuation price mismatch')
        stored[r['factory_id']] += q
    for fid,q in stored.items():
        require(q <= integer(F[fid]['storage_capacity'],'Storage capacity'), 'Factory synthetic storage limit exceeded')
    fc = ext['factory_calendar']; sc = ext['supplier_calendar']
    require(not fc.duplicated(['factory_id','date']).any(), 'Duplicate factory calendar key')
    require(not sc.duplicated(['supplier_id','component_id','date']).any(), 'Duplicate supplier calendar key')
    dates_f = {date.fromisoformat(x) for x in fc['date']}
    dates_s = {date.fromisoformat(x) for x in sc['date']}
    require(dates_f == dates_s and min(dates_f) == snapshot, 'Calendar horizons differ or do not start at snapshot')
    require(dates_f == {snapshot + timedelta(days=i) for i in range(len(dates_f))}, 'Calendar dates are not contiguous')
    expected_dates = {x.isoformat() for x in dates_f}
    require(set(zip(fc['factory_id'],fc['date'])) == {(fid,d) for fid in F for d in expected_dates}, 'Incomplete factory calendar')
    require(set(zip(sc['component_id'],sc['date'])) == {(cid,d) for cid in C for d in expected_dates}, 'Incomplete supplier-component calendar')
    for r in fc.to_dict('records'):
        require(r['factory_id'] in F, 'Unknown factory calendar ID')
        n,c,a = [integer(r[k],k) for k in ('nominal_capacity_units','committed_capacity_units','available_capacity_units')]
        require(n == integer(F[r['factory_id']]['production_capacity'],'Nominal capacity') and c <= n and a == n-c, 'Factory calendar capacity mismatch')
        operating, labor, conversion = [decimal(r[k]) for k in ('operating_cost_per_unit_usd','labor_cost_per_unit_usd','conversion_cost_per_unit_usd')]
        require(min(operating,labor,conversion) >= 0 and conversion == cents(operating+labor), 'Conversion cost decomposition mismatch')
    group = defaultdict(list)
    for r in sc.to_dict('records'):
        sid,cid = r['supplier_id'],r['component_id']
        require(sid in S and cid in C and C[cid]['supplier_id'] == sid, 'Supplier/component ownership mismatch')
        n,c,a = [integer(r[k],k) for k in ('component_capacity_units','component_committed_units','component_available_units')]
        require(n == integer(C[cid]['maximum_supply'],'Component capacity') and c <= n and a == n-c, 'Component calendar capacity mismatch')
        sn,st,sa = [integer(r[k],k) for k in ('supplier_capacity_units','supplier_committed_units','supplier_available_units')]
        require(sn == integer(S[sid]['component_capacity'],'Supplier capacity') and st <= sn and sa == sn-st, 'Supplier capacity mismatch')
        require(decimal(r['unit_cost_usd']) >= 0 and decimal(r['unit_cost_usd']) == cents(decimal(C[cid]['unit_cost'])), 'Procurement price mismatch')
        require(integer(r['lead_time_days'],'Lead time') == integer(C[cid]['lead_time_days'],'Component lead time'), 'Lead time mismatch')
        require(integer(r['minimum_order_qty'],'MOQ') == integer(C[cid]['minimum_order_qty'],'Component MOQ'), 'MOQ mismatch')
        group[sid,r['date']].append(r)
    for key, rows in group.items():
        for col in ('supplier_capacity_units','supplier_committed_units','supplier_available_units'):
            require(len({r[col] for r in rows}) == 1, 'Repeated supplier total inconsistent')
        require(sum(integer(r['component_committed_units'],'Commitment') for r in rows) == integer(rows[0]['supplier_committed_units'],'Supplier commitment'), 'Supplier commitments do not reconcile')
        require(sum(integer(r['component_capacity_units'],'Component capacity') for r in rows) <= integer(rows[0]['supplier_capacity_units'],'Supplier total'), 'Component nominal totals exceed supplier total')
    return dict(status='PASSED', actual_row_counts={SCHEMAS[k][0]:len(v) for k,v in ext.items()},
        actual_column_counts={SCHEMAS[k][0]:len(v.columns) for k,v in ext.items()},
        snapshot_date=snapshot.isoformat(), calendar_days=len(dates_f), calendar_end=max(dates_f).isoformat(),
        validated_route_types=dict(route_types), checks=['schemas/no NULLs', 'unique primary keys',
        'supplier/factory/component foreign keys', 'BOM/substitute approval', 'route endpoints/types/costs',
        'inventory balances/storage limits', 'integer quantities', 'snapshot/contiguous calendar coverage',
        'shared supplier totals/commitments', 'factory capacity balances', 'cost decomposition'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', default='data'); ap.add_argument('--output', default='data_v2')
    ap.add_argument('--days', type=int, default=31); ap.add_argument('--seed', type=int, default=20260918)
    ap.add_argument('--validate-only', action='store_true')
    a = ap.parse_args()
    before = original_hashes(a.data); tables = load_tables(a.data)
    if not a.validate_only:
        generate_extension(tables, a.output, a.days, a.seed)
    ext = load_extension(a.output)
    report = validate_extension(tables, ext)
    after = original_hashes(a.data)
    if before != after:
        raise ArithmeticError('Original dataset bytes changed.')
    report.update(original_csv_sha256=after, original_files_unchanged=True,
                  original_actual_row_counts={FILES[k]:len(v) for k,v in tables.items()},
                  generation_seed=a.seed if not a.validate_only else None)
    Path(a.output).mkdir(parents=True, exist_ok=True)
    (Path(a.output)/'validation_report_v2.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
