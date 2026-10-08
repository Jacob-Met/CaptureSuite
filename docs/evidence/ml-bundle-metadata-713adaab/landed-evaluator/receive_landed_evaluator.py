# SPDX-License-Identifier: GPL-3.0-only
"""Receive the newly landed external evaluator against the reviewed metadata."""
from pathlib import Path
import os, sys, subprocess, json, hashlib, datetime, xml.etree.ElementTree as ET
ROOT=Path("/Users/me/Developer/capturesuite-ml-bundle-metadata-20261008-713adaab")
E=ROOT/"out/ml-bundle-metadata-evidence"
out=E/"landed-evaluator-receiving"
out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
scope="tests/analysis/test_external_predictions.py::test_real_pose_kinematics_bundle_to_external_eval"
paths=subprocess.check_output(["git","ls-files","libs/python/capture_analysis","libs/python/capture_session","libs/python/capture_protocol","libs/python/capture_worker","tests/analysis","tools/run_analysis.py","schemas"],cwd=ROOT,text=True).splitlines()
inputs=[n for n in paths if (ROOT/n).is_file()]
before={n:sha(ROOT/n) for n in inputs}
assert before["libs/python/capture_analysis/capture_analysis/ml_bundle/job.py"]=="38b7161f081ef038e6ce464dd3b82ca2b49f775ad8988010243743274d6fc5e6"
assert before["tests/analysis/test_ml_bundle_metadata.py"]=="b2104dd43f464629e284fe946126a65fa5423531f67b9fd165b702f888cd799d"
assert before["libs/python/capture_analysis/capture_analysis/eval/predictions.py"]=="decff22c1e2e661a3ce21679db68b667ea44fa5b18df8501204d7d23161cc906"
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=os.pathsep.join([str(ROOT),*[str(ROOT/"libs/python"/n) for n in ("capture_analysis","capture_session","capture_protocol","capture_worker")]]),MPLBACKEND="Agg",MPLCONFIGDIR="/Users/me/Developer/capturesuite-analysis-provenance-20261008/out/analysis-provenance-evidence/matplotlib-cache")
py="/Users/me/Developer/capturesuite-analysis-provenance-20261008/.venv-analysis/bin/python"
check=subprocess.run([py,"-B","-c","import sys,json,capture_analysis.ml_bundle.job,capture_analysis.eval.predictions;print(json.dumps({'python':sys.version,'producer':capture_analysis.ml_bundle.job.__file__,'evaluator':capture_analysis.eval.predictions.__file__}))"],cwd=ROOT,env=env,capture_output=True)
assert check.returncode==0,check.stderr
resolved=json.loads(check.stdout)
assert Path(resolved["producer"]).is_relative_to(ROOT) and Path(resolved["evaluator"]).is_relative_to(ROOT)
command=[py,"-B","-m","pytest",scope,"-q","-p","no:cacheprovider","--basetemp",str(out/"fixtures"),"--junitxml",str(out/"pytest.xml")]
with (out/"pytest.log").open("xb") as f:
    r=subprocess.run(command,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT)
cases=list(ET.parse(out/"pytest.xml").getroot().iter("testcase"))
counts={"tests":len(cases),"passed":sum(all(c.find(k) is None for k in ("failure","error","skipped")) for c in cases),"failures":sum(c.find("failure") is not None for c in cases),"errors":sum(c.find("error") is not None for c in cases),"skipped":sum(c.find("skipped") is not None for c in cases)}
after={n:sha(ROOT/n) for n in inputs}
assert before==after
inventory=[]
for manifest in (out/"fixtures").rglob("job_manifest.json"):
    d=json.loads(manifest.read_bytes())
    for row in d["outputs"]:
        path=manifest.parent/row["relativePath"]
        assert path.is_file() and path.stat().st_size==row["bytes"] and sha(path)==row["sha256"],path
    inventory.append({"path":str(manifest.relative_to(out)),"status":d.get("status"),"outputs":len(d["outputs"]),"sha256":sha(manifest)})
receipt={"schema":"capture.ml_bundle_metadata.landed_evaluator_receiving/1","recorded_at":datetime.datetime.now(datetime.UTC).isoformat(),"main_commit":"58157fdc1b83a12bb4856ef14b0498cf524a1087","reviewed_native_commit":"1e9727201face54a1a70551dbcc8df50a70a3f70","tested_staged_tree":subprocess.check_output(["git","write-tree"],cwd=ROOT,text=True).strip(),"command":command,"exit_code":r.returncode,"counts":counts,"runtime":resolved,"source_before":before,"source_after":after,"inputs_unchanged":True,"final_inventories":inventory,"junit_sha256":sha(out/"pytest.xml"),"log_sha256":sha(out/"pytest.log"),"runner_sha256":sha(Path(__file__)),"limits":"One existing actual pose/kinematics/bundle-to-external-eval receiver on macOS Python 3.12.8; supported Windows hosted CI is a separate gate. No evaluator or numeric source changes."}
p=out/"receipt.json";p.write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps({"exit_code":r.returncode,"counts":counts,"inputs_unchanged":len(inputs),"finalized_inventories":len(inventory),"receipt_sha256":sha(p),"junit_sha256":receipt["junit_sha256"],"log_sha256":receipt["log_sha256"]}))
sys.exit(r.returncode)
