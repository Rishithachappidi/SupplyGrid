import unittest
from pathlib import Path
from scipy.special import expit
from risk_core import *
from predict import load
class Step7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model,cls.manifest=load('.');cls.frame=pd.read_csv('data/ml_dataset.csv');cls.forward=pd.read_csv('data/inference_features.csv')
    def test_one_model(self):self.assertEqual(len(list(Path('model').glob('*.joblib'))),1)
    def test_temporal_selection(self):
        for fold in self.manifest['folds']:self.assertLess(pd.Timestamp(fold['train_label_end']),pd.Timestamp(fold['validation_start']))
        expected=sorted(self.manifest['candidate_search'],key=lambda r:(-r['mean_temporal_ap'],r['candidate']))[0];self.assertEqual(expected,self.manifest['winner'])
    def test_all_targets(self):
        raw=pd.read_csv('source_history/supplier_daily_observations.csv')
        for supplier,part in raw.groupby('supplier_id'):
            part=part.sort_values('date').reset_index(drop=True);prefix=np.r_[0,np.cumsum(part.onset_today.to_numpy(int))];t=np.arange(len(part)-7);mapping=dict(zip(part.date.iloc[:len(t)],((prefix[t+8]-prefix[t+1])>0).astype(int)));origins=self.frame[self.frame.supplier_id==supplier];np.testing.assert_array_equal(origins.date.map(mapping),origins.disruption_risk)
    def test_no_future_features(self):self.assertFalse(set(FEATURES)&{'disruption_risk','label_window_end','capacity_loss','duration_days','financial_impact','split'})
    def test_train_only_scaler(self):np.testing.assert_allclose(self.model.estimator.named_steps['preprocessing'].named_transformers_['numeric'].mean_,self.frame[self.frame.split=='train'][NUMERIC].mean().to_numpy())
    def test_probabilities_reload(self):
        a=self.model.probability(self.forward);b=joblib.load('model/risk_model.joblib').probability(self.forward);np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-12);self.assertTrue(((a>=0)&(a<=1)).all())
    def test_ranks(self):
        result=self.model.predict(self.forward);self.assertTrue(result.disruption_probability.is_monotonic_decreasing);np.testing.assert_array_equal(result.risk_rank,np.arange(1,len(result)+1))
    def test_additive_explanation(self):
        _,contrib,bias=self.model.explain(self.forward.iloc[:10]);np.testing.assert_allclose(expit(contrib.sum(axis=1)+bias),self.model.probability(self.forward.iloc[:10]),rtol=1e-5,atol=1e-6)
    def test_corrupted_inputs(self):
        for value in [np.nan,-1,np.inf]:
            bad=self.forward.copy();bad.loc[0,NUMERIC[0]]=value
            with self.assertRaises(ValueError):validate(bad)
        with self.assertRaises(ValueError):validate(pd.concat([self.forward,self.forward.iloc[:1]]))
    def test_alert_cap(self):
        val=self.frame[self.frame.split=='validation'];self.assertLessEqual(metrics(val.disruption_risk,self.model.probability(val),self.model.threshold)['false_alert_rate'],self.manifest['provisional_false_alert_cap']+1e-10)
    def test_no_final_test_claim(self):self.assertFalse(self.manifest['benchmark_test_evaluated']);self.assertFalse(Path('results/final_test_metrics.json').exists())
    def test_seen_final_period_rejected(self):
        import subprocess,sys
        result=subprocess.run([sys.executable,'evaluate.py','--final-future-test'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('genuinely later',result.stderr)
    def test_missing_column_rejected(self):
        with self.assertRaises(ValueError):validate(self.forward.drop(columns='weather_signal'))
    def test_rank_reset_multiple_dates(self):
        other=self.forward.copy();other['date']='2028-12-31';result=self.model.predict(pd.concat([self.forward,other]))
        for _,group in result.groupby('date'):np.testing.assert_array_equal(group.risk_rank,np.arange(1,len(group)+1))
if __name__=='__main__':unittest.main()
