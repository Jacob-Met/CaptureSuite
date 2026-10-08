# SPDX-License-Identifier: GPL-3.0-only
"""Read-only qualification of the two already completed native CLI outputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

original = json.loads((ROOT / "summary.json").read_text())
result = {
    "kind": "read-only assessment of retained native output; no application rerun",
    "receiving_source": original["source_commit"],
    "receiving_tree": original["source_tree"],
    "original_summary_sha256": sha(ROOT / "summary.json"),
    "original_receiver_sha256": sha(ROOT / "receive.py"),
    "observer_sha256": sha(ROOT / "observer/sitecustomize.py"),
    "known_manifest_self_entry": {
        "reason": "jobs.py records its preliminary manifest bytes/hash before adding the self-entry and rewriting.",
        "maintained_receiver": "tests/analysis/test_numeric_cli_receiving.py::assert_artifacts, lines 292–296",
        "source_blob": "9d1bc393b23ed30e52cab2e6f65e8ac7a96018d8",
        "jobs_blob": "7badee5cdf5a4b30a283e0dcbb2c5d85fb787489",
        "scope": "Verify every non-self output against its declared bytes/hash; record the actual final manifest hash separately."
    },
    "runs": [],
}
for prior in original["runs"]:
    variant = prior["variant"]
    case = ROOT / variant
    source = ROOT / (variant + "-source")
    job = case / "numeric.mmsession/processing/jobs/numeric-checkpoint"
    manifest = json.loads((job / "job_manifest.json").read_text())
    outputs = []
    preliminary = []
    for row in manifest["outputs"]:
        p = job / row["relativePath"]
        actual = {"bytes": p.stat().st_size, "sha256": sha(p)}
        measured = {"relativePath": row["relativePath"], "kind": row["kind"],
                    "declared": {"bytes": row["bytes"], "sha256": row["sha256"]},
                    "actual": actual}
        if row["kind"] == "manifest":
            assert row["relativePath"] == "job_manifest.json"
            preliminary.append(measured)
        else:
            measured["matches"] = actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"]
            outputs.append(measured)
    assert len(preliminary) == 1
    recorded_checks = [c for c in prior["checks"]
                       if c["name"] != "reported artifact sizes and hashes bind actual outputs"]
    corrected_checks = recorded_checks + [{
        "name": "every non-self output matches its recorded bytes/hash",
        "passed": all(x["matches"] for x in outputs),
        "actual": {"non_self_outputs": len(outputs), "preliminary_manifest_entries": len(preliminary)}}]
    before = json.loads((ROOT / (variant + "-source-before.json")).read_text())
    after = json.loads((ROOT / (variant + "-source-after.json")).read_text())
    assert before == after and len(after) == 812
    assert all(blob((source / row["path"]).read_bytes()) == row["executed_git_blob"] for row in after)
    imports = json.loads((case / "imported-source.json").read_text())
    assert len(imports) == 49
    assert all(sha(source / row["path"]) == row["sha256"] for row in imports)
    assert manifest["sourcesSelected"] == ["sampler.section"]
    assert manifest["timeRange"]["checkpointIds"] == ["trial"]
    assert manifest["timeRange"]["mode"] == "cp:trial"
    assert [manifest["timeRange"]["startSessionNs"], manifest["timeRange"]["endSessionNs"]] == prior["window"]
    result["runs"].append({
        "variant": variant, "actual_cli_exit": prior["exit_code"],
        "recorded_cli_seconds": prior["seconds"], "timeRange": manifest["timeRange"],
        "sourcesSelected": manifest["sourcesSelected"], "modalities": manifest["modalities"],
        "native_original_checks": {"passed": prior["passed"], "failed": prior["failed"]},
        "original_false_assumption": "all outputs have final self-consistent hashes, including the manifest itself",
        "assessed_checks": corrected_checks, "passed": sum(c["passed"] for c in corrected_checks),
        "failed": sum(not c["passed"] for c in corrected_checks),
        "non_self_outputs": outputs, "preliminary_self_entry": preliminary,
        "actual_manifest_sha256": sha(job / "job_manifest.json"),
        "source_modules": len(imports), "source_files_reverified": len(after),
        "raw_files": len(prior["raw_before"]), "raw_preserved": prior["raw_before"] == prior["raw_after"],
        "feature_rows": len(prior["feature_rows"]),
        "retained_samples": len(prior["retained_series"]["t_ns"]),
        "sample_start_ns": prior["retained_series"]["t_ns"][0],
        "sample_end_ns": prior["retained_series"]["t_ns"][-1],
        "means": [row["index_mean"] for row in prior["feature_rows"]],
    })
result["accepted"] = (result["runs"][0]["passed"], result["runs"][0]["failed"],
                      result["runs"][1]["passed"], result["runs"][1]["failed"]) == (8, 5, 13, 0)
assert result["accepted"]
(ROOT / "final-assessment.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"accepted": result["accepted"], "runs": [
    {key: run[key] for key in ("variant", "actual_cli_exit", "passed", "failed", "feature_rows",
                               "retained_samples", "source_modules", "source_files_reverified")}
    | {"non_self_outputs": len(run["non_self_outputs"])} for run in result["runs"]]}, indent=2))
