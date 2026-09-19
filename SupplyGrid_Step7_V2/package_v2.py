"""Package only Step 7 V2 files; verify tests and content hashes."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from risk_api import sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    root=Path(__file__).resolve().parent;out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('Choose an unused ZIP filename')
    env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='2';env['OMP_NUM_THREADS']='2'
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root),'-p','test_v2.py','-v'],
                          capture_output=True,text=True,env=env)
    write(root/'test_results.json',dict(exit_code=tests.returncode,stdout=tests.stdout,stderr=tests.stderr))
    if tests.returncode:raise RuntimeError('Tests failed; refusing to package')
    excluded={'__pycache__','my_scores.csv'}
    files=[f for f in root.rglob('*') if f.is_file() and not any(x in f.parts for x in excluded)
           and f.name!='SHA256SUMS.json' and f.suffix!='.pyc' and f.name!='risk_scores_demo.csv']
    manifest={str(f.relative_to(root)):sha(f) for f in sorted(files)}
    write(root/'SHA256SUMS.json',manifest);files.append(root/'SHA256SUMS.json')
    with ZipFile(out,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for f in sorted(files):z.write(f,'SupplyGrid_Step7_V2/'+str(f.relative_to(root)))
    with ZipFile(out) as z:
        if z.testzip():raise RuntimeError('ZIP integrity failure')
        assert not any(n.endswith('risk_model.joblib') or 'SupplyGrid_Step7/' in n for n in z.namelist())
    print('Created',out,'files',len(files),'size',out.stat().st_size)


if __name__=='__main__':main()
