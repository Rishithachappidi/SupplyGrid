"""Train XGBoost on historical train, calibrate later, select threshold on validation."""
import argparse
import platform
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.metrics import average_precision_score,roc_curve
from sklearn.linear_model import LogisticRegression
from risk_api import FEATURES,NUMERIC,validate,sha,write,metrics,ranking,Predictor

SEED=20260919
GRID=[dict(max_depth=d,min_child_weight=w,reg_lambda=l) for d in (1,2) for w in (20,50) for l in (5,20)]


def fit(train,params):
    pre=ColumnTransformer([('numeric',StandardScaler(),NUMERIC),
                           ('region',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['region'])])
    x=pre.fit_transform(train[FEATURES]);est=xgb.XGBClassifier(
        n_estimators=160,learning_rate=.035,subsample=.85,colsample_bytree=.9,
        tree_method='hist',eval_metric='logloss',random_state=SEED,n_jobs=2,
        **params).fit(x,train.disruption_risk)
    return pre,est.get_booster()


def score(pre,model,frame):
    return model.predict(xgb.DMatrix(pre.transform(frame[FEATURES])),output_margin=True)


def train(data,output,cap=.05):
    if output.exists():raise FileExistsError('Training output exists; frozen artifact cannot be overwritten')
    if not 0<cap<1:raise ValueError('False-alert cap must be between 0 and 1')
    frame=pd.read_csv(data/'ml_dataset.csv');validate(frame)
    if frame.split.isna().any() or not frame.disruption_risk.isin([0,1]).all():raise ValueError('Invalid target or split')
    if not (pd.to_datetime(frame.label_window_end)-pd.to_datetime(frame.date)).dt.days.eq(7).all():raise ValueError('Wrong seven-day target horizon')
    parts={k:frame[frame.split==k].copy() for k in ('train','calibration','validation','test')}
    if any(v.empty for v in parts.values()):raise ValueError('Missing split')
    for a,b in zip(list(parts.values())[:-1],list(parts.values())[1:]):
        if pd.to_datetime(a.label_window_end).max()>=pd.to_datetime(b.date).min():raise ValueError('Label window overlaps subsequent partition')
    train=parts['train'];dates=np.sort(train.date.unique());bounds=[int(len(dates)*q) for q in (.5,.67,.84,1.)]
    folds=[]
    for i in range(3):
        start=dates[bounds[i]];stop=dates[bounds[i+1]-1]
        fitrows=train[pd.to_datetime(train.label_window_end)<pd.Timestamp(start)]
        valrows=train[train.date.between(start,stop)]
        if fitrows.empty or valrows.empty:raise ValueError('Empty purged CV fold')
        folds.append((fitrows,valrows))
    trials=[]
    for config in GRID:
        aps=[]
        for a,b in folds:
            pre,model=fit(a,config)
            aps.append(float(average_precision_score(b.disruption_risk,score(pre,model,b))))
        trials.append(dict(config=config,fold_ap=aps,mean_ap=float(np.mean(aps))))
    winner=sorted(trials,key=lambda x:-x['mean_ap'])[0]
    pre,model=fit(train,winner['config'])
    cal=parts['calibration'];valid=parts['validation']
    calibrator=LogisticRegression(C=1,max_iter=1000,random_state=SEED).fit(score(pre,model,cal).reshape(-1,1),cal.disruption_risk)
    probabilities=calibrator.predict_proba(score(pre,model,valid).reshape(-1,1))[:,1]
    fpr,tpr,thresholds=roc_curve(valid.disruption_risk,probabilities,drop_intermediate=False)
    candidates=np.flatnonzero((fpr<=cap)&np.isfinite(thresholds))
    threshold=float(thresholds[sorted(candidates,key=lambda i:(-tpr[i],fpr[i],-thresholds[i]))[0]]) if len(candidates) else 1.0
    (output/'model').mkdir(parents=True)
    model.save_model(str(output/'model/xgboost_model.json'))
    joblib.dump(pre,output/'model/preprocessor.joblib')
    joblib.dump(calibrator,output/'model/calibrator.joblib')
    versions=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,scikit_learn=sklearn.__version__,xgboost=xgb.__version__,joblib=joblib.__version__)
    ranges={key:dict(start=v.date.min(),end=v.date.max(),last_label_end=v.label_window_end.max(),rows=len(v)) for key,v in parts.items()}
    ranges['future_evaluation']='NOT GENERATED when this model was frozen; see sealed_future_test.json'
    metadata=dict(model_version='SupplyGrid-XGBoost-native-v2',artifact_format='XGBoost JSON booster + independent sklearn preprocessor and sigmoid calibrator',
      versions=versions,training_seed=SEED,features=FEATURES,target='New supplier disruption onset in T+1 through T+7 inclusive, given supplier state through T; exclude active disruptions',
      date_ranges=ranges,hyperparameters=dict(n_estimators=160,learning_rate=.035,subsample=.85,colsample_bytree=.9,tree_method='hist',**winner['config']),
      model_selection='8 XGBoost candidates, best mean AP over 3 purged expanding train folds',selection_trials=trials,
      calibration='sigmoid fit on separate calibration period',threshold=threshold,threshold_rule=f'Maximize validation recall subject to {cap:.2%} false-alert-rate cap',
      historical_source='Original frozen Step7 synthetic supplier-day features; no new observed enterprise dataset',
      source_data_sha256=sha(data/'ml_dataset.csv'),model_checksum=sha(output/'model/xgboost_model.json'),
      checksums={f'model/{p.name}':sha(p) for p in (output/'model').iterdir()},
      known_previous_future_test='2028-12-31 to 2029-06-28 was previously inspected and is NOT an untouched final test for this V2')
    write(output/'model_metadata.json',metadata)
    report=dict(status='DEVELOPMENT_ONLY',winning_config=winner,validation=metrics(valid.disruption_risk,probabilities,threshold),
                ranking=ranking(valid,probabilities),alert_cap=cap,baseline_ap=float(valid.disruption_risk.mean()),
                warning='Do not select new thresholds/features using sealed future results')
    write(output/'development_report.json',report)
    # Round-trip the separately serialized artifacts before making any forecast.
    loaded=Predictor(output)
    np.testing.assert_allclose(loaded.probability(valid),probabilities,rtol=1e-5,atol=1e-7)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--false-alert-cap',type=float,default=.05)
    a=p.parse_args();print(train(a.data,a.output,a.false_alert_cap),flush=True)
