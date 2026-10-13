"""Receive exact IMU median timestamps through real MCAP and saved public jobs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pins(root):
    return {p.relative_to(root).as_posix(): digest(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file()}


def library_pins(root):
    return {name:value for name,value in pins(root/'libs/python').items()
            if '__pycache__' not in Path(name).parts and not name.endswith('.pyc')}


def bytecode_pins(root):
    return {name:value for name,value in pins(root/'libs/python').items()
            if '__pycache__' in Path(name).parts or name.endswith('.pyc')}


CHILD = r'''
import hashlib,json,sys
from pathlib import Path
source,package,out=map(Path,sys.argv[1:4])
label=sys.argv[4]
sys.path[:0]=[str(source/'libs/python'/n) for n in ('capture_analysis','capture_session','capture_protocol')]
import numpy as np
import pandas as pd
from capture_analysis import JobParams,run,hash_sources_tree
from capture_analysis.discover import discover_streams
from capture_analysis.loaders.imu import load_imu
from capture_analysis.types import TimeWindow
from capture_analysis.features import imu
assert Path(imu.__file__).resolve()==(source/'libs/python/capture_analysis/capture_analysis/features/imu.py').resolve()
raw=Path(imu.__file__).read_bytes()
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()=={'baseline':'0ee47b3d579e4c3732634958dda21ae724beca9e','candidate':'329431e05d73d18e3a3da708537b4ec14bbc047b'}[label]
expected=json.loads((package/'receiver-case.json').read_text())
times=expected['timestamps']
window=TimeWindow(min(times),max(times))
streams=discover_streams(package)
assert len(streams)==1
loaded=load_imu(streams[0],window,max_ram_bytes=1024**2)
assert loaded.t_frame_ns.dtype==np.dtype('int64')
assert loaded.t_frame_ns.tolist()==sorted(times)
arrays={name:{'dtype':str(a.dtype),'shape':list(a.shape),'sha256':hashlib.sha256(a.tobytes()).hexdigest()}
        for name,a in [('t_frame_ns',loaded.t_frame_ns),('accel',loaded.accel),('gyro',loaded.gyro),('quat',loaded.quat)]}
before=hash_sources_tree(package)
result=run(package,JobParams(command='features',overwrite_job_id='imu-timestamp-'+label,
    start_session_ns=min(times),end_session_ns=max(times),max_ram_bytes=1024**2))
assert result.status in ('completed','completed_with_warnings'),result.status
assert hash_sources_tree(package)==before
rel='features/imu/sim.imu.upper/windows.parquet'
table=pd.read_parquet(result.job_dir/rel)
csv=pd.read_csv(result.job_dir/rel.replace('.parquet','.csv'))
assert table.shape==(1,20),table.shape
mid=int(table.at[0,'t_mid_ns'])
assert int(csv.at[0,'t_mid_ns'])==mid
if label=='candidate':
 assert mid==expected['expected_mid_ns'],(mid,expected)
 assert table.t_mid_ns.dtype==np.dtype('int64')
schema=json.loads((result.job_dir/'features/_schema.json').read_text())
out.mkdir()
import shutil
shutil.copytree(result.job_dir,out/'job')
record={'label':label,'status':result.status,'warnings':result.qc.get('warnings',[]) if result.qc else [],
    'implementation_path':imu.__file__,'implementation_sha256':hashlib.sha256(raw).hexdigest(),
    'loaded_arrays':arrays,'loaded_times':loaded.t_frame_ns.tolist(),'sensor_ids':loaded.sensor_ids,
    't_mid_ns':mid,'t_mid_dtype':str(table.t_mid_ns.dtype),'columns':list(table.columns),'rows':len(table),
    'non_time_values':table.drop(columns='t_mid_ns').to_dict(orient='list'),
    'non_time_dtypes':{k:str(v) for k,v in table.drop(columns='t_mid_ns').dtypes.items()},
    'schema':schema,'inputs_unchanged':True,'job_manifest':result.manifest}
(out/'receiving.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'label':label,'t_mid_ns':mid,'expected':expected['expected_mid_ns'],'status':result.status}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True)
    roots = {'baseline': args.baseline, 'candidate': args.candidate}
    source_pins = {k: library_pins(v) for k,v in roots.items()}
    original_bytecode = {k: bytecode_pins(v) for k,v in roots.items()}
    assert source_pins['baseline'].keys() == source_pins['candidate'].keys()
    changed = [p for p in source_pins['baseline'] if source_pins['baseline'][p] != source_pins['candidate'][p]]
    assert changed == ['capture_analysis/capture_analysis/features/imu.py'], changed
    sys.path[:0] = [str(args.baseline/'libs/python'/n) for n in ('capture_analysis','capture_session','capture_protocol')]
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2
    from mcap.writer import Writer
    cases = [
        ('ordinary', [1,3,5], 3),
        ('large_odd', [(1<<53)+1,(1<<53)+3,(1<<53)+5], (1<<53)+3),
        ('upper_even', [(1<<63)-2,(1<<63)-1], (1<<63)-2),
        ('negative_even', [-(1<<53)-2,-(1<<53)-1], -(1<<53)-1),
    ]
    receipts=[]
    for name,times,expected in cases:
        case_out=args.out/name
        case_out.mkdir()
        package=case_out/'fixture.mmsession'
        shutil.copytree(args.baseline/'tests/fixtures/mini_session',package)
        shutil.rmtree(package/'processing')
        shutil.rmtree(package/'sources/sim.emg.main')
        manifest=json.loads((package/'manifest.json').read_text())
        manifest['sourceIds']=['sim.imu.upper']
        (package/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        stream=package/'sources/sim.imu.upper/streams/sim.imu.upper.frames'
        stream_doc=json.loads((stream/'stream.json').read_text())
        stream_doc.update(nominalRateHz=100.0,dimensions=[2])
        (stream/'stream.json').write_text(json.dumps(stream_doc),encoding='utf-8')
        gap_path=package/'sources/sim.imu.upper/health/gaps.jsonl'
        gap_path.parent.mkdir(exist_ok=True)
        gap_path.write_text('',encoding='utf-8')
        mcap=stream/'segments/000000.mcap'
        with mcap.open('wb') as fh:
            writer=Writer(fh)
            writer.start(profile='',library='capturesuite-imu-composed-receiving')
            sid=writer.register_schema(name='imu.frame/1',encoding='protobuf',data=b'')
            channel=writer.register_channel(topic='imu',message_encoding='protobuf',schema_id=sid)
            for i,t in enumerate(times):
                msg=imu_frame_pb2.ImuFrame()
                msg.timing.session_time_ns=t
                msg.timing.sequence_number=i
                msg.frame_index=i
                for j,sensor_id in enumerate(('left','right')):
                    s=msg.sensors.add(sensor_id=sensor_id,qw=1.0)
                    s.accel_x=float(i+j+1);s.accel_y=float(2*i-j);s.accel_z=9.0
                    s.gyro_x=0.25*(i+1);s.gyro_y=-0.5*j;s.gyro_z=0.125
                # MCAP log time is unsigned; the protobuf timing header is the signed analysis clock.
                writer.add_message(channel_id=channel,log_time=i,publish_time=i,data=msg.SerializeToString())
            writer.finish()
        integrity={'schemaVersion':'1','files':[{'path':mcap.relative_to(package).as_posix(),
            'sizeBytes':mcap.stat().st_size,'sha256':digest(mcap.read_bytes()),
            'startSessionTimeNs':min(times),'endSessionTimeNs':max(times)}]}
        (package/'integrity.json').write_text(json.dumps(integrity),encoding='utf-8')
        spec={'name':name,'timestamps':times,'expected_mid_ns':expected,'sensors':['left','right'],
              'nominal_rate_hz':100.0,'synthetic':True,'mcap_log_time':'nonnegative ordinal'}
        (package/'receiver-case.json').write_text(json.dumps(spec),encoding='utf-8')
        original=pins(package)
        records=[]
        for label,source in roots.items():
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
            proc=subprocess.run([args.python,'-B','-c',CHILD,str(source),str(package),str(case_out/label),label],
                                env=env,capture_output=True,timeout=90)
            (case_out/(label+'.stdout.txt')).write_bytes(proc.stdout)
            (case_out/(label+'.stderr.txt')).write_bytes(proc.stderr)
            assert proc.returncode==0,(name,label,proc.stderr.decode(errors='replace'),proc.stdout.decode(errors='replace'))
            record=json.loads((case_out/label/'receiving.json').read_text())
            records.append(record)
        a,b=records
        for key in ('loaded_arrays','loaded_times','sensor_ids','non_time_values','non_time_dtypes','schema','status','warnings'):
            assert a[key]==b[key],(name,key)
        assert b['t_mid_ns']==expected
        assert (a['t_mid_ns']==expected)==(name=='ordinary'),(name,a['t_mid_ns'])
        after={n:h for n,h in pins(package).items() if not n.startswith('processing/')}
        assert after==original
        receipts.append({'name':name,'spec':spec,'input_pins':original,'records':records,
                         'inputs_unchanged':True,'non_time_values_and_metadata_equal':True})
        print(json.dumps({'case':name,'baseline':a['t_mid_ns'],'candidate':b['t_mid_ns'],'expected':expected}),flush=True)
    for label,source in roots.items():
        assert library_pins(source)==source_pins[label]
        assert bytecode_pins(source)==original_bytecode[label]
    result={'status':'ACCEPT','baseline_commit':'778de777a26899895d014948a1b12d759a0f8d0f',
        'candidate_commit':'223e6926438b63dd848225da070f71575703c4cb','source_pins':source_pins,
        'cases':receipts,'actual_jobs':8,'source_unchanged':True,
        'preserved_existing_bytecode':original_bytecode,
        'receiver_adaptation':'Existing __pycache__/.pyc files are separately preserved; all non-bytecode source files remain compared by equal key sets and exact hashes.',
        'limits':['Synthetic real MCAP and actual public feature jobs; no hardware or live capture.',
                  'Explicit signed selection bounds keep allocation bounded; no nominal-rate memory policy change.',
                  'Original and candidate feature tables differ only in t_mid_ns for the three precision cases.',
                  'Original upper-limit marker uses uint64; accepted candidate retains signed int64.',
                  'No repeated 512-case oracle, performance, GUI or default-installation claim.']}
    (args.out/'receiving.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':'ACCEPT','actual_jobs':8,'baseline_precision_failures':3}),flush=True)


if __name__=='__main__':
    main()
