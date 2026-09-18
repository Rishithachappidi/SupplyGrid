"""Generate one predeclared synthetic continuation and score the frozen model once."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

SEED=20260920
DAYS=180
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False))

def continuation(base,history,events):
    rng=np.random.default_rng(SEED);last=pd.to_datetime(history.date).max();first=pd.to_datetime(history.date).min();obs=[];new_events=[]
    for supplier in base.to_dict('records'):
        old=history[history.supplier_id==supplier['supplier_id']].sort_values('date');latest=old.iloc[-1];state=np.array([latest.weather_signal,latest.congestion_signal,latest.demand_pressure],float)
        past_events=events[events.supplier_id==supplier['supplier_id']];onset_dates=list(pd.to_datetime(past_events.onset_date));end=pd.to_datetime(past_events.end_date_exclusive).max() if len(past_events) else first
        for offset in range(1,DAYS+1):
            date=last+pd.Timedelta(days=offset);day=(date-first).days;seasonal=.08*np.sin(2*np.pi*day/90)
            state=np.clip(.90*state+.10*np.array([.35+seasonal,.35,.45])+rng.normal(0,.07,3),0,1)
            count=sum(date-pd.Timedelta(days=30)<=d<date for d in onset_dates)
            z=-6.5+2*state[0]+.9*state[1]+1.2*state[2]+.9*(1-supplier['reliability_score'])+.8*supplier['financial_risk']+.35*supplier['downstream_product_count']/100+.275*count
            onset=0
            if date>=end and rng.random()<1/(1+np.exp(-z)):
                duration=int(rng.integers(2,6));end=date+pd.Timedelta(days=duration);onset_dates.append(date);onset=1
                new_events.append(dict(supplier_id=supplier['supplier_id'],onset_date=str(date.date()),end_date_exclusive=str(end.date()),duration_days=duration))
            active=int(date<end);delay=rng.binomial(20,np.clip(.05+.15*state[0]+.10*state[1]+.35*active,0,1))/20
            obs.append(dict(supplier_id=supplier['supplier_id'],date=str(date.date()),weather_signal=state[0],congestion_signal=state[1],demand_pressure=state[2],observed_delay_fraction=delay,onset_today=onset,active_disruption=active))
    return pd.DataFrame(obs),pd.DataFrame(new_events)

def feature_rows(base,history,events,cutoff):
    rows=[]
    history=history.copy();history['date']=pd.to_datetime(history.date);events=events.copy();events['onset_date']=pd.to_datetime(events.onset_date);events['end_date_exclusive']=pd.to_datetime(events.end_date_exclusive)
    for supplier in base.to_dict('records'):
        part=history[history.supplier_id==supplier['supplier_id']].sort_values('date').reset_index(drop=True);ev=events[events.supplier_id==supplier['supplier_id']];onsets=part.onset_today.to_numpy(int);delays=part.observed_delay_fraction.to_numpy(float)
        for t in range(30,len(part)-7):
            day=part.loc[t,'date']
            if day<=cutoff or part.loc[t,'active_disruption']:continue
            completed=ev[(ev.end_date_exclusive<=day)&(ev.onset_date>=day-pd.Timedelta(days=90))];prior=np.flatnonzero(onsets[:t+1]);row=dict(supplier)
            row.update(date=str(day.date()),weather_signal=float(part.loc[t,'weather_signal']),congestion_signal=float(part.loc[t,'congestion_signal']),demand_pressure=float(part.loc[t,'demand_pressure']),utilization=min(1.,.5+.45*float(part.loc[t,'demand_pressure'])),delay_rate_7d=float(delays[t-6:t+1].mean()),onsets_30d=int(onsets[t-29:t+1].sum()),completed_duration_mean_90d=float(completed.duration_days.mean()) if len(completed) else 0.,days_since_onset=min(366,t-int(prior[-1])) if len(prior) else 366,disruption_risk=int(onsets[t+1:t+8].any()),label_window_end=str(part.loc[t+7,'date'].date()))
            rows.append(row)
    return pd.DataFrame(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--model-root',default='../SupplyGrid_Step7');args=parser.parse_args();root=Path(args.model_root).resolve();local=Path(__file__).resolve().parent
    if (local/'protocol.json').exists():raise FileExistsError('This fixed test has already been reserved/run. Read its saved results; no reseeding or retesting.')
    sys.path.insert(0,str(root));from predict import load;from risk_core import validate,metrics
    model,selection=load(root);watched=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts];before={str(p.relative_to(root)):digest(p) for p in watched}
    source=root/'source_history';base=pd.read_csv(source/'base_supplier_features.csv');history=pd.read_csv(source/'supplier_daily_observations.csv');events=pd.read_csv(source/'supplier_disruption_events.csv');cutoff=pd.to_datetime(history.date).max()
    if cutoff!=pd.Timestamp(selection['source_last_observed_date']):raise ValueError('Frozen model/source history cutoff mismatch')
    protocol=dict(seed=SEED,observation_days=DAYS,synthetic=True,cutoff=str(cutoff.date()),start=str((cutoff+pd.Timedelta(days=1)).date()),
       model_sha256=digest(root/'model/risk_model.joblib'),threshold=model.threshold,model_name=model.name,
       primary_metrics=['average_precision','precision','recall','f1','brier','false_alert_rate','daily_precision_at_k','daily_recall_at_k','daily_lift'],
       tuning_allowed=False,calibration_allowed=False,threshold_changes_allowed=False,
       generator='Same documented AR(1)/stochastic onset process, continued from last observed supplier state; new fixed random stream.',
       performance_acceptance_limits='Not supplied by user; no automatic predictive pass or deployment certification.',
       independence='Future random innovations/new onset draws not previously generated or inspected for model/feature decisions; same synthetic mechanism and same suppliers.')
    write(local/'protocol.json',protocol)
    new_obs,new_events=continuation(base,history,events);combined=pd.concat([history,new_obs],ignore_index=True);all_events=pd.concat([events,new_events],ignore_index=True)
    data=local/'data';data.mkdir();new_obs.to_csv(data/'new_daily_observations.csv',index=False,float_format='%.10g');new_events.to_csv(data/'new_disruption_events.csv',index=False)
    features=feature_rows(base,combined,all_events,cutoff);validate(features)
    if features.empty or pd.to_datetime(features.date).min()<=cutoff:raise ValueError('Old origins in final test')
    features.to_csv(data/'future_test.csv',index=False,float_format='%.10g');features=pd.read_csv(data/'future_test.csv');validate(features)
    if not (pd.to_datetime(features.label_window_end)-pd.to_datetime(features.date)).dt.days.eq(7).all():raise ValueError('Wrong target window')
    # Only after reserving/generating the fixed test: score the finalized model.
    probability=model.probability(features);result=metrics(features.disruption_risk,probability,model.threshold)
    ranked=model.predict(features).merge(features[['supplier_id','date','disruption_risk']],on=['supplier_id','date'],validate='one_to_one')
    ranking=[]
    for k in [1,5,10,20]:
        hits=alerts=positives=0;expected=0.
        for _,group in ranked.groupby('date'):
            n=min(k,len(group));hits+=int(group.sort_values('risk_rank').head(n).disruption_risk.sum());alerts+=n;positives+=int(group.disruption_risk.sum());expected+=n*group.disruption_risk.mean()
        ranking.append(dict(k=k,precision_at_k=hits/alerts,recall_at_k=hits/positives,lift_over_random=hits/expected))
    results=local/'results';results.mkdir();ranked.to_csv(results/'final_test_predictions.csv',index=False,float_format='%.10g');pd.DataFrame(ranking).to_csv(results/'final_test_ranking.csv',index=False)
    after={str(p.relative_to(root)):digest(p) for p in watched}
    if before!=after:raise ValueError('Frozen model package changed')
    report=dict(evaluation_status='COMPLETED_ONCE',synthetic_only=True,model_unchanged=True,calibration_unchanged=True,threshold_unchanged=True,
       observations_start=new_obs.date.min(),observations_end=new_obs.date.max(),forecast_start=features.date.min(),forecast_end=features.date.max(),
       rows=len(features),positives=int(features.disruption_risk.sum()),prevalence=float(features.disruption_risk.mean()),
       model=model.name,threshold=model.threshold,**result,ranking=ranking,baseline_ap=float(features.disruption_risk.mean()),
       no_alert_accuracy=1-float(features.disruption_risk.mean()),
       interpretation='Research evaluation complete. Predictive usefulness is not certified; no predeclared business acceptance limits. Real-world testing and downstream integration not performed.',
       source_model_package_sha256=before,future_data_sha256={p.name:digest(p) for p in data.glob('*')})
    write(results/'final_test_metrics.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['source_model_package_sha256','future_data_sha256']},indent=2))
if __name__=='__main__':main()
