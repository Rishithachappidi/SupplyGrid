"""Independent read-back checks; never reruns or tunes the model evaluation."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

def main():
    root=Path(__file__).resolve().parent;model_root=root.parent/'SupplyGrid_Step7';report=json.loads((root/'results/final_test_metrics.json').read_text());protocol=json.loads((root/'protocol.json').read_text())
    for name,sha in report['source_model_package_sha256'].items():
        if hashlib.sha256((model_root/name).read_bytes()).hexdigest()!=sha:raise ValueError('Model package changed')
    for name,sha in report['future_data_sha256'].items():
        if hashlib.sha256((root/'data'/name).read_bytes()).hexdigest()!=sha:raise ValueError('Future file changed')
    features=pd.read_csv(root/'data/future_test.csv');observations=pd.read_csv(root/'data/new_daily_observations.csv');events=pd.read_csv(root/'data/new_disruption_events.csv');predictions=pd.read_csv(root/'results/final_test_predictions.csv')
    if len(features)!=report['rows'] or len(predictions)!=len(features):raise ValueError('CSV row mismatch')
    if not (pd.to_datetime(features.date)>pd.Timestamp(protocol['cutoff'])).all():raise ValueError('Seen origins')
    if features.duplicated(['supplier_id','date']).any():raise ValueError('Duplicate origins')
    active=features.merge(observations[['supplier_id','date','active_disruption']],on=['supplier_id','date'],validate='one_to_one')
    if len(active)!=len(features) or active.active_disruption.any():raise ValueError('Forecasting already active disruption')
    if not (pd.to_datetime(features.label_window_end)-pd.to_datetime(features.date)).dt.days.eq(7).all():raise ValueError('Wrong label horizon')
    if pd.to_datetime(features.label_window_end).max()>pd.to_datetime(observations.date).max():raise ValueError('Incomplete future outcomes')
    checked=features.merge(predictions,on=['supplier_id','date'],validate='one_to_one',suffixes=('_actual','_prediction'))
    if not checked.disruption_risk_actual.eq(checked.disruption_risk_prediction).all():raise ValueError('Mismatched prediction labels')
    if not np.isfinite(predictions.disruption_probability).all() or not predictions.disruption_probability.between(0,1).all():raise ValueError('Invalid risk probabilities')
    # Independently reconstruct every label using the new event log, not the generator's label code.
    for supplier,part in features.groupby('supplier_id'):
        ev=pd.to_datetime(events.loc[events.supplier_id==supplier,'onset_date']).to_numpy();origins=pd.to_datetime(part.date).to_numpy()
        truth=((ev[None,:]>origins[:,None])&(ev[None,:]<=origins[:,None]+np.timedelta64(7,'D'))).any(axis=1).astype(int)
        np.testing.assert_array_equal(truth,part.disruption_risk)
    for date,part in predictions.groupby('date'):
        ranked=part.sort_values('risk_rank');np.testing.assert_array_equal(ranked.risk_rank,np.arange(1,len(ranked)+1))
        if not ranked.disruption_probability.is_monotonic_decreasing:raise ValueError('Invalid ranking')
    validation=dict(software_data_integrity='PASS',row_counts_read_from_csv=dict(forecast_rows=len(features),prediction_rows=len(predictions),new_observation_rows=len(observations),new_event_rows=len(events)),
       all_labels_independently_reconstructed=True,complete_followup=True,model_package_unchanged=True,
       predictive_performance_gate='NOT CERTIFIED: no business acceptance limits supplied',real_world_validation=False)
    (root/'results/integrity_validation.json').write_text(json.dumps(validation,indent=2));print(json.dumps(validation,indent=2))
if __name__=='__main__':main()
