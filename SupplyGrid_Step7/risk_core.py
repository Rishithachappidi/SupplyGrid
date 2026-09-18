"""Single-model calibrated supplier risk, ranking and additive explanations."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score,roc_auc_score,brier_score_loss,
    precision_score,recall_score,f1_score,accuracy_score,confusion_matrix)

SEED=20260918
NUMERIC=['reliability_score','financial_risk','geopolitical_risk','weather_risk','cyber_risk',
 'component_capacity','lead_time_days','lead_time_std','component_count','downstream_product_count',
 'downstream_factory_count','route_count','graph_degree','weather_signal','congestion_signal',
 'demand_pressure','utilization','delay_rate_7d','onsets_30d','completed_duration_mean_90d','days_since_onset']
FEATURES=NUMERIC+['region']
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,allow_nan=False))
def validate(frame):
    missing=set(FEATURES+['supplier_id','date'])-set(frame.columns)
    if missing:raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    if frame[FEATURES+['supplier_id','date']].isna().any().any():raise ValueError('Missing input; no silent imputation')
    if frame.duplicated(['supplier_id','date']).any():raise ValueError('Duplicate supplier/date')
    values=frame[NUMERIC].to_numpy(float)
    if not np.isfinite(values).all() or (values<0).any():raise ValueError('Invalid numeric input')
    bounded=['reliability_score','financial_risk','geopolitical_risk','weather_risk','cyber_risk','weather_signal','congestion_signal','demand_pressure','utilization','delay_rate_7d']
    if (frame[bounded]>1).any().any():raise ValueError('Fraction outside [0,1]')
    pd.to_datetime(frame.date,errors='raise')
class SupplierRiskModel:
    def __init__(self,estimator,calibrator,threshold,name):
        self.estimator=estimator;self.calibrator=calibrator;self.threshold=threshold;self.name=name
    def raw_score(self,frame):
        validate(frame)
        if hasattr(self.estimator,'decision_function'):return self.estimator.decision_function(frame[FEATURES])
        p=np.clip(self.estimator.predict_proba(frame[FEATURES])[:,1],1e-7,1-1e-7);return np.log(p/(1-p))
    def probability(self,frame):return self.calibrator.predict_proba(self.raw_score(frame).reshape(-1,1))[:,1]
    def predict(self,frame):
        p=self.probability(frame);out=frame[['supplier_id','date']].copy();out['disruption_probability']=p
        out=out.sort_values(['date','disruption_probability','supplier_id'],ascending=[True,False,True])
        out['risk_rank']=out.groupby('date').cumcount()+1
        out['risk_level']=np.where(out.disruption_probability>=self.threshold,'HIGH','LOW')
        out['horizon_days']=7;out['model_version']='SupplyGrid-'+self.name+'-single-v1';return out
    def explain(self,frame):
        # Contributions add to calibrated log-odds, NOT directly to probability or causal effects.
        validate(frame);transformed=self.estimator.named_steps['preprocessing'].transform(frame[FEATURES]);clf=self.estimator.named_steps['classifier']
        names=self.estimator.named_steps['preprocessing'].get_feature_names_out();slope=float(self.calibrator.coef_[0,0]);intercept=float(self.calibrator.intercept_[0])
        if hasattr(clf,'coef_'):
            contributions=transformed*clf.coef_[0];bias=np.full(len(frame),float(clf.intercept_[0]))
        else:
            import xgboost as xgb
            values=clf.get_booster().predict(xgb.DMatrix(transformed),pred_contribs=True)
            contributions=values[:,:-1];bias=values[:,-1]
        contributions*=slope;bias=bias*slope+intercept;rows=[]
        for i,row in enumerate(frame.itertuples()):
            for k in np.argsort(-np.abs(contributions[i]))[:5]:
                rows.append(dict(supplier_id=row.supplier_id,date=row.date,feature=str(names[k]),
                    calibrated_log_odds_contribution=float(contributions[i,k]),calibrated_baseline_log_odds=float(bias[i]),
                    direction='increases' if contributions[i,k]>0 else 'decreases'))
        return pd.DataFrame(rows),contributions,bias
def metrics(y,p,threshold):
    label=p>=threshold;tn,fp,fn,tp=confusion_matrix(y,label,labels=[0,1]).ravel()
    return dict(average_precision=float(average_precision_score(y,p)),roc_auc=float(roc_auc_score(y,p)),brier=float(brier_score_loss(y,p)),
      precision=float(precision_score(y,label,zero_division=0)),recall=float(recall_score(y,label,zero_division=0)),f1=float(f1_score(y,label,zero_division=0)),
      accuracy=float(accuracy_score(y,label)),false_alert_rate=float(fp/(fp+tn)),alert_fraction=float(label.mean()),tp=int(tp),fp=int(fp),tn=int(tn),fn=int(fn))
