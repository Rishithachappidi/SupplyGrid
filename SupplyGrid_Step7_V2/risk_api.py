"""Stable V2 risk inference. Only the preprocessor/calibrator use joblib."""
import hashlib
import json
import math
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, confusion_matrix

FEATURES = ['reliability_score','financial_risk','geopolitical_risk','weather_risk','cyber_risk',
 'component_capacity','lead_time_days','lead_time_std','component_count','downstream_product_count',
 'downstream_factory_count','route_count','graph_degree','weather_signal','congestion_signal',
 'demand_pressure','utilization','delay_rate_7d','onsets_30d','completed_duration_mean_90d',
 'days_since_onset','region']
NUMERIC = FEATURES[:-1]
SCHEMA = ['supplier_id','date'] + FEATURES


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf8')


def validate(frame):
    if set(SCHEMA)-set(frame.columns):raise ValueError('Missing features: '+str(sorted(set(SCHEMA)-set(frame.columns))))
    if frame[SCHEMA].isna().any().any() or frame.duplicated(['supplier_id','date']).any():raise ValueError('Missing values or duplicate supplier/date')
    if not np.isfinite(frame[NUMERIC].to_numpy(dtype=float)).all():raise ValueError('Nonfinite numeric input')
    if (frame[NUMERIC]<0).any().any():raise ValueError('Negative numeric feature')
    if pd.to_datetime(frame.date,format='%Y-%m-%d',errors='raise').dt.strftime('%Y-%m-%d').ne(frame.date.astype(str)).any():raise ValueError('Date must be ISO YYYY-MM-DD')
    if not frame.supplier_id.astype(str).str.fullmatch(r'S\d{3}').all():raise ValueError('Invalid supplier')
    if not frame.region.astype(str).str.len().gt(0).all():raise ValueError('Invalid region')
    return frame


def metrics(labels, probabilities, threshold):
    y=np.asarray(labels,dtype=int);p=np.asarray(probabilities,dtype=float)
    if not len(y) or set(y)!={0,1} or not np.isfinite(p).all() or np.min(p)<0 or np.max(p)>1:
        raise ValueError('Invalid evaluation labels/probabilities')
    tn,fp,fn,tp=map(int,confusion_matrix(y,p>=threshold,labels=[0,1]).ravel())
    return dict(n=len(y),positives=int(y.sum()),prevalence=float(y.mean()),
      average_precision=float(average_precision_score(y,p)),roc_auc=float(roc_auc_score(y,p)),
      brier=float(brier_score_loss(y,p)),accuracy=(tp+tn)/len(y),
      precision=tp/(tp+fp) if tp+fp else 0.,recall=tp/(tp+fn) if tp+fn else 0.,
      f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
      false_alert_rate=fp/(fp+tn) if fp+tn else 0.,tp=tp,fp=fp,tn=tn,fn=fn)


class Predictor:
    def __init__(self,root):
        root=Path(root);self.meta=json.loads((root/'model_metadata.json').read_text())
        for name,want in self.meta['checksums'].items():
            if sha(root/name)!=want:raise ValueError('Model artifact checksum mismatch: '+name)
        self.preprocessor=joblib.load(root/'model/preprocessor.joblib')
        self.calibrator=joblib.load(root/'model/calibrator.joblib')
        self.booster=xgb.Booster(model_file=str(root/'model/xgboost_model.json'))
        self.features=self.meta['features'];self.threshold=float(self.meta['threshold'])

    def probability(self,frame):
        validate(frame)
        x=self.preprocessor.transform(frame[self.features])
        raw=self.booster.predict(xgb.DMatrix(x),output_margin=True).reshape(-1,1)
        p=self.calibrator.predict_proba(raw)[:,1]
        if not np.isfinite(p).all() or np.min(p)<0 or np.max(p)>1:raise ValueError('Invalid risk probabilities')
        return p

    def predict(self,frame):
        p=self.probability(frame)
        out=frame[['supplier_id','date']].copy().rename(columns={'date':'risk_date'})
        out['risk_probability']=p
        out=out.sort_values(['risk_date','risk_probability','supplier_id'],ascending=[True,False,True]).reset_index(drop=True)
        out['risk_level']=np.where(out.risk_probability>=self.threshold,'HIGH','LOW')
        out['risk_rank']=out.groupby('risk_date').cumcount()+1
        out['model_version']=self.meta['model_version']
        return out[['supplier_id','risk_date','risk_probability','risk_level','model_version','risk_rank']]


def ranking(frame,probabilities,ks=(1,5,10,20)):
    temp=frame[['date','supplier_id','disruption_risk']].copy()
    temp['p']=probabilities;results=[]
    for k in ks:
        hits=n=positive=expected=0.
        for _,day in temp.groupby('date'):
            top=day.sort_values(['p','supplier_id'],ascending=[False,True]).head(k)
            hits+=top.disruption_risk.sum();n+=len(top)
            positive+=day.disruption_risk.sum();expected+=len(top)*day.disruption_risk.mean()
        results.append(dict(k=k,precision_at_k=float(hits/n),recall_at_k=float(hits/positive),
                            lift_over_random=float(hits/expected)))
    return results
