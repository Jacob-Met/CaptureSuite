"""Receive the exact reviewed IMU analysis composition in a new owned checkout."""
from datetime import datetime, timezone
import hashlib, json, os, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source-223e6926'
COMMIT='223e6926438b63dd848225da070f71575703c4cb'
TREE='b330b1e2ad4728b42105252328d193880c53420c'
GIT=r'C:\Program Files\Git\cmd\git.exe'
receipt={'owner':'team-7cb7e049e2c0/runtime-consumer','device_id':'9ea77fe9-bb87-46e0-a5a8-8b3e25f6ff7e','commit':COMMIT,'tree':TREE,'started_utc':datetime.now(timezone.utc).isoformat()}
assert not SOURCE.exists(),'Inspect existing receiver instead of overwriting'
SOURCE.mkdir()
env=dict(os.environ,TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'),GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GIT_LFS_SKIP_SMUDGE='1')
def git(*args):
 r=subprocess.run([GIT,'-c','core.autocrlf=false',*args],cwd=SOURCE,env=env,capture_output=True,timeout=120)
 with (ROOT/'imu-composition-source.log').open('ab') as f:f.write(('git '+' '.join(args)+'\n').encode()+r.stdout+r.stderr+b'\n')
 assert r.returncode==0,'Inspect imu-composition-source.log'
 return r.stdout
try:
 git('init','--initial-branch=receiving')
 git('remote','add','origin','https://github.com/Jacob-Met/CaptureSuite.git')
 git('fetch','--no-tags','--depth=1','origin',COMMIT)
 git('checkout','--detach',COMMIT)
 assert git('rev-parse','HEAD').decode().strip()==COMMIT
 assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
 commit=git('cat-file','commit','HEAD').decode()
 parents=[line.split()[1] for line in commit.split('\n\n',1)[0].splitlines() if line.startswith('parent ')]
 assert parents==['778de777a26899895d014948a1b12d759a0f8d0f','865f3900590da523ab66434b581e2ebb3688be1c']
 receipt['parents']=parents; pins={};differences=[]
 for item in git('ls-tree','-rz','--full-tree','HEAD').split(b'\0'):
  if not item:continue
  header,path=item.split(b'\t',1);mode,kind,oid=header.decode().split();name=path.decode()
  assert kind=='blob' and mode in ('100644','100755')
  b=(SOURCE/name).read_bytes();actual=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
  pins[name]={'git_blob':oid,'working_git_blob':actual,'sha256':hashlib.sha256(b).hexdigest(),'mode':mode}
  if actual!=oid:differences.append(name)
 assert len(pins)==1348
 # Auxiliary shell/CMD checkout transformations are recorded; scientific and guide files must be exact.
 assert all(not n.startswith(('libs/','tests/','docs/','tools/run_analysis')) for n in differences),differences
 assert not git('status','--porcelain','--untracked-files=no').strip()
 receipt.update(status='ready',leaves=len(pins),working_byte_differences=differences,source_path=str(SOURCE))
 (ROOT/'imu-composition-source-pins.json').write_text(json.dumps(pins,indent=2),encoding='utf-8')
except BaseException as exc:
 receipt.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
finally:
 receipt['completed_utc']=datetime.now(timezone.utc).isoformat()
 (ROOT/'imu-composition-source-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(receipt,indent=2),flush=True)
