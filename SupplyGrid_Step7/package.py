import subprocess
import sys
import re
import zipfile
from pathlib import Path
from risk_core import *
def main():
    root=Path(__file__).resolve().parent;run=subprocess.run([sys.executable,'-m','unittest','test_step7','-v'],cwd=root,capture_output=True,text=True);(root/'results/test_log.txt').write_text(run.stdout+run.stderr)
    if run.returncode:raise RuntimeError(run.stderr)
    count=int(re.search(r'Ran (\d+) tests',run.stderr).group(1));prior=root.parent/'Step7_ML/results/prior_files_sha256.json'
    if prior.exists():
        for name,value in json.loads(prior.read_text()).items():
            if digest(root.parent/name)!=value:raise ValueError('Earlier project file changed')
    write_json(root/'results/validation_report.json',dict(status='PASS',tests_passed=count,saved_model_count=1,earlier_project_files_unchanged=prior.exists(),final_future_test='PENDING',integration_performed=False))
    files=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='SHA256SUMS.json'];sums={str(p.relative_to(root)):digest(p) for p in files};write_json(root/'SHA256SUMS.json',sums);files.append(root/'SHA256SUMS.json');target=root.parent/'SupplyGrid_Step7_One_Model.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(files):archive.write(p,str(p.relative_to(root.parent)))
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        import hashlib
        assert all(hashlib.sha256(archive.read(root.name+'/'+name)).hexdigest()==value for name,value in sums.items())
    print(target,target.stat().st_size,count,'tests passed')
if __name__=='__main__':main()
