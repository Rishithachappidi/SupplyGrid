"""One sealed synthetic extension after the already-exposed 2029-06-28 period."""
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from risk_api import Predictor,validate,metrics,ranking,write,sha

SEED=20261019
DAYS=180
CUTOFF=pd.Timestamp('2029-06-28')


def continuation(base,history,events):
    rng=np.random.default_rng(SEED);last=pd.to_datetime(history.date).max()
    first=pd.to_datetime(history.date).min();obs=[];new_events=[]
    if last!=CUTOFF:raise ValueError('Bridge ends on wrong date')
    for supplier in base.to_dict('records'):
        sid=supplier['supplier_id'];old=history[history.supplier_id==sid].sort_values('date')
        latest=old.iloc[-1];state=np.array([latest.weather_signal,latest.congestion_signal,latest.demand_pressure],float)
        past=events[events.supplier_id==sid];onset_dates=list(pd.to_datetime(past.onset_date))
        end=pd.to_datetime(past.end_date_exclusive).max() if len(past) else first
        for offset in range(1,DAYS+1):
            day=last+pd.Timedelta(days=offset)
            seasonal=.08*np.sin(2*np.pi*(day-first).days/90)
            state=np.clip(.90*state+.10*np.array([.35+seasonal,.35,.45])+rng.normal(0,.07,3),0,1)
            count=sum(day-pd.Timedelta(days=30)<=d<day for d in onset_dates)
            z=-6.5+2*state[0]+.9*state[1]+1.2*state[2]+.9*(1-supplier['reliability_score'])+.8*supplier['financial_risk']+.35*supplier['downstream_product_count']/100+.275*count
            onset=0
            if day>=end and rng.random()<1/(1+np.exp(-z)):
                duration=int(rng.integers(2,6));end=day+pd.Timedelta(days=duration)
                onset_dates.append(day);onset=1
                new_events.append(dict(supplier_id=sid,onset_date=str(day.date()),end_date_exclusive=str(end.date()),duration_days=duration))
            active=int(day<end)
            delay=rng.binomial(20,np.clip(.05+.15*state[0]+.10*state[1]+.35*active,0,1))/20
            obs.append(dict(supplier_id=sid,date=str(day.date()),weather_signal=state[0],congestion_signal=state[1],
                            demand_pressure=state[2],observed_delay_fraction=delay,onset_today=onset,active_disruption=active))
    return pd.DataFrame(obs),pd.DataFrame(new_events)


def reconstruct(base,history,events):
    history=history.copy();events=events.copy()
    history['date']=pd.to_datetime(history.date)
    events['onset_date']=pd.to_datetime(events.onset_date)
    events['end_date_exclusive']=pd.to_datetime(events.end_date_exclusive)
    if history.duplicated(['supplier_id','date']).any() or history.isna().any().any():raise ValueError('Invalid daily observations')
    rows=[]
    for supplier in base.to_dict('records'):
        sid=supplier['supplier_id'];part=history[history.supplier_id==sid].sort_values('date').reset_index(drop=True)
        if not part.date.diff().dropna().eq(pd.Timedelta(days=1)).all():raise ValueError('Non-contiguous daily records')
        ev=events[events.supplier_id==sid]
        onsets=part.onset_today.to_numpy(int);delays=part.observed_delay_fraction.to_numpy(float)
        for t in range(30,len(part)-7):
            day=part.loc[t,'date']
            if day<=CUTOFF or part.loc[t,'active_disruption']:continue
            completed=ev[(ev.end_date_exclusive<=day)&(ev.onset_date>=day-pd.Timedelta(days=90))]
            past=np.flatnonzero(onsets[:t+1]);row=dict(supplier)
            row.update(date=str(day.date()),weather_signal=float(part.loc[t,'weather_signal']),
                congestion_signal=float(part.loc[t,'congestion_signal']),demand_pressure=float(part.loc[t,'demand_pressure']),
                utilization=min(1.,.5+.45*float(part.loc[t,'demand_pressure'])),
                delay_rate_7d=float(delays[t-6:t+1].mean()),onsets_30d=int(onsets[t-29:t+1].sum()),
                completed_duration_mean_90d=float(completed.duration_days.mean()) if len(completed) else 0.,
                days_since_onset=min(366,t-int(past[-1])) if len(past) else 366,
                disruption_risk=int(onsets[t+1:t+8].any()),label_window_end=str(part.loc[t+7,'date'].date()))
            rows.append(row)
    frame=pd.DataFrame(rows);validate(frame)
    if not (pd.to_datetime(frame.label_window_end)-pd.to_datetime(frame.date)).dt.days.eq(7).all():raise ValueError('Forward label window incorrect')
    return frame


def run(root,original,bridge,output):
    root=Path(root);output=Path(output)
    if output.exists():raise FileExistsError('This future test has already been generated; do not repeat')
    model=Predictor(root);model_hashes=model.meta['checksums'].copy()
    old=Path(original)/'source_history'
    base=pd.read_csv(old/'base_supplier_features.csv')
    past=pd.read_csv(old/'supplier_daily_observations.csv')
    earlier=pd.read_csv(old/'supplier_disruption_events.csv')
    bridge_obs=pd.read_csv(Path(bridge)/'new_daily_observations.csv')
    bridge_events=pd.read_csv(Path(bridge)/'new_disruption_events.csv')
    history=pd.concat([past,bridge_obs],ignore_index=True)
    events=pd.concat([earlier,bridge_events],ignore_index=True)
    protocol=dict(seed=SEED,days=DAYS,cutoff=str(CUTOFF.date()),generator='documented same synthetic mechanism; new random stream',
        train_model_hash=model_hashes['model/xgboost_model.json'],threshold=model.threshold,
        policies_locked_before_generation=True,no_retuning_after_test=True,
        known_previous_test='2028-12-31 through 2029-06-28 already inspected: used only as chronological context',
        limitations='Same synthetic simulator and supplier pool, no real-enterprise generalization or statistically independent rows')
    output.mkdir(parents=True)
    write(output/'protocol.json',protocol)
    new_obs,new_events=continuation(base,history,events)
    combined=pd.concat([history,new_obs],ignore_index=True)
    all_events=pd.concat([events,new_events],ignore_index=True)
    frame=reconstruct(base,combined,all_events)
    (output/'data').mkdir()
    new_obs.to_csv(output/'data/new_daily_observations.csv',index=False,float_format='%.12g')
    new_events.to_csv(output/'data/new_disruption_events.csv',index=False)
    frame.to_csv(output/'data/future_test.csv',index=False,float_format='%.12g')
    # Score the frozen artifacts exactly once, after writing the generator outputs.
    result=model.predict(frame);prob=model.probability(frame)
    report=dict(status='COMPLETED_ONCE',synthetic_only=True,
        forecast_origin_start=frame.date.min(),forecast_origin_end=frame.date.max(),
        observed_start=new_obs.date.min(),observed_end=new_obs.date.max(),
        **metrics(frame.disruption_risk,prob,model.threshold),baseline_ap=float(frame.disruption_risk.mean()),
        ranking=ranking(frame,prob),
        expected_disruption_cost='UNAVAILABLE: no event-level causal loss labels and dated matching operational state',
        downstream_mitigation_change='NOT EVALUATED: 2027 operations cannot support 2029 forecast simulation',
        score_interpretation='Frozen V2 evaluated on new synthetic future after prior exposed future period; NOT new enterprise evidence')
    result=result.merge(frame[['supplier_id','date','disruption_risk']],left_on=['supplier_id','risk_date'],right_on=['supplier_id','date'],validate='one_to_one').drop(columns='date')
    result.to_csv(output/'test_predictions.csv',index=False,float_format='%.12g')
    write(output/'future_metrics.json',report)
    write(output/'data_checksums.json',{str(p.relative_to(output)):sha(p) for p in sorted((output/'data').iterdir())})
    if model.meta['checksums'] != model_hashes or any(sha(root/name)!=want for name,want in model_hashes.items()):raise RuntimeError('Frozen model changed during evaluation')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model-root',required=True);p.add_argument('--original-root',required=True)
    p.add_argument('--bridge-data',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.model_root,a.original_root,a.bridge_data,a.output),indent=2))
