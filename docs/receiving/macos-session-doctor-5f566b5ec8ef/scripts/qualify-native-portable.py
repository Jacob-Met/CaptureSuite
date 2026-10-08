# SPDX-License-Identifier: GPL-3.0-only
from pathlib import Path
import datetime,hashlib,json,os,platform,shutil,subprocess,time
r=Path('/Users/me/capturesuite-macos-session-doctor-20261008-5f566b5ec8ef');s=r/'source';build=r/'build';assert not build.exists();manifest=json.loads((r/'evidence/source-inputs.json').read_text())
def source_state():
 errors=[]
 for f in manifest['files']:
  p=s/f['path'];b=p.read_bytes();mode='100755' if p.stat().st_mode & 0o111 else '100644'
  if len(b)!=f['size'] or hashlib.sha256(b).hexdigest()!=f['sha256'] or mode!=f['mode']:errors.append(f['path'])
 return {'input_errors':errors,'git_status':subprocess.check_output(['git','-C',str(s),'status','--porcelain'],text=True),'commit':subprocess.check_output(['git','-C',str(s),'rev-parse','HEAD'],text=True).strip()}
receipt={'schema':'capturesuite.canonical-mac-portable-qualification/1','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'canonical_base':manifest['canonical_base'],'native_source':str(s),'host':{'system':platform.platform(),'machine':platform.machine(),'macos':platform.mac_ver()[0]},'source_before':source_state(),'disk_free_before':shutil.disk_usage(r).free,'phases':[]}
assert not receipt['source_before']['input_errors'] and not receipt['source_before']['git_status']
env=dict(os.environ,MCAP_INCLUDE_DIR=str(r/'dependencies/mcap/cpp/mcap/include'))
commands=[('configure',['/opt/homebrew/bin/cmake','-S',str(s),'-B',str(build),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_COMPILER=/usr/bin/clang++','-DCMAKE_PREFIX_PATH=/opt/homebrew;'+str(s/'cmake/linux-shims'),'-DCAPTURE_BUILD_TESTS=ON','-DCAPTURE_ENABLE_CAMERA_WORKER=OFF','-DCAPTURE_ENABLE_RADAR_WORKER=OFF','-DCAPTURE_WERROR=OFF']),('build',['/opt/homebrew/bin/cmake','--build',str(build),'--parallel','2']),('ctest',['/opt/homebrew/bin/ctest','--test-dir',str(build),'--output-on-failure','--no-tests=error','--output-junit',str(r/'evidence/native-ctest.xml')])]
for name,args in commands:
 t=time.monotonic();logpath=r/'evidence'/('native-'+name+'.log')
 with logpath.open('w') as log:
  try:done=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600);code=done.returncode
  except subprocess.TimeoutExpired:code='timeout'
 phase={'name':name,'argv':args,'exit_code':code,'duration_seconds':time.monotonic()-t,'log_sha256':hashlib.sha256(logpath.read_bytes()).hexdigest()};receipt['phases'].append(phase)
 (r/'evidence/native-qualification-progress.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(phase),flush=True)
 if code!=0:break
receipt['source_after']=source_state();receipt['disk_free_after']=shutil.disk_usage(r).free;receipt['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
binary=build/'tools/session_doctor/session_doctor'
if binary.is_file():receipt['binary']={'path':str(binary),'size':binary.stat().st_size,'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'mode':oct(binary.stat().st_mode & 0o777)}
p=r/'evidence/native-qualification-first.json';p.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'receipt':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'phases':receipt['phases'],'source_after':receipt['source_after'],'binary':receipt.get('binary')},indent=2),flush=True)
assert len(receipt['phases'])==3 and all(p['exit_code']==0 for p in receipt['phases']) and not receipt['source_after']['input_errors'] and not receipt['source_after']['git_status']
