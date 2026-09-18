import hashlib
import json
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parent
files=[p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='SHA256SUMS.json']
sums={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(root/'SHA256SUMS.json').write_text(json.dumps(sums,indent=2));files.append(root/'SHA256SUMS.json')
target=root.parent/'SupplyGrid_Step7_Future_Test_Only.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for p in sorted(files):archive.write(p,str(p.relative_to(root.parent)))
with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
print(target,target.stat().st_size)
