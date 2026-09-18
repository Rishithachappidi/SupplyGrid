"""Reconstruct rolling features and seven-day targets from the included daily history."""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
from risk_core import *
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',default='source_history');parser.add_argument('--output',default='regenerated_data');args=parser.parse_args();source=Path(args.source);out=Path(args.output)
    if out.exists():raise FileExistsError('Choose a fresh output directory')
    base=pd.read_csv(source/'base_supplier_features.csv');raw=pd.read_csv(source/'supplier_daily_observations.csv');events=pd.read_csv(source/'supplier_disruption_events.csv')
    if base.supplier_id.duplicated().any() or raw.duplicated(['supplier_id','date']).any() or raw.isna().any().any():raise ValueError('Invalid source keys/missing records')
    if not set(raw.supplier_id).issubset(set(base.supplier_id)):raise ValueError('Unknown supplier')
    raw['date']=pd.to_datetime(raw.date);events['onset_date']=pd.to_datetime(events.onset_date);events['end_date_exclusive']=pd.to_datetime(events.end_date_exclusive)
    if not set(raw.onset_today).issubset({0,1}) or not set(raw.active_disruption).issubset({0,1}):raise ValueError('Invalid event state')
    rows=[];forward=[]
    for supplier in base.to_dict('records'):
        part=raw[raw.supplier_id==supplier['supplier_id']].sort_values('date').reset_index(drop=True);ev=events[events.supplier_id==supplier['supplier_id']]
        if not part.date.diff().dropna().eq(pd.Timedelta(days=1)).all():raise ValueError('Missing daily coverage')
        onsets=part.onset_today.to_numpy(int);delays=part.observed_delay_fraction.to_numpy(float)
        for t in range(30,len(part)):
            if part.loc[t,'active_disruption']:continue
            day=part.loc[t,'date'];completed=ev[(ev.end_date_exclusive<=day)&(ev.onset_date>=day-pd.Timedelta(days=90))];past=np.flatnonzero(onsets[:t+1]);row=dict(supplier)
            row.update(date=str(day.date()),weather_signal=float(part.loc[t,'weather_signal']),congestion_signal=float(part.loc[t,'congestion_signal']),demand_pressure=float(part.loc[t,'demand_pressure']),utilization=min(1.,.5+.45*float(part.loc[t,'demand_pressure'])),delay_rate_7d=float(delays[t-6:t+1].mean()),onsets_30d=int(onsets[t-29:t+1].sum()),completed_duration_mean_90d=float(completed.duration_days.mean()) if len(completed) else 0.,days_since_onset=min(366,t-int(past[-1])) if len(past) else 366)
            if t+7<len(part):row.update(disruption_risk=int(onsets[t+1:t+8].any()),label_window_end=str(part.loc[t+7,'date'].date()));rows.append(row)
            elif t==len(part)-1:forward.append(row)
    frame=pd.DataFrame(rows);dates=sorted(frame.date.unique());cuts=[0,int(len(dates)*.55),int(len(dates)*.7),int(len(dates)*.85),len(dates)];mapping={}
    for k,name in enumerate(['train','calibration','validation','test']):
        for date in dates[cuts[k]:cuts[k+1]]:mapping[date]='purged' if k<3 and pd.Timestamp(date)+pd.Timedelta(days=7)>=pd.Timestamp(dates[cuts[k+1]]) else name
    frame['split']=frame.date.map(mapping);inference=pd.DataFrame(forward);validate(frame);validate(inference);out.mkdir(parents=True)
    frame.to_csv(out/'ml_dataset.csv',index=False,float_format='%.10g');inference.to_csv(out/'inference_features.csv',index=False,float_format='%.10g')
    if len(pd.read_csv(out/'ml_dataset.csv'))!=len(frame):raise ValueError('Incomplete written CSV')
    write_json(out/'provenance.json',dict(synthetic=True,rows=len(frame),source_sha256={p.name:digest(p) for p in source.glob('*.csv')}));print('Prepared',len(frame),'forecast origins')
if __name__=='__main__':main()
