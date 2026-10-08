# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path, PurePosixPath
import base64,hashlib,json,os,subprocess,datetime
r=Path('/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef');s=r/'source';packet=json.loads((r/'source-payload.json').read_text());assert not list(s.iterdir())
rows=[]
for f in packet['files']:
 rel=PurePosixPath(f['path']);assert not rel.is_absolute() and '..' not in rel.parts and f['mode'] in ['100644','100755']
 b=base64.b64decode(f['content'],validate=True) if f['encoding']=='base64' else f['content'].encode();blob=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert len(b)==f['size'] and blob==f['git_blob_sha'],f['path']
 p=s/f['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);p.chmod(int(f['mode'][-3:],8));rows.append({k:v for k,v in f.items() if k not in ['content','encoding']}|{'sha256':hashlib.sha256(b).hexdigest()})
subprocess.run(['git','init','-b','receiving/canonical-macos-session-doctor-5f566b5ec8ef',str(s)],check=True,capture_output=True)
subprocess.run(['git','-C',str(s),'add','--all'],check=True)
subprocess.run(['git','-C',str(s),'-c','user.name=ChatGPT estate receiving','-c','user.email=chatgpt-5f566b5ec8ef@localhost','commit','-m','Receive immutable canonical portable source d43bdea for native Mac qualification'],check=True,capture_output=True)
receipt={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'canonical_base':packet['base'],'native_commit':subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip(),'git_status':subprocess.check_output(['git','-C',str(s),'status','--porcelain'],text=True),'files':rows}
p=r/'evidence/source-inputs.json';p.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'native_commit':receipt['native_commit'],'files':len(rows),'bytes':sum(f['size'] for f in rows),'status':receipt['git_status'],'manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest()},indent=2))
