"""Verify the native IMU supplement using only the Python standard library."""
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent
    outer=zipfile.ZipFile(path) if path.is_file() else None
    read=outer.read if outer else lambda n:(path/n).read_bytes()
    manifest=json.loads(read('MANIFEST.json'))
    for name,pin in manifest.items():
        b=read(name);assert len(b)==pin['bytes'] and sha(b)==pin['sha256'],name
    raw=read('evidence/native-evidence.zip')
    assert len(raw)==376314 and sha(raw)=='e4e684e1718df128d2866fe88b14b3f5159c09c823cb6a22d11e3a2655e03748'
    z=zipfile.ZipFile(io.BytesIO(raw))
    native=json.loads(z.read('MANIFEST.json'))
    assert len(native)==208
    for name,pin in native.items():
        b=z.read(name);assert len(b)==pin['bytes'] and sha(b)==pin['sha256'],name
    source=json.loads(z.read('imu-composition-source-receipt.json'))
    assert source['status']=='ready' and source['commit']=='223e6926438b63dd848225da070f71575703c4cb'
    assert source['tree']=='b330b1e2ad4728b42105252328d193880c53420c'
    assert source['parents']==['778de777a26899895d014948a1b12d759a0f8d0f','865f3900590da523ab66434b581e2ebb3688be1c']
    pins=json.loads(z.read('imu-composition-source-pins.json'))
    assert len(pins)==1348 and len(source['working_byte_differences'])==9
    assert all(p['git_blob']==p['working_git_blob'] for n,p in pins.items() if n.startswith(('libs/','tests/','docs/')))
    final=json.loads(z.read('native-v2/receipt.json'))
    assert final['status']=='qualified_composed_native_analysis' and final['source_files_preserved']==1348
    assert sha(z.read('native-v1/receipt.json'))==final['pytest_reused']['receipt_sha256']
    assert sha(z.read('native-v1/junit.xml'))==final['pytest_reused']['junit_sha256']
    xml=ET.fromstring(z.read('native-v1/junit.xml'))
    assert len(list(xml.iter('testcase')))==183
    assert sum(int(x.get('tests','0')) for x in xml.iter('testsuite'))==207
    assert not list(xml.iter('failure'))+list(xml.iter('error'))+list(xml.iter('skipped'))
    assert final['pytest_reused']['diagnostics']['windows_wmi_0x8007000e']==0
    course=json.loads(z.read('native-v2/public-jobs/receiving.json'))
    assert course['status']=='ACCEPT' and course['actual_jobs']==8 and course['source_unchanged']
    a=course['source_pins']['baseline'];b=course['source_pins']['candidate']
    assert a.keys()==b.keys() and len(a)==96
    assert [n for n in a if a[n]!=b[n]]==['capture_analysis/capture_analysis/features/imu.py']
    assert len(course['preserved_existing_bytecode']['baseline'])==39
    assert course['preserved_existing_bytecode']['candidate']=={}
    assert sha(read('receive_imu_composition_mcap_native_v2.py'))==final['receiver_sha256']=='4859917eb4611ce89debf74724aad4e3e6f66fcd696dce13e88460cc298cb555'
    outputs=0
    for case in course['cases']:
        label=case['name'];prefix='native-v2/public-jobs/'+label+'/'
        before,after=case['records']
        assert after['t_mid_ns']==case['spec']['expected_mid_ns'] and after['t_mid_dtype']=='int64'
        assert (before['t_mid_ns']==after['t_mid_ns'])==(label=='ordinary')
        for key in ('loaded_arrays','loaded_times','sensor_ids','non_time_values','non_time_dtypes','schema','status','warnings'):
            assert before[key]==after[key],(label,key)
        assert before['job_manifest']['warnings']==after['job_manifest']['warnings']
        assert before['job_manifest']['errors']==after['job_manifest']['errors']==[]
        warnings=after['job_manifest']['warnings']
        assert not any('jsonschema' in w for w in warnings)
        assert (len(warnings)==1 and 'duration_ns' in warnings[0]) if label=='negative_even' else warnings==[]
        for name,pin in case['input_pins'].items():
            assert sha(z.read(prefix+'fixture.mmsession/'+name))==pin
        for record in (before,after):
            job=prefix+record['label']+'/job/'
            rows=list(csv.DictReader(io.StringIO(z.read(job+'features/imu/sim.imu.upper/windows.csv').decode())))
            assert len(rows)==1 and int(rows[0]['t_mid_ns'])==record['t_mid_ns']
            for output in record['job_manifest']['outputs']:
                data=z.read(job+output['relativePath'])
                assert len(data)==output['bytes'] and sha(data)==output['sha256']
                outputs+=1
    assert outputs==56
    print(json.dumps({'status':'ACCEPT','outer_payloads':len(manifest),'native_payloads':len(native),
        'source_leaves':1348,'library_files':96,'preserved_bytecode':39,'concrete_tests':183,
        'passing_subtests':24,'aggregate_tests':207,'actual_native_jobs':8,'saved_output_payloads':outputs,
        'native_errors':0,'native_job_warnings':'Only the two negative-time jobs retain inherited unknown-duration warning.',
        'numerical_or_native_rerun':False}))


if __name__=='__main__':
    main()
