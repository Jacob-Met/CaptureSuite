"""Continue only actual MCAP receiving after the already successful native 183-case gate."""
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source-223e6926'
BASE=ROOT/'source-778de777'
OLD=ROOT/'imu-composition-native-v1'
OUT=ROOT/'imu-composition-native-v2'
PY=ROOT/'python312/python.exe'
OUT.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
receipt={'owner':'team-7cb7e049e2c0/runtime-consumer','commit':'223e6926438b63dd848225da070f71575703c4cb','python':sys.version,'interpreter':str(PY),'started_utc':datetime.now(timezone.utc).isoformat(),'status':'started','history':'v1 passed 183 cases plus24 subtests, then receiver stopped before fixtures on derived-bytecode key-set mismatch. No production change, bytecode deletion or gate rerun.'}
try:
 previous=json.loads((OLD/'receipt.json').read_text())
 assert previous['status']=='failed' and previous['pytest']['exit_code']==0
 assert previous['pytest']['junit']=={'concrete_cases':183,'aggregate_tests':207,'failures':0,'errors':0,'skipped':0}
 receipt['pytest_reused']={'receipt_path':str(OLD/'receipt.json'),'receipt_sha256':sha((OLD/'receipt.json').read_bytes()),'junit_sha256':sha((OLD/'junit.xml').read_bytes()),'counts':previous['pytest']['junit'],'diagnostics':previous['diagnostics']}
 pins=json.loads((ROOT/'imu-composition-source-pins.json').read_text())
 for name,pin in pins.items():assert sha((SOURCE/name).read_bytes())==pin['sha256'],name
 receiver=ROOT/'receive_imu_composition_mcap_native_v2.py'
 receipt['receiver_sha256']=sha(receiver.read_bytes())
 assert receipt['receiver_sha256']=='4859917eb4611ce89debf74724aad4e3e6f66fcd696dce13e88460cc298cb555'
 env=dict(os.environ,TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'),PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(OUT/'matplotlib'),XDG_CACHE_HOME=str(OUT/'cache'))
 command=[str(PY),'-B',str(receiver),'--baseline',str(BASE),'--candidate',str(SOURCE),'--python',str(PY),'--out',str(OUT/'public-jobs')]
 with (OUT/'public-jobs.log').open('xb') as log:r=subprocess.run(command,cwd=OUT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
 receipt['public_jobs']={'command':command,'exit_code':r.returncode}
 assert r.returncode==0,'Inspect public-jobs.log'
 course=json.loads((OUT/'public-jobs/receiving.json').read_text())
 assert course['status']=='ACCEPT' and course['actual_jobs']==8 and len(course['cases'])==4
 summaries=[]
 for case in course['cases']:
  a,b=case['records']
  assert a['job_manifest']['warnings']==b['job_manifest']['warnings']
  assert a['job_manifest']['errors']==b['job_manifest']['errors']==[]
  summaries.append({'case':case['name'],'baseline_mid_ns':a['t_mid_ns'],'candidate_mid_ns':b['t_mid_ns'],'candidate_dtype':b['t_mid_dtype'],'statuses':[a['status'],b['status']],'manifest_warnings':b['job_manifest']['warnings'],'non_time_equal':case['non_time_values_and_metadata_equal']})
 receipt['public_jobs'].update(cases=summaries,actual_jobs=8)
 for name,pin in pins.items():assert sha((SOURCE/name).read_bytes())==pin['sha256'],name
 receipt['source_files_preserved']=len(pins)
 receipt['status']='qualified_composed_native_analysis'
 receipt['limits']=['Synthetic analysis only; no hardware, live capture, GUI, performance or default installation claim.','Existing derived bytecode preserved separately; production source unchanged.','Portable kit remains immutable with its different environment warnings.']
except BaseException as exc:
 receipt.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
finally:
 receipt['completed_utc']=datetime.now(timezone.utc).isoformat()
 (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(receipt,indent=2),flush=True)
