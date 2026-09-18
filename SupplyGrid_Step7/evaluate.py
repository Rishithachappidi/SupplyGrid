"""Development ranking/error/calibration diagnostics, or ONCE-only fresh final test."""
import argparse
from pathlib import Path
import pandas as pd
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from risk_core import *
from predict import load

def ranking_metrics(frame,model):
    ranked=model.predict(frame).merge(frame[['supplier_id','date','disruption_risk']],on=['supplier_id','date'],validate='one_to_one');rows=[]
    for k in [1,5,10,20]:
        hits=alerts=positives=population=0;random_hits=0.
        for date,group in ranked.groupby('date'):
            n=min(k,len(group));selected=group.sort_values('risk_rank').head(n)
            hits+=int(selected.disruption_risk.sum());alerts+=n;positives+=int(group.disruption_risk.sum());population+=len(group);random_hits+=n*group.disruption_risk.mean()
        rows.append(dict(k=k,precision_at_k=hits/alerts,recall_at_k=hits/positives if positives else None,
            lift_over_random_ranking=hits/random_hits if random_hits else None,hits=hits,alerts=alerts,
            aggregation='micro counts across dates; random expected hits account for daily prevalence and cohort size'))
    return ranked,pd.DataFrame(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',default='data/ml_dataset.csv');parser.add_argument('--root',default='.');parser.add_argument('--final-future-test',action='store_true')
    args=parser.parse_args();root=Path(args.root);model,manifest=load(root);frame=pd.read_csv(args.data);validate(frame)
    if args.final_future_test:
        if (root/'results/final_test_metrics.json').exists():raise FileExistsError('Final evaluation already performed')
        if frame.empty or pd.to_datetime(frame.date).min()<=pd.Timestamp(manifest['source_last_observed_date']):raise ValueError('Final test must be genuinely later than all observed history; old benchmark rejected')
        if not (pd.to_datetime(frame.label_window_end)-pd.to_datetime(frame.date)).dt.days.eq(7).all():raise ValueError('Wrong target horizon')
        prefix='final_test'
    else:
        if digest(args.data)!=manifest['data_sha256']['ml_dataset.csv']:raise ValueError('Development dataset differs from fitted run')
        frame=frame[frame.split=='validation'];prefix='development'
    if set(frame.disruption_risk.unique())!={0,1}:raise ValueError('Both classes required for evaluation')
    p=model.probability(frame);ranked,ranking=ranking_metrics(frame,model);ranking.to_csv(root/'results'/f'{prefix}_ranking_metrics.csv',index=False)
    write_json(root/'results'/f'{prefix}_metrics.json',dict(model=model.name,rows=len(frame),threshold=model.threshold,
        evaluation='fresh_future_test' if args.final_future_test else 'seen_development_validation',**metrics(frame.disruption_risk,p,model.threshold),
        data_sha256=digest(args.data),previously_selected_model=True))
    errors=frame[['supplier_id','date','disruption_risk']].copy();errors['risk_probability']=p;errors['predicted']=p>=model.threshold
    errors['error_type']=np.where(errors.predicted, np.where(errors.disruption_risk==1,'TP','FP'),np.where(errors.disruption_risk==1,'FN','TN'))
    errors['wrong_label_confidence']=np.where(errors.predicted, p,1-p);errors[errors.error_type.isin(['FP','FN'])].sort_values('wrong_label_confidence',ascending=False).to_csv(root/'results'/f'{prefix}_mistakes.csv',index=False,float_format='%.10g')
    group_metrics=[]
    for kind,groups in [('supplier',frame.groupby('supplier_id')),('month',frame.assign(month=frame.date.str[:7]).groupby('month'))]:
        for name,g in groups:
            prob=model.probability(g)
            if g.disruption_risk.nunique()==2:value=metrics(g.disruption_risk,prob,model.threshold)
            else:value=dict(brier=float(np.mean((prob-g.disruption_risk.to_numpy())**2)),note='AP/ROC omitted for single-class group')
            group_metrics.append(dict(group_kind=kind,group=str(name),rows=len(g),**value))
    pd.DataFrame(group_metrics).to_csv(root/'results'/f'{prefix}_group_performance.csv',index=False)
    obs,expected=calibration_curve(frame.disruption_risk,p,n_bins=8,strategy='quantile');pd.DataFrame(dict(predicted_probability=expected,observed_frequency=obs)).to_csv(root/'results'/f'{prefix}_calibration.csv',index=False)
    fig,axes=plt.subplots(1,2,figsize=(9,4));axes[0].plot(expected,obs,'o-');axes[0].plot([0,1],[0,1],'k--');axes[0].set(xlabel='Predicted risk',ylabel='Observed frequency',title=prefix+' calibration')
    matrix=confusion_matrix(frame.disruption_risk,p>=model.threshold,labels=[0,1]);axes[1].imshow(matrix,cmap='Blues')
    for i in range(2):
        for j in range(2):axes[1].text(j,i,str(matrix[i,j]),ha='center',va='center')
    axes[1].set(xticks=[0,1],yticks=[0,1],xlabel='Predicted',ylabel='Actual',title=prefix+' confusion matrix');fig.tight_layout();fig.savefig(root/'results'/f'{prefix}_plots.png',dpi=150);plt.close(fig)
    if not args.final_future_test:
        train=pd.read_csv(args.data);train=train[train.split=='train'];drift=[]
        for feature in NUMERIC:
            sd=float(train[feature].std());delta=float(frame[feature].mean()-train[feature].mean())
            drift.append(dict(feature=feature,train_mean=float(train[feature].mean()),development_mean=float(frame[feature].mean()),standardized_mean_shift=delta/sd if sd>0 else None))
        pd.DataFrame(drift).to_csv(root/'results/feature_drift.csv',index=False)
        rng=np.random.default_rng(SEED);sample=frame.sample(min(1500,len(frame)),random_state=SEED);baseline=average_precision_score(sample.disruption_risk,model.probability(sample));importance=[]
        for feature in FEATURES:
            changed=sample.copy();changed[feature]=rng.permutation(changed[feature].to_numpy());importance.append(dict(feature=feature,development_ap_decrease=float(baseline-average_precision_score(sample.disruption_risk,model.probability(changed)))))
        pd.DataFrame(importance).sort_values('development_ap_decrease',ascending=False).to_csv(root/'results/feature_importance.csv',index=False)
        sensitivity=[]
        for feature in ['weather_signal','congestion_signal','demand_pressure']:
            changed=sample.copy();changed[feature]=np.clip(changed[feature]+.2,0,1);base=model.probability(sample);new=model.probability(changed)
            sensitivity.append(dict(feature=feature,mean_risk_delta=float((new-base).mean()),fraction_increased=float((new>base).mean()),note='Illustrative sensitivity, not a causal or physically consistent scenario'))
        pd.DataFrame(sensitivity).to_csv(root/'results/robustness.csv',index=False)
    print(ranking.to_string(index=False));print((root/'results'/f'{prefix}_metrics.json').read_text())
if __name__=='__main__':main()
