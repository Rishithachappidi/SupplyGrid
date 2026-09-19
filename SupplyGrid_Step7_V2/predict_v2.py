"""Stable Step 8-compatible CLI and Python API; no raw XGBoost object in output."""
import argparse
from pathlib import Path
import pandas as pd
from risk_api import Predictor


def predict_suppliers(root,features):
    frame=pd.read_csv(features) if isinstance(features,(str,Path)) else features
    return Predictor(root).predict(frame)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model-root',type=Path,required=True)
    p.add_argument('--features',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Output exists')
    result=predict_suppliers(a.model_root,a.features)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(a.output,index=False,float_format='%.12g')
    print(result.head(10).to_string(index=False))
