# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

OWNER=Path('/workspace/scratch/20b27c2ea29e/workers/estate-production')
REPO=OWNER/'capturesuite'
OUT=Path('/dev/shm/ultra-20b27c2e-estate-production-capture-qc')

def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p.relative_to(root).parts[0]!='processing'}

receipts={}
for case, expected in [('no_gap',0),('closed_gap',2)]:
    original=OWNER/'capturesuite-evidence'/(case+'.mmsession')
    destination=OUT/('candidate-witness-'+case+'.mmsession')
    shutil.copytree(original,destination,ignore=shutil.ignore_patterns('processing'))
    before=hashes(destination)
    assert before==hashes(original)
    command=[sys.executable,str(REPO/'tools/run_analysis.py'),'qc',str(destination),
             '--overwrite-job-id','gap-review','--strict-warnings']
    proc=subprocess.run(command,cwd=REPO,capture_output=True,text=True,timeout=30)
    (OUT/(case+'-candidate-cli.log')).write_text(proc.stdout+proc.stderr)
    assert proc.returncode==expected,(proc.returncode,proc.stdout,proc.stderr)
    after=hashes(destination)
    assert before==after
    job=destination/'processing/jobs/gap-review'
    qc=json.loads((job/'reports/qc.json').read_text())
    manifest=json.loads((job/'job_manifest.json').read_text())
    assert qc['schemaId']=='capture.analysis_qc/2'
    if case=='closed_gap':
        assert qc['trafficLights']['sim.emg.main']=='warn'
        assert qc['gaps'][0]['durationNs']=='2500000000'
        assert manifest['status']=='completed_with_warnings'
    else:
        assert qc['trafficLights']['sim.emg.main']=='ok'
        assert qc['gaps']==[]
        assert manifest['status']=='completed'
    receipts[case]={'command':command,'cwd':str(REPO),'exit_code':proc.returncode,
                    'stdout':proc.stdout,'stderr':proc.stderr,'qc':qc,'job_manifest':manifest,
                    'raw_before':before,'raw_after':after,'same_input_bytes_as_baseline':True}
    if case=='closed_gap':
        shutil.copyfile(job/'reports/qc.html',OUT/'candidate-qc.html')
        shutil.copyfile(job/'reports/qc.json',OUT/'candidate-qc.json')
versions={}
for package in ['pytest','numpy','scipy','pandas','matplotlib','PyYAML','jsonschema','protobuf','mcap','pyarrow','PySide6']:
    try:
        versions[package]=importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        versions[package]=None
receipt={'python':sys.version,'versions':versions,'cases':receipts}
(OUT/'candidate-cli-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'versions':versions,'cases':{k:{'exit_code':v['exit_code'],'trafficLights':v['qc']['trafficLights'],'raw_preserved':v['raw_before']==v['raw_after'],'status':v['job_manifest']['status']} for k,v in receipts.items()}},indent=2))

