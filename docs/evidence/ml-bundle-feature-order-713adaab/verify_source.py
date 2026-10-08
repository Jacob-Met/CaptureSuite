# SPDX-License-Identifier: GPL-3.0-only
"""Verify the bounded source change and its scoped style gates."""
from pathlib import Path
import subprocess
import hashlib
import json
import shutil
root=Path(__file__).resolve().parent.parent
source=root/"source"
target=source/"libs/python/capture_analysis/capture_analysis/ml_bundle/job.py"
old=(root/"evidence/baseline-producer.py").read_bytes()
added=b'        # Nearest lookup requires timestamp order; keep each value with its row.\n        if np.any(t_ns[1:] < t_ns[:-1]):\n            order = np.argsort(t_ns, kind="stable")\n            t_ns, values = t_ns[order], values[order]\n'
record={"source_preservation":target.read_bytes().replace(added,b"",1)==old,
"producer_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
"free_bytes":shutil.disk_usage(root).free,
"prior_wrapper":"One direct read/style tool process exited1 with no captured stdout/stderr. Its reason is unconfirmed; this file-backed check is the recorded authority.",
"checks":[]}
for args in [
["-m","ruff","check","libs/python/capture_analysis/capture_analysis/ml_bundle/job.py","tests/analysis/test_ml_bundle_feature_order.py"],
["-m","ruff","format","--check","tests/analysis/test_ml_bundle_feature_order.py"],
]:
    run=subprocess.run([str(root/"environment/venv/bin/python"),*args],cwd=source,capture_output=True,text=True)
    record["checks"].append({"args":args,"exit":run.returncode,"stdout":run.stdout,"stderr":run.stderr})
out=root/"evidence/source-verification.json"
out.write_text(json.dumps(record,indent=2)+"\n")
print(json.dumps(record),flush=True)
assert record["source_preservation"]
assert all(check["exit"]==0 for check in record["checks"])
