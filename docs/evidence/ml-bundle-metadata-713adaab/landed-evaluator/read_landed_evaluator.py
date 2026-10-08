# SPDX-License-Identifier: GPL-3.0-only
"""Read retained results after the original optional inventory diagnostic failed."""
from pathlib import Path
import sys, subprocess, json, hashlib, datetime, xml.etree.ElementTree as ET
ROOT=Path("/Users/me/Developer/capturesuite-ml-bundle-metadata-20261008-713adaab")
E=ROOT/"out/ml-bundle-metadata-evidence"
out=E/"landed-evaluator-receiving"
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
g=lambda *a:subprocess.check_output(["git",*a],cwd=ROOT)
cases=list(ET.parse(out/"pytest.xml").getroot().iter("testcase"))
counts={"tests":len(cases),"passed":sum(all(c.find(k) is None for k in ("failure","error","skipped")) for c in cases),"failures":sum(c.find("failure") is not None for c in cases),"errors":sum(c.find("error") is not None for c in cases),"skipped":sum(c.find("skipped") is not None for c in cases)}
assert counts=={"tests":1,"passed":1,"failures":0,"errors":0,"skipped":0}
paths=g("ls-files","libs/python/capture_analysis","libs/python/capture_session","libs/python/capture_protocol","libs/python/capture_worker","tests/analysis","tools/run_analysis.py","schemas").decode().splitlines()
source_after={n:sha(ROOT/n) for n in paths if (ROOT/n).is_file()}
assert all((ROOT/n).read_bytes()==g("show",":"+n) for n in source_after)
inventories=[]; excluded=[]
for manifest in sorted((out/"fixtures").rglob("job_manifest.json")):
    d=json.loads(manifest.read_bytes())
    if "outputs" not in d:
        assert manifest.parent.name=="feat-radar" and set(d)=={"schemaId","jobId","status","command"}
        excluded.append({"path":str(manifest.relative_to(out)),"sha256":sha(manifest),"reason":"Pre-existing test-authored feature input stub, not a job emitted by this receiving."})
        continue
    entries=[]
    for row in d["outputs"]:
        path=manifest.parent/row["relativePath"]
        assert path.is_file() and path.stat().st_size==row["bytes"] and sha(path)==row["sha256"],path
        entries.append({"relativePath":row["relativePath"],"bytes":row["bytes"],"sha256":row["sha256"]})
    inventories.append({"path":str(manifest.relative_to(out)),"sha256":sha(manifest),"status":d["status"],"outputs":entries})
assert len(inventories)==4 and len(excluded)==1
receipt={"schema":"capture.ml_bundle_metadata.landed_evaluator_receiving/1","recorded_at":datetime.datetime.now(datetime.UTC).isoformat(),"received_main":"58157fdc1b83a12bb4856ef14b0498cf524a1087","reviewed_native_commit":"1e9727201face54a1a70551dbcc8df50a70a3f70","tested_staged_tree":"38015f3dec35025daea4e84d198a00e22cae5327","test":"tests/analysis/test_external_predictions.py::test_real_pose_kinematics_bundle_to_external_eval","counts":counts,"runtime_readback":sys.version,"pytest_exit_code":None,"pytest_exit_code_reason":"The original wrapper did not persist this value before its later inventory diagnostic exception; the raw JUnit and pytest summary both record the one passing case.","original_wrapper_exit_code":1,"original_wrapper_failure":{"exception":"KeyError: 'outputs'","at":"receive_landed_evaluator.py line 33","phase":"Optional post-test inventory enumeration of a pre-existing feature input stub","pytest_already_completed":True,"source_before_after_equality_assertion_completed_before_exception":True,"original_maps_persisted":False},"readback_corrections":[{"exception":"AssertionError: completed_with_warnings","phase":"First read-only inventory recovery incorrectly assumed the successful status spelling was success; no pytest replay or source write occurred. The corrected readback records actual statuses and checks every output byte."}],"source_after_recovery":source_after,"source_after_matches_tested_index":True,"final_inventories":inventories,"excluded_fixture_manifests":excluded,"junit_sha256":sha(out/"pytest.xml"),"log_sha256":sha(out/"pytest.log"),"original_driver_sha256":sha(E/"receive_landed_evaluator.py"),"recovery_driver_sha256":hashlib.sha256(sys.argv[1].encode()).hexdigest(),"limits":"This recovery only reads preserved source, JUnit, logs and artifacts. It does not replay pytest or producer/evaluator code. Supported Windows CI remains a separate gate."}
g("diff","--cached","--exit-code","38015f3dec35025daea4e84d198a00e22cae5327")
print(json.dumps({"receipt":receipt,"receipt_content":json.dumps(receipt,indent=2)+"\n"}))
print(json.dumps({"counts":counts,"source_files_match_tested_index":len(source_after),"finalized_job_inventories":len(inventories),"excluded_authored_stubs":len(excluded),"junit_sha256":receipt["junit_sha256"],"log_sha256":receipt["log_sha256"]}))
