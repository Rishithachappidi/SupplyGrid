"""Small justified temporal model search; saves ONLY one final fitted risk model."""
import argparse
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score,roc_curve
from xgboost import XGBClassifier
from risk_core import *

def estimator(spec,weight):
    pre=ColumnTransformer([('numeric',StandardScaler(),NUMERIC),('region',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['region'])])
    if spec['family']=='LogisticRegression':clf=LogisticRegression(C=spec['C'],class_weight='balanced' if spec['weight']=='full' else None,max_iter=1000,random_state=SEED)
    else:clf=XGBClassifier(n_estimators=120,max_depth=spec['depth'],learning_rate=.04,subsample=.85,colsample_bytree=.9,min_child_weight=30,reg_lambda=10,
        scale_pos_weight=weight if spec['weight']=='full' else np.sqrt(weight) if spec['weight']=='mild' else 1.,tree_method='hist',eval_metric='logloss',random_state=SEED,n_jobs=2)
    return Pipeline([('preprocessing',pre),('classifier',clf)])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',default='data');parser.add_argument('--output',default='.');parser.add_argument('--max-false-alert-rate',type=float,default=.05)
    args=parser.parse_args();root=Path(args.output);data=Path(args.data)
    if not 0<args.max_false_alert_rate<1:raise ValueError('False-alert cap must be in (0,1)')
    if (root/'model/risk_model.joblib').exists():raise FileExistsError('Choose a fresh --output; preserving fitted model')
    frame=pd.read_csv(data/'ml_dataset.csv');validate(frame)
    for col in ['date','label_window_end']:pd.to_datetime(frame[col],errors='raise')
    if not (pd.to_datetime(frame.label_window_end)-pd.to_datetime(frame.date)).dt.days.eq(7).all():raise ValueError('Wrong future target window')
    train=frame[frame.split=='train'];cal=frame[frame.split=='calibration'];val=frame[frame.split=='validation']
    for first,second in [(train,cal),(cal,val)]:
        if pd.to_datetime(first.label_window_end).max()>=pd.to_datetime(second.date).min():raise ValueError('Temporal leakage')
    specs=[dict(family='LogisticRegression',C=c,weight=w) for c in [.01,.1,1.] for w in ['none','full']]
    specs += [dict(family='XGBoost',depth=d,weight=w) for d in [1,2] for w in ['none','mild','full']]
    dates=sorted(train.date.unique());cuts=[int(len(dates)*x) for x in [.5,.67,.84,1.]];search=[];folds=[]
    for i in range(3):
        start=dates[cuts[i]];end=dates[cuts[i+1]-1];fit=train[pd.to_datetime(train.label_window_end)<pd.Timestamp(start)];score=train[(train.date>=start)&(train.date<=end)]
        folds.append((fit,score));print('Temporal fold',i+1,len(fit),len(score),flush=True)
    for i,spec in enumerate(specs):
        aps=[]
        for fit,score in folds:
            weight=(len(fit)-fit.disruption_risk.sum())/fit.disruption_risk.sum();pipe=estimator(spec,float(weight));pipe.fit(fit[FEATURES],fit.disruption_risk)
            aps.append(float(average_precision_score(score.disruption_risk,pipe.predict_proba(score[FEATURES])[:,1])))
        search.append(dict(candidate=i,spec=spec,mean_temporal_ap=float(np.mean(aps)),fold_ap=aps));print(spec,round(np.mean(aps),5),flush=True)
    winner=sorted(search,key=lambda r:(-r['mean_temporal_ap'],r['candidate']))[0]
    weight=(len(train)-train.disruption_risk.sum())/train.disruption_risk.sum();pipe=estimator(winner['spec'],float(weight));pipe.fit(train[FEATURES],train.disruption_risk)
    temporary=SupplierRiskModel(pipe,None,1.,winner['spec']['family']);sigmoid=LogisticRegression(C=1.,max_iter=1000,random_state=SEED).fit(temporary.raw_score(cal).reshape(-1,1),cal.disruption_risk)
    temporary.calibrator=sigmoid;p=temporary.probability(val);fpr,tpr,thresholds=roc_curve(val.disruption_risk,p,drop_intermediate=False)
    allowed=np.flatnonzero(fpr<=args.max_false_alert_rate);index=sorted(allowed,key=lambda k:(-tpr[k],fpr[k],-thresholds[k]))[0]
    threshold=float(thresholds[index]) if np.isfinite(thresholds[index]) else 1.0000001;temporary.threshold=threshold
    (root/'model').mkdir(parents=True,exist_ok=True);joblib.dump(temporary,root/'model/risk_model.joblib',compress=3)
    results=root/'results';results.mkdir(parents=True,exist_ok=True)
    write_json(results/'selection.json',dict(candidate_search=search,winner=winner,selection_rule='maximum mean AP across three expanding temporal folds inside train; tie candidate order',
      folds=[dict(train_end=a.date.max(),train_label_end=a.label_window_end.max(),validation_start=b.date.min(),validation_end=b.date.max(),train_rows=len(a),validation_rows=len(b)) for a,b in folds],
      threshold=threshold,threshold_rule='maximize validation recall subject to false-alert cap; tie smaller FPR then higher threshold',
      provisional_false_alert_cap=args.max_false_alert_rate,cap_requires_business_review=True,
      calibration_partition='calibration',probability_calibration='sigmoid',benchmark_test_evaluated=False,
      final_test_status='PENDING genuinely unseen future history; existing periods are development evidence',
      source_last_observed_date=pd.read_csv(data/'inference_features.csv').date.max(),data_sha256={p.name:digest(p) for p in data.glob('*') if p.is_file()},
      model_sha256=digest(root/'model/risk_model.joblib'),synthetic=True,integration_performed=False))
    write_json(results/'validation_metrics.json',dict(partition='validation_development_not_final_test',rows=len(val),prevalence=float(val.disruption_risk.mean()),
       model=winner['spec']['family'],**metrics(val.disruption_risk,p,threshold),baseline_ap=float(val.disruption_risk.mean())))
    out=temporary.predict(val);out=out.merge(val[['supplier_id','date','disruption_risk']],on=['supplier_id','date'],validate='one_to_one');out.to_csv(results/'development_predictions.csv',index=False,float_format='%.10g')
    print('Single saved winner',winner['spec']);print((results/'validation_metrics.json').read_text())

if __name__=='__main__':main()
