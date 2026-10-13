"""Qualify the exact published IMU composition on the existing isolated Windows receiver."""
from datetime import datetime, timezone
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'source-223e6926'
BASE=ROOT/'source-778de777'
OUT=ROOT/'imu-composition-native-v1'
PY=ROOT/'python312/python.exe'
COMMIT='223e6926438b63dd848225da070f71575703c4cb'
OUT.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
receipt={'owner':'team-7cb7e049e2c0/runtime-consumer','commit':COMMIT,'interpreter':str(PY),'python':sys.version,'started_utc':datetime.now(timezone.utc).isoformat(),'status':'started'}
env=dict(os.environ,TEMP=str(ROOT/'temp'),TMP=str(ROOT/'temp'),PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(OUT/'matplotlib'),XDG_CACHE_HOME=str(OUT/'cache'))
try:
 source_receipt=json.loads((ROOT/'imu-composition-source-receipt.json').read_text())
 assert source_receipt['status']=='ready' and source_receipt['commit']==COMMIT
 pins=json.loads((ROOT/'imu-composition-source-pins.json').read_text())
 assert len(pins)==1348
 for name,pin in pins.items():assert sha((SOURCE/name).read_bytes())==pin['sha256'],name
 tests=['tests/analysis/test_imu_feature_timestamps.py','tests/analysis/test_stream_rate_admission.py','tests/analysis/test_emg_gap_adjacency.py','tests/analysis/test_sync_series_json.py','tests/analysis/test_video_qc_intervals.py','tests/analysis/test_plot_observations.py','tests/analysis/test_cli_console_encoding.py','tests/analysis/test_job_failure_cli.py','tests/analysis/test_phase_b_features.py','tests/analysis/test_numeric_batch_pipeline.py','tests/analysis/test_stream_gap_scope.py','tests/analysis/test_feature_table_paths.py']
 command=[str(PY),'-B','-m','pytest',*tests,'-vv','-rA','-p','no:cacheprovider','--basetemp='+str(OUT/'pytest-tmp'),'--junitxml='+str(OUT/'junit.xml')]
 with (OUT/'pytest.log').open('xb') as log:r=subprocess.run(command,cwd=SOURCE,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 receipt['pytest']={'command':command,'exit_code':r.returncode}
 assert r.returncode==0,'Inspect pytest.log'
 xml=ET.parse(OUT/'junit.xml').getroot()
 counts={'concrete_cases':len(list(xml.iter('testcase'))),'aggregate_tests':sum(int(n.get('tests','0')) for n in xml.iter('testsuite')),'failures':len(list(xml.iter('failure'))),'errors':len(list(xml.iter('error'))),'skipped':len(list(xml.iter('skipped')))}
 receipt['pytest']['junit']=counts
 assert counts['concrete_cases']==183 and counts['aggregate_tests']==207 and counts['failures']==counts['errors']==counts['skipped']==0,counts
 log=(OUT/'pytest.log').read_text(encoding='utf-8',errors='replace')
 receipt['diagnostics']={'windows_wmi_0x8007000e':log.count('Windows fatal exception: code 0x8007000e')}
 receiver=ROOT/'receive_imu_composition_mcap.py'
 command=[str(PY),'-B',str(receiver),'--baseline',str(BASE),'--candidate',str(SOURCE),'--python',str(PY),'--out',str(OUT/'public-jobs')]
 receipt['receiver_sha256']=sha(receiver.read_bytes())
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
 receipt['public_jobs']['cases']=summaries
 receipt['public_jobs']['actual_jobs']=8
 for name,pin in pins.items():assert sha((SOURCE/name).read_bytes())==pin['sha256'],name
 receipt['source_files_preserved']=len(pins)
 receipt['status']='qualified_composed_native_analysis'
 receipt['limits']=['Synthetic CaptureSuite receiving in one isolated owned Windows source.','No hardware, live acquisition, GUI, performance or default installation claim.','No unpublished EMG vectorization or axis-label/raw overlay adoption.','Earlier portable warning and receiver-setup failure evidence remains unchanged.']
except BaseException as exc:
 receipt.update(status='failed',error=type(exc).__name__+': '+str(exc));raise
finally:
 receipt['completed_utc']=datetime.now(timezone.utc).isoformat()
 (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 print(json.dumps(receipt,indent=2),flush=True)
