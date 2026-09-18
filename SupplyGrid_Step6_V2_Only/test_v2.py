"""Small deterministic end-to-end tests and deliberate data/plan corruption tests.
Run: python -m unittest -v test_v2
"""
import copy
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from financial_blast_radius import calculate_financial_exposure
from extend_dataset_v2 import generate_extension, load_extension, validate_extension
from optimize_mitigation_v2 import Context, optimize_v2, audit_plan


def fixture():
    tables = {
        'suppliers': pd.DataFrame([dict(supplier_id='S1',component_capacity=5),dict(supplier_id='S2',component_capacity=5)]),
        'components': pd.DataFrame([
            dict(component_id='C1',supplier_id='S1',category='Battery',unit_cost=1,lead_time_days=0,minimum_order_qty=5,maximum_supply=5),
            dict(component_id='C2',supplier_id='S2',category='Battery',unit_cost=2,lead_time_days=0,minimum_order_qty=5,maximum_supply=5)]),
        'factories': pd.DataFrame([dict(factory_id='F1',production_capacity=5,current_utilization=0,
            operating_cost_per_unit=1,labor_cost_per_unit=1,storage_capacity=1000)]),
        'products': pd.DataFrame([dict(product_id='P1',factory_id='F1',production_time_hours=48,production_cost=999)]),
        'warehouses': pd.DataFrame([dict(warehouse_id='W1')]),
        'inventory': pd.DataFrame([dict(last_updated_date='2027-01-01')]),
        'bom': pd.DataFrame([dict(product_id='P1',component_id='C1',quantity_required=1,substitute_component_id='C2')]),
        'routes': pd.DataFrame([
            dict(route_id='R1',origin_id='S1',destination_id='F1',normal_transit_days=1,route_capacity=5,cost_per_unit=.2,estimated_transit_cost=3),
            dict(route_id='R2',origin_id='S2',destination_id='F1',normal_transit_days=1,route_capacity=5,cost_per_unit=.2,estimated_transit_cost=3),
            dict(route_id='R3',origin_id='F1',destination_id='W1',normal_transit_days=1,route_capacity=5,cost_per_unit=.5,estimated_transit_cost=2)]),
        'orders': pd.DataFrame([dict(order_id=o,product_id='P1',warehouse_id='W1',quantity=q,unit_price=2000) for o,q in [('A',2),('B',3)]]),
    }
    event = dict(supplier='S1',capacity_loss_percent=100,duration_days=5,start_date='2027-01-01',
        end_date_inclusive='2027-01-05',potential_order_ids=['A','B'],eligible_orders=[
            dict(order_id=o,product_id='P1',factory_id='F1',warehouse_id='W1',required_date='2027-01-05',uncovered_units=q) for o,q in [('A',2),('B',3)]])
    with tempfile.TemporaryDirectory() as tmp:
        generate_extension(tables,tmp,7)
        ext = load_extension(tmp)
    for col in ('quantity_on_hand','reserved_quantity','safety_stock','available_quantity','usable_quantity'):
        ext['factory_inventory'][col] = '0'
    sc = ext['supplier_calendar']
    for col in ('supplier_committed_units','component_committed_units'):
        sc[col] = '0'
    for col in ('supplier_available_units','component_available_units'):
        sc[col] = '5'
    options = dict(candidates=[],spare_finished_stock={})
    finance = calculate_financial_exposure(event,tables,10)
    return tables,ext,event,options,finance


def context(parts):
    return Context(*parts,'single-batch')


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.parts = fixture()

    def test_complete_procurement_production_path_and_hand_cost(self):
        r = optimize_v2(context(self.parts))
        self.assertEqual(r['status'],'OPTIMAL')
        self.assertEqual(r['objective_value'],30.50)
        self.assertEqual(r['audit']['orders_protected'],2)
        self.assertEqual(r['audit']['production_orders'],2)
        self.assertEqual(len(r['plan']['procurement_lots']),1)
        lot = r['plan']['procurement_lots'][0]
        self.assertEqual((lot['supplier_id'],lot['quantity'],lot['packs']),('S2',5,1))
        self.assertEqual(r['audit']['factory_material_balances']['F1:C2']['consumed'],5)
        self.assertTrue(all(j['start_date']=='2027-01-02' and j['arrival_date']=='2027-01-05' for j in r['plan']['production_jobs']))
        # 10 materials + 4 inbound + 10 conversion + 6.50 outbound = 30.50.
        # Product production_cost=999 is deliberately NOT added again.

    def test_factory_shared_slots(self):
        fc = self.parts[1]['factory_calendar']
        fc['committed_capacity_units']='2'; fc['available_capacity_units']='3'
        r = optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],63.50)
        self.assertEqual([j['order_id'] for j in r['plan']['production_jobs']],['B'])

    def test_moq_surplus_is_paid_and_carried_not_order_coverage(self):
        self.parts[2]['potential_order_ids']=['A']
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],21)
        self.assertEqual(r['plan']['procurement_lots'][0]['quantity'],5)
        self.assertEqual(r['audit']['factory_material_balances']['F1:C2']['closing_usable'],3)
        self.assertEqual(r['audit']['orders_protected'],1)

    def test_same_physical_substitute_cannot_satisfy_two_bom_roles_twice(self):
        tables=self.parts[0]
        tables['bom']=pd.concat([tables['bom'],pd.DataFrame([dict(
            product_id='P1',component_id='C2',quantity_required=1,substitute_component_id='')])],ignore_index=True)
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],81)
        self.assertEqual([j['order_id'] for j in r['plan']['production_jobs']],['A'])
        self.assertEqual(r['audit']['factory_material_balances']['F1:C2']['consumed'],4)

    def test_supplier_and_component_capacity_shared_across_factories(self):
        tables,ext,event,options,finance=self.parts
        f=tables['factories'].iloc[0].to_dict(); f['factory_id']='F2'
        tables['factories']=pd.concat([tables['factories'],pd.DataFrame([f])],ignore_index=True)
        p=tables['products'].iloc[0].to_dict(); p.update(product_id='P2',factory_id='F2')
        tables['products']=pd.concat([tables['products'],pd.DataFrame([p])],ignore_index=True)
        b=tables['bom'].iloc[0].to_dict(); b['product_id']='P2'
        tables['bom']=pd.concat([tables['bom'],pd.DataFrame([b])],ignore_index=True)
        inbound=tables['routes'].iloc[1].to_dict(); inbound.update(route_id='R4',destination_id='F2')
        outbound=tables['routes'].iloc[2].to_dict(); outbound.update(route_id='R5',origin_id='F2')
        tables['routes']=pd.concat([tables['routes'],pd.DataFrame([inbound,outbound])],ignore_index=True)
        tables['orders'].loc[tables['orders']['order_id']=='B','product_id']='P2'
        event['eligible_orders'][1].update(product_id='P2',factory_id='F2')
        with tempfile.TemporaryDirectory() as tmp:
            generate_extension(tables,tmp,7); ext=load_extension(tmp)
        for col in ('quantity_on_hand','reserved_quantity','safety_stock','available_quantity','usable_quantity'):
            ext['factory_inventory'][col]='0'
        for col in ('supplier_committed_units','component_committed_units'):
            ext['supplier_calendar'][col]='0'
        for col in ('supplier_available_units','component_available_units'):
            ext['supplier_calendar'][col]='5'
        finance=calculate_financial_exposure(event,tables,10)
        r=optimize_v2(context((tables,ext,event,options,finance)))
        self.assertEqual(r['objective_value'],63.50)
        self.assertEqual([j['factory_id'] for j in r['plan']['production_jobs']],['F2'])
        self.assertEqual(r['audit']['resource_utilization']['supplier:S2:2027-01-01'],dict(used=5,capacity=5,scope='shared'))
        self.assertEqual(r['audit']['resource_utilization']['component:C2:2027-01-01'],dict(used=5,capacity=5,scope='shared'))

    def test_supplier_disruption_capacity_is_applied_by_date(self):
        tables,ext,event,options,finance=self.parts
        event.update(supplier='S2',capacity_loss_percent=80)
        # S1 has zero remaining reservation capacity; S2's 80% loss leaves one
        # unit/day, smaller than the five-unit MOQ. Neither procurement path works.
        mask=ext['supplier_calendar']['supplier_id']=='S1'
        for col in ('supplier_committed_units','component_committed_units'):
            ext['supplier_calendar'].loc[mask,col]='5'
        for col in ('supplier_available_units','component_available_units'):
            ext['supplier_calendar'].loc[mask,col]='0'
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['audit']['orders_protected'],0)

    def test_procurement_and_production_do_not_override_no_action_cost(self):
        for o in self.parts[4]['detail']:
            o['penalty_usd']=0
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],0)
        self.assertEqual(r['audit']['orders_protected'],0)

    def test_dated_supplier_component_capacity_below_moq(self):
        sc = self.parts[1]['supplier_calendar']
        sc['component_committed_units']='1'; sc['supplier_committed_units']='1'
        sc['component_available_units']='4'; sc['supplier_available_units']='4'
        r = optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],100)
        self.assertEqual(r['audit']['orders_protected'],0)

    def test_factory_inventory_not_double_used(self):
        inv = self.parts[1]['factory_inventory']; mask=inv['component_id']=='C1'
        for col in ('quantity_on_hand','available_quantity','usable_quantity'):
            inv.loc[mask,col]='4'
        sc = self.parts[1]['supplier_calendar']
        sc['component_committed_units']='5'; sc['supplier_committed_units']='5'
        sc['component_available_units']='0'; sc['supplier_available_units']='0'
        r = optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],49.50)
        self.assertEqual(r['audit']['orders_protected'],1)
        self.assertEqual(r['audit']['factory_material_balances']['F1:C1']['closing_usable'],1)

    def test_production_duration_blocks_late_path(self):
        self.parts[0]['products']['production_time_hours']=72
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['objective_value'],100)

    def test_missing_inbound_route(self):
        self.parts[0]['routes']=self.parts[0]['routes'].query("route_id != 'R2'").copy()
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['audit']['orders_protected'],0)

    def test_unapproved_substitution_not_generated(self):
        self.parts[0]['bom']['substitute_component_id']=''
        self.parts[1]['factory_inventory']=self.parts[1]['factory_inventory'].query("component_id == 'C1'").copy()
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['audit']['orders_protected'],0)

    def test_empty_exposure(self):
        self.parts[2]['potential_order_ids']=[]
        r=optimize_v2(context(self.parts))
        self.assertEqual(r['status'],'OPTIMAL'); self.assertEqual(r['objective_value'],0)

    def test_independent_audit_rejects_corrupted_plans(self):
        ctx=context(self.parts); base=optimize_v2(ctx)['plan']
        bad=copy.deepcopy(base); bad['procurement_lots'][0]['quantity']=4
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base); bad['procurement_lots'][0]['supplier_id']='S1'
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base); bad['production_jobs'][0]['materials'][0]['quantity']+=1
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base); bad['production_jobs'][0]['materials'][0]['physical_component_id']='C999'
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base); bad['production_jobs'].append(copy.deepcopy(bad['production_jobs'][0]))
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base); bad['production_jobs'][0]['cost_breakdown_cents']['conversion_operating_cents']+=1
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base)
        bad['production_jobs'][0].update(start_date='2027-01-01',finish_date='2027-01-03',arrival_date='2027-01-04')
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)
        bad=copy.deepcopy(base)
        bad['production_jobs'][0].update(start_date='2027-01-03',finish_date='2027-01-05',arrival_date='2027-01-06')
        with self.assertRaises(ArithmeticError):audit_plan(ctx,bad)

    def test_independent_audit_rechecks_shared_capacities(self):
        ctx=context(self.parts); plan=optimize_v2(ctx)['plan']
        ctx.routes['R3']['route_capacity']=4
        with self.assertRaises(ArithmeticError):audit_plan(ctx,plan)
        ctx.routes['R3']['route_capacity']=5
        for r in ctx.fc.values():r['available_capacity_units']='4'
        with self.assertRaises(ArithmeticError):audit_plan(ctx,plan)
        for r in ctx.fc.values():r['available_capacity_units']='5'
        for r in ctx.sc.values():
            if r['supplier_id']=='S2':
                r['component_committed_units']='1'; r['supplier_committed_units']='1'
        with self.assertRaises(ArithmeticError):audit_plan(ctx,plan)

    def test_invalid_data_rejected_before_optimization(self):
        tables,ext,*_=self.parts
        changes=[('factory_inventory','factory_id','F999'),
                 ('factory_inventory','component_id','C999'),
                 ('factory_inventory','usable_quantity','-1'),
                 ('factory_inventory','snapshot_date','bad-date'),
                 ('supplier_calendar','supplier_id','S999'),
                 ('supplier_calendar','component_available_units','1.5'),
                 ('factory_calendar','conversion_cost_per_unit_usd','999')]
        for key,col,value in changes:
            with self.subTest(key=key,col=col):
                bad=copy.deepcopy(ext); bad[key].loc[bad[key].index[0],col]=value
                with self.assertRaises(ValueError):validate_extension(tables,bad)
        bad=copy.deepcopy(ext); bad['factory_calendar']=bad['factory_calendar'].iloc[:-1]
        with self.assertRaises(ValueError):validate_extension(tables,bad)
        bad=copy.deepcopy(ext); bad['supplier_calendar']=pd.concat([bad['supplier_calendar'],bad['supplier_calendar'].iloc[:1]],ignore_index=True)
        with self.assertRaises(ValueError):validate_extension(tables,bad)
        bad=copy.deepcopy(tables); bad['routes'].loc[0,'destination_id']='W999'
        with self.assertRaises(ValueError):validate_extension(bad,ext)
        bad=copy.deepcopy(tables); bad['bom'].loc[0,'quantity_required']=0
        with self.assertRaises(ValueError):validate_extension(bad,ext)

    def test_generation_reproducibility_and_refuse_overwrite(self):
        tables=self.parts[0]
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            generate_extension(tables,a,7); generate_extension(tables,b,7)
            for name in ('15_factory_component_inventory.csv','16_factory_capacity_calendar.csv','17_supplier_capacity_calendar.csv'):
                self.assertEqual((a/name).read_bytes(),(b/name).read_bytes())
            with self.assertRaises(FileExistsError):generate_extension(tables,a,7)


if __name__=='__main__':
    unittest.main(verbosity=2)
