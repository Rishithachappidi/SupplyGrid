"""Leakage, artifact, probability and future-data integrity checks."""
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from risk_api import Predictor,sha,validate,metrics,ranking
from sealed_future import CUTOFF,reconstruct

ROOT=Path(__file__).resolve().parent
ORIGINAL=ROOT.parent/'SupplyGrid_Step7'
BRIDGE=ROOT.parent/'SupplyGrid_Step7_Future_Test_Only/data'


class Step7V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=Predictor(ROOT)
        cls.inference=pd.read_csv(ORIGINAL/'data/inference_features.csv')

    def test_native_serialization(self):
        native=ROOT/'model/xgboost_model.json'
        self.assertTrue(native.is_file())
        content=json.loads(native.read_text())
        self.assertIn('learner',content)
        self.assertNotIn('risk_model.joblib',[p.name for p in (ROOT/'model').iterdir()])

    def test_model_metadata_checksum(self):
        meta=self.model.meta
        self.assertEqual(meta['model_checksum'],sha(ROOT/'model/xgboost_model.json'))
        for name,value in meta['checksums'].items():self.assertEqual(sha(ROOT/name),value)
        self.assertEqual(meta['target'].split(',')[0], 'New supplier disruption onset in T+1 through T+7 inclusive')

    def test_probability_and_stable_contract(self):
        scores=self.model.predict(self.inference)
        self.assertEqual(set(scores.columns),{'supplier_id','risk_date','risk_probability','risk_level','model_version','risk_rank'})
        self.assertTrue(scores.risk_probability.between(0,1).all())
        self.assertEqual(len(scores),len(self.inference))

    def test_corrupted_input(self):
        wrong=self.inference.copy();wrong.loc[0,'weather_signal']=float('nan')
        with self.assertRaises(ValueError):self.model.predict(wrong)
        wrong=self.inference.copy();wrong.loc[0,'date']='not a date'
        with self.assertRaises(ValueError):self.model.predict(wrong)

    def test_purged_chronology(self):
        frame=pd.read_csv(ORIGINAL/'data/ml_dataset.csv')
        parts=[frame[frame.split==v] for v in ['train','calibration','validation','test']]
        for a,b in zip(parts[:-1],parts[1:]):
            self.assertLess(pd.to_datetime(a.label_window_end).max(),pd.to_datetime(b.date).min())

    def test_future_labels_reconstructed_independently(self):
        future=ROOT/'sealed_future_result/data'
        self.assertTrue(future.is_dir())
        base=pd.read_csv(ORIGINAL/'source_history/base_supplier_features.csv')
        past=pd.read_csv(ORIGINAL/'source_history/supplier_daily_observations.csv')
        old_events=pd.read_csv(ORIGINAL/'source_history/supplier_disruption_events.csv')
        combined=pd.concat([past,pd.read_csv(BRIDGE/'new_daily_observations.csv'),pd.read_csv(future/'new_daily_observations.csv')],ignore_index=True)
        all_events=pd.concat([old_events,pd.read_csv(BRIDGE/'new_disruption_events.csv'),pd.read_csv(future/'new_disruption_events.csv')],ignore_index=True)
        rebuilt=reconstruct(base,combined,all_events)
        recorded=pd.read_csv(future/'future_test.csv')
        self.assertEqual(len(rebuilt),len(recorded))
        self.assertEqual(rebuilt[['supplier_id','date','disruption_risk','label_window_end']].to_dict('records'),
                         recorded[['supplier_id','date','disruption_risk','label_window_end']].to_dict('records'))
        self.assertTrue((pd.to_datetime(rebuilt.date)>CUTOFF).all())

    def test_probability_calibration_and_reproducibility(self):
        v=pd.read_csv(ORIGINAL/'data/ml_dataset.csv');v=v[v.split=='validation']
        first=self.model.probability(v);second=Predictor(ROOT).probability(v)
        np.testing.assert_array_equal(first,second)
        recorded=json.loads((ROOT/'development_report.json').read_text())
        self.assertAlmostEqual(metrics(v.disruption_risk,first,self.model.threshold)['average_precision'],
                               recorded['validation']['average_precision'],places=7)

    def test_future_report_consistency(self):
        result=ROOT/'sealed_future_result'
        future=pd.read_csv(result/'data/future_test.csv')
        scores=self.model.probability(future)
        measured=metrics(future.disruption_risk,scores,self.model.threshold)
        report=json.loads((result/'future_metrics.json').read_text())
        for key in ('average_precision','recall','precision','brier','false_alert_rate','n','positives'):
            self.assertAlmostEqual(measured[key],report[key],places=8)
        self.assertEqual(report['expected_disruption_cost'].split(':')[0],'UNAVAILABLE')


if __name__=='__main__':unittest.main()
