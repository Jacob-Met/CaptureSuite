# SPDX-License-Identifier: GPL-3.0-only
"""Exercise the public features CLI with a source ID containing '.parquet'."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for package in ("capture_analysis", "capture_session", "capture_protocol"):
        sys.path.insert(0, str(repo / "libs/python" / package))
    fixture = runpy.run_path(str(repo / "tests/analysis/test_phase_b_features.py"))

    cases = []
    for label, source_id in (("ordinary", "sim.imu.upper"), ("source_token", "sim.imu.parquet")):
        package = fixture["_write_emg_imu_package"](out / f"{label}.mmsession")
        if source_id != "sim.imu.upper":
            for item in sorted(package.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                if item.is_file() and item.suffix in (".json", ".jsonl"):
                    text = item.read_text(encoding="utf-8")
                    changed = text.replace("sim.imu.upper", source_id)
                    if text != changed:
                        item.write_text(changed, encoding="utf-8")
                if "sim.imu.upper" in item.name:
                    item.rename(item.with_name(item.name.replace("sim.imu.upper", source_id)))

        inputs = {str(p.relative_to(package)): digest(p) for p in package.rglob("*") if p.is_file()}
        command = [
            sys.executable, str(repo / "tools/run_analysis.py"), "features", str(package),
            "--sources", source_id, "--start-ns", "0", "--end-ns", "500000000",
            "--overwrite-job-id", "feature-path-receiving",
        ]
        proc = subprocess.run(command, cwd=repo, capture_output=True, text=True, timeout=60)
        (out / f"{label}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (out / f"{label}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        job = package / "processing/jobs/feature-path-receiving"
        manifest = json.loads((job / "job_manifest.json").read_text(encoding="utf-8"))
        relative = f"features/imu/{source_id}/windows.parquet"
        csv_relative = f"features/imu/{source_id}/windows.csv"
        wanted = {relative, csv_relative}
        listed = {row["relativePath"]: row for row in manifest["outputs"]}
        registered = wanted <= set(listed)
        hashes_match = registered and all(
            listed[name]["sha256"] == digest(job / name)
            and listed[name]["bytes"] == (job / name).stat().st_size for name in wanted
        )
        table_equal = False
        if all((job / name).is_file() for name in wanted):
            import pandas as pd

            parquet = pd.read_parquet(job / relative)
            csv = pd.read_csv(job / csv_relative)
            pd.testing.assert_frame_equal(parquet, csv, check_dtype=False, check_exact=False)
            table_equal = True
        unchanged = all(digest(package / name) == sha for name, sha in inputs.items())
        case = {
            "case": label, "source_id": source_id, "returncode": proc.returncode,
            "status": manifest["status"], "warnings": manifest["warnings"],
            "input_file_count": len(inputs), "inputs_unchanged": unchanged,
            "parquet_exists": (job / relative).is_file(),
            "csv_exists": (job / csv_relative).is_file(),
            "both_registered": registered, "hashes_match": hashes_match,
            "tables_equal": table_equal,
            "parquet_sha256": digest(job / relative) if (job / relative).is_file() else None,
        }
        cases.append(case)
    result = {
        "python": sys.version,
        "writer_sha256": digest(repo / "libs/python/capture_analysis/capture_analysis/features/io.py"),
        "cases": cases,
        "accepted": all(
            c["returncode"] == 0 and c["inputs_unchanged"] and c["both_registered"]
            and c["hashes_match"] and c["tables_equal"] for c in cases
        ),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
