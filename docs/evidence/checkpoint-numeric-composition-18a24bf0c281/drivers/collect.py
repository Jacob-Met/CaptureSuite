# SPDX-License-Identifier: GPL-3.0-only
"""Freeze exact retained evidence; omit only disposable matplotlib caches and source checkouts."""
from pathlib import Path
import base64
from datetime import datetime, UTC
import gzip
import hashlib
import importlib.metadata
import io
import json
import platform
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parent
assert json.loads((ROOT / "final-assessment.json").read_text())["accepted"]
def sha(data):
    return hashlib.sha256(data).hexdigest()
def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], check=True, capture_output=True).stdout
(ROOT / "environment-current.txt").write_bytes(freeze)
write_json(ROOT / "runtime-identity.json", {
    "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
    "environment_freeze_sha256": sha(freeze),
    "packages": {name: importlib.metadata.version(name) for name in
                 ("numpy", "pandas", "pyarrow", "mcap", "protobuf", "matplotlib", "jsonschema")},
    "reuse": "existing isolated Python 3.12 environment; no install or dependency change",
    "source_receiving": "actual CLI sys.path and receipt-only import observer bind 49 current application modules per run"
})
paths = [
    ROOT / name for name in (
        "receive.py", "assess.py", "collect.py", "observer/sitecustomize.py", "frozen-windows.py",
        "source-intake.json", "fixture-definition.json", "summary.json", "final-assessment.json",
        "runner.log", "baseline-source-before.json", "baseline-source-after.json",
        "candidate-source-before.json", "candidate-source-after.json",
        "environment-current.txt", "runtime-identity.json")
]
for directory in ("baseline", "candidate", "raw-fixture.mmsession"):
    paths.extend(p for p in (ROOT / directory).rglob("*")
                 if p.is_file() and "matplotlib-cache" not in p.relative_to(ROOT).parts)
paths = sorted(set(paths))
entries = [{"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
            "sha256": sha(p.read_bytes())} for p in paths]
manifest = {"files": entries, "count": len(entries), "bytes": sum(x["bytes"] for x in entries),
            "excluded": ["two current source worktrees (all 812 exact Git blobs bound in before/after manifests)",
                         "disposable matplotlib caches only"],
            "raw_and_derived_outputs": "all retained fixture, original and candidate session inputs and job outputs"}
manifest_path = ROOT / "native-packet-manifest.json"
write_json(manifest_path, manifest)
archive = ROOT / "native-packet.tar.gz"
assert not archive.exists()
with archive.open("wb") as destination:
    with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as tar:
            for p in paths + [manifest_path]:
                data = p.read_bytes()
                item = tarfile.TarInfo(p.relative_to(ROOT).as_posix())
                item.size = len(data); item.mode = 0o644; item.mtime = 0
                tar.addfile(item, io.BytesIO(data))
with tarfile.open(archive, "r:gz") as tar:
    members = {m.name: m for m in tar.getmembers()}
    assert len(members) == len(entries) + 1
    for entry in entries:
        data = tar.extractfile(members[entry["path"]]).read()
        assert len(data) == entry["bytes"] and sha(data) == entry["sha256"]
encoded = base64.b64encode(archive.read_bytes()).decode()
(ROOT / "native-packet.b64").write_text("\n".join(encoded[i:i+60000] for i in range(0, len(encoded), 60000)) + "\n")
receipt = {"created_utc": datetime.now(UTC).isoformat(), "archive": str(archive),
           "bytes": archive.stat().st_size, "sha256": sha(archive.read_bytes()),
           "base64_chunks": (len(encoded)+59999)//60000, "payload_files": len(entries),
           "payload_bytes": sum(x["bytes"] for x in entries),
           "manifest_sha256": sha(manifest_path.read_bytes()), "all_payload_hashes_verified": True}
write_json(ROOT / "collection.json", receipt)
print(json.dumps(receipt, indent=2))
