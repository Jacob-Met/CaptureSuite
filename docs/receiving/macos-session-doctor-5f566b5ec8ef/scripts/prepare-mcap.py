# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import datetime,hashlib,json,os,subprocess,time
r=Path('/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef');p=r/'dependencies/mcap';assert not p.exists()
args=['git','clone','--depth','1','--branch','releases/cpp/v2.1.1','https://github.com/foxglove/mcap.git',str(p)];start=time.monotonic();env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
with (r/'evidence/mcap-clone.log').open('w') as log: result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=120)
receipt={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':args,'exit_code':result.returncode,'duration_seconds':time.monotonic()-start}
if result.returncode==0:
 receipt['commit']=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip();receipt['status']=subprocess.check_output(['git','-C',str(p),'status','--porcelain'],text=True);receipt['files']=[{'path':str(f.relative_to(p)),'size':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted((p/'cpp/mcap/include').rglob('*')) if f.is_file()]
q=r/'evidence/mcap-source.json';q.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2));print('header_files='+str(len(receipt.get('files',[]))))
assert result.returncode==0 and receipt['commit']=='b2953496735e7b89d5b2ea58be73abed85317c5f' and not receipt['status']
