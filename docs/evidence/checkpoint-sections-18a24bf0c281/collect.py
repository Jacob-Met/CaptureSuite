# SPDX-License-Identifier: GPL-3.0-only
"""Collect completed native checkpoint receiving without modifying its sources."""
from __future__ import annotations
import csv, hashlib, json, shutil, tarfile, xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path("/Users/me/capturesuite-checkpoint-18a24bf0c281")
PACKET = ROOT / "packet"
PACKET.mkdir(exist_ok=False)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
def entry(path, relative):
    return {"path": relative, "bytes": path.stat().st_size, "sha256": sha(path)}
def inventory(directory):
    return [p for p in sorted(directory.rglob("*"))
            if p.is_file() and not p.is_symlink() and "mpl" not in p.relative_to(directory).parts]
def archive(target, files, base):
    with tarfile.open(target, "w:gz") as handle:
        for p in files:
            handle.add(p, arcname=p.relative_to(base).as_posix(), recursive=False)

source_custody = {}
summaries, cli = [], []
for label in ("baseline", "candidate", "regression"):
    directory = ROOT / "evidence" / label
    received = json.loads((directory / "receiving-run.json").read_text())
    if label != "regression":
        repo = ROOT / ("repository" if label == "baseline" else "candidate")
        for item in received["source_after"]:
            path = repo / item["path"]
            assert path.stat().st_size == item["worktree_bytes"], str(path)
            assert sha(path) == item["worktree_sha256"], str(path)
        source_custody[label] = received["source_after"]
        summary = {k: v for k, v in received.items() if k not in ("source_before", "source_after")}
        summary["authored_files_verified_after_all_tests"] = len(received["source_after"])
    else:
        summary = received
    suite = ET.parse(directory / "junit.xml").getroot().find("testsuite")
    summary["junit"] = dict(suite.attrib)
    summaries.append(summary)
    files = inventory(directory)
    manifest = [entry(p, p.relative_to(ROOT / "evidence").as_posix()) for p in files]
    target = PACKET / f"{label}-native.tar.gz"
    archive(target, files, ROOT / "evidence")
    write(PACKET / f"{label}-manifest.json", {"files": manifest})
    for receipt in files:
        if receipt.name != "receiving.json":
            continue
        r = json.loads(receipt.read_text())
        package = next(p for p in receipt.parent.iterdir() if p.is_dir() and p.suffix == ".mmsession")
        jobs = list((package / "processing/jobs").glob("*/job_manifest.json"))
        assert len(jobs) == 1
        job = jobs[0].parent
        params = json.loads((job / "params.json").read_text())
        manifest_doc = json.loads(jobs[0].read_text())
        feature_files = list(job.glob("features/imu/*/windows.csv"))
        table = None
        if feature_files:
            with feature_files[0].open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            table = {"rows": len(rows), "first": rows[0] if rows else None,
                     "last": rows[-1] if rows else None,
                     "csv_sha256": sha(feature_files[0]),
                     "parquet_sha256": sha(feature_files[0].with_suffix(".parquet"))}
        cli.append({"label": label, "case": r.get("case", "persisted-negative"),
                    "exit_code": r["returncode"], "expected_bounds": r.get("expected_bounds"),
                    "time_range": manifest_doc.get("timeRange"), "status": manifest_doc["status"],
                    "errors": manifest_doc.get("errors"), "params": params, "feature": table,
                    "raw_files": len(r["raw_before"]),
                    "raw_hashes_unchanged": r["raw_before"] == r["raw_after"],
                    "raw_before": r["raw_before"], "raw_after": r["raw_after"],
                    "full_receipt": receipt.relative_to(ROOT / "evidence").as_posix()})
assert set(x["path"] for x in source_custody["baseline"]) == set(x["path"] for x in source_custody["candidate"])
before = {x["path"]: x["worktree_sha256"] for x in source_custody["baseline"]}
after = {x["path"]: x["worktree_sha256"] for x in source_custody["candidate"]}
changed = [p for p in before if before[p] != after[p]]
assert changed == ["libs/python/capture_analysis/capture_analysis/windows.py"], changed
write(PACKET / "run-summary.json", summaries)
write(PACKET / "cli-comparison.json", cli)
write(PACKET / "source-custody-summary.json", {
    "verified_at": datetime.now(UTC).isoformat(),
    "authored_files_per_fixture": len(before),
    "only_differing_executed_source": changed[0],
    "candidate_sha256": after[changed[0]], "baseline_sha256": before[changed[0]],
    "raw_custody": "Complete before/after inventories are retained in each native archive.",
    "native_boundary": "Pinned main72c15 plus windows.py and frozen test. Documentation remains bound to local source4fcd0aa and is not an execution dependency.",
})
for label in ("baseline", "candidate"):
    job = ROOT / "evidence" / label / "pytest-tmp/test_real_cli_emits_the_select1/sections.mmsession/processing/jobs/checkpoint-receiving"
    for name, short in (("imu_sim.imu.upper_accel.png", "imu"), ("sync_dashboard.png", "sync")):
        target = PACKET / "figures" / f"{label}-{short}.png"
        target.parent.mkdir(exist_ok=True)
        shutil.copyfile(job / "figures" / name, target)
for name in ("receive.cjs", "regression.cjs", "prepare.cjs", "candidate-freeze.json",
             "environment-freeze.txt", "environment-check.txt", "environment-install.json",
             "source-transfer.json"):
    shutil.copyfile(ROOT / name, PACKET / name)
write(PACKET / "visual-receiving.json", {
    "method": "Direct inspection of actual unedited native Matplotlib PNGs through RDC.",
    "inspected": ["figures/candidate-imu.png", "figures/candidate-sync.png", "figures/baseline-imu.png"],
    "candidate_data": "The selected Reach section contains session2–5s, IMU magnitudes20–50; actual sync JSON retains31 exact session timestamps.",
    "baseline_data": "The old resolver selects5–5s because the following marker is tied; only the boundary sample remains.",
    "existing_presentation_limit": "Both current plot functions subtract the first retained timestamp but label the0–3s axis 'session time (s)'. This scope preserves those owned plot files. Actual window provenance and exported tables retain absolute session nanoseconds.",
    "coordination": "Reported to root for current plot/scope owners; no claim that this resolver repair fixes plot-origin labels.",
})
write(PACKET / "collection.json", {
    "collected_at": datetime.now(UTC).isoformat(), "source_commit": "4fcd0aa4319b6594af637af8644c187fcbff3cf5",
    "current_main": "72c15d6b623e217291a824e4e4808a385df896a9",
    "snapshot_policy": "All regular native receipt, JUnit, stdout, synthetic package raw files and derived outputs are retained. Reproducible Matplotlib caches, empty state directories and pytest convenience symlinks are excluded. Nothing in the original evidence or source was removed or edited.",
})
files = inventory(PACKET)
write(PACKET / "packet-manifest.json", {"files": [entry(p, p.relative_to(PACKET).as_posix()) for p in files]})
files = inventory(PACKET)
outer = ROOT / "checkpoint-evidence.tar.gz"
archive(outer, files, PACKET)
import base64
encoded = base64.b64encode(outer.read_bytes()).decode("ascii")
chunks = [encoded[i:i+60000] for i in range(0, len(encoded), 60000)]
Path(str(outer) + ".b64").write_text("\n".join(chunks) + "\n", encoding="ascii")
receipt = {"archive": str(outer), "bytes": outer.stat().st_size, "sha256": sha(outer),
           "chunks": len(chunks), "packet_files": len(files),
           "packet_bytes": sum(p.stat().st_size for p in files)}
write(ROOT / "checkpoint-evidence-transfer.json", receipt)
print(json.dumps(receipt))
