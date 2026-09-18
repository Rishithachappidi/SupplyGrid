"""Predict and explain ranked supplier risk using the one saved model."""
import argparse
from pathlib import Path
import joblib
import pandas as pd
from risk_core import *
def load(root):
    root=Path(root);manifest=json.loads((root/'results/selection.json').read_text())
    if digest(root/'model/risk_model.joblib')!=manifest['model_sha256']:raise ValueError('Model checksum mismatch')
    return joblib.load(root/'model/risk_model.joblib'),manifest
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',default='data/inference_features.csv');parser.add_argument('--root',default='.');parser.add_argument('--output',default='results/supplier_risk_scores.csv')
    args=parser.parse_args();model,_=load(args.root);frame=pd.read_csv(args.input);validate(frame)
    result=model.predict(frame);Path(args.output).parent.mkdir(parents=True,exist_ok=True);result.to_csv(args.output,index=False,float_format='%.10g')
    explanation,_,_=model.explain(frame);explanation.to_csv(Path(args.output).with_name('supplier_explanations.csv'),index=False,float_format='%.10g')
    print(result.head(10).to_string(index=False));print('Saved',len(result),'ranked suppliers')
if __name__=='__main__':main()
