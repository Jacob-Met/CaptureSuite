# SPDX-License-Identifier: GPL-3.0-only
"""Freeze exact native receiving files into a small verified archive."""
from pathlib import Path
import gzip
import hashlib
import io
import json
import tarfile

root = Path(__file__).resolve().parent.parent
evidence = root / "evidence"
destination = root / "source/docs/evidence/ml-bundle-feature-order-713adaab"
destination.mkdir(parents=True, exist_ok=True)
def sha(data):
    return hashlib.sha256(data).hexdigest()
members = {}
for name in [
    "receive_feature_order.py", "receive_related.py", "read_paired_artifacts.py",
    "baseline-producer.py", "candidate-producer.py", "paired-test.py",
    "test_feature_order_initial.py", "initial-receiver-correction.json",
    "runtime.patch", "documentation.patch", "paired-artifacts.json",
]:
    members["evidence/" + name] = (evidence / name).read_bytes()
for stage in ["baseline", "baseline-final", "candidate", "related"]:
    for name in ["receipt.json","process.json","pytest.xml","pytest.log",
                 "source-before.json","source-after.json"]:
        members[f"evidence/{stage}/{name}"] = (evidence/stage/name).read_bytes()
    if stage != "related":
        for path in sorted((evidence/stage/"pytest-temp").rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(evidence).as_posix()
                members["evidence/" + relative] = path.read_bytes()
for name in ["runtime-receipt.json","dependency-receipt.json",
             "requirements-receiver.txt","runtime.sha256","dependencies.log"]:
    members["environment/"+name]=(root/"environment"/name).read_bytes()
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode="w") as archive:
    for name,data in sorted(members.items()):
        info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
        archive.addfile(info,io.BytesIO(data))
packed=gzip.compress(buffer.getvalue(),mtime=0)
target=destination/"receiving.tar.gz"
target.write_bytes(packed)
with tarfile.open(target,"r:gz") as archive:
    restored={row.name:archive.extractfile(row).read() for row in archive.getmembers()}
assert restored==members
manifest={
    "schema":"capturesuite.ml_feature_order_capsule/1","issue":86,
    "base_commit":"11cc78297d8d214407aea693548af4de855d61da",
    "original_producer_sha256":"38b7161f081ef038e6ce464dd3b82ca2b49f775ad8988010243743274d6fc5e6",
    "candidate_producer_sha256":"ed67d94ded834d63599797bbd8efb7b26f125bd216f52bcb7f01febb928922ce",
    "final_test_sha256":"7a5e226afb9c0f49eadf6d4c25b8bc22575f1fdd04afdac854cf8aa4adee58be",
    "archive":{"path":target.name,"bytes":len(packed),"sha256":sha(packed),
               "members":len(members),"expanded_file_bytes":sum(map(len,members.values())),
               "all_members_reopened_and_verified":True},
    "files":[{"path":name,"bytes":len(data),"sha256":sha(data)}
             for name,data in sorted(members.items())],
    "limits":["Archive contains the complete initial/final paired test artifacts. Related inherited test outputs remain in native custody; their complete process/log/JUnit/source maps and artifact-inventory receipt are included.",
              "Private Linux Python3.12.10 runtime only; no Windows, physical sensor, installed application or scientific-validity qualification.",
              "Original mixed negative with four schema-invalid 2ns windows is retained separately from corrected final17 test receiving."],
}
output=destination/"manifest.json"
output.write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps({"archive":str(target),"bytes":len(packed),"sha256":sha(packed),
"members":len(members),"expanded_bytes":manifest["archive"]["expanded_file_bytes"],
"manifest_sha256":sha(output.read_bytes())}))
