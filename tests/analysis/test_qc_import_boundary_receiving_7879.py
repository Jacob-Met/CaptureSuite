# SPDX-License-Identifier: GPL-3.0-only
"""Fresh-process receiving of QC import conservation and the existing job API.

This is separate from the frozen multi-package CLI consumer. It never runs a
job, relocates a runtime cache, or replaces a native module with a test stub.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ALL = [
    "__version__", "JobParams", "JobResult", "QcReport", "collect_qc",
    "discover_streams", "hash_sources_tree", "run",
]
STATE_FOLDERS = [
    ("LOCALAPPDATA", "local"), ("APPDATA", "roaming"),
    ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
    ("XDG_CACHE_HOME", "cache"),
]
PROBE = r"""
import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
phase = sys.argv[2]
names = [
    "capture_analysis", "capture_analysis.jobs", "capture_analysis.pipeline",
    "capture_analysis.plots.style", "matplotlib", "matplotlib.pyplot", "numpy",
]
record = {
    "phase": phase, "python": sys.version, "executable": sys.executable,
    "modulesBefore": [name for name in names if name in sys.modules],
}
import capture_analysis as api

record["apiFile"] = str(Path(api.__file__).resolve())
record["all"] = list(api.__all__)
record["visibleBeforeJobAccess"] = [name for name in api.__all__ if name in dir(api)]
if phase == "qc":
    from capture_analysis.discover import discover_streams
    from capture_analysis.qc import QcReport, collect_qc
    from capture_analysis.report_html import render_qc_html

    review_module = importlib.import_module("capture_analysis.qc_packages")
    record["qcIdentity"] = {
        "QcReport": api.QcReport is QcReport,
        "collect_qc": api.collect_qc is collect_qc,
        "discover_streams": api.discover_streams is discover_streams,
    }
    record["rendererCallable"] = callable(render_qc_html)
    record["reviewModuleFile"] = str(Path(review_module.__file__).resolve())
elif phase == "job-api":
    from capture_analysis import JobParams, JobResult, hash_sources_tree, run

    native_jobs = importlib.import_module("capture_analysis.jobs")
    imported = {
        "JobParams": JobParams, "JobResult": JobResult,
        "hash_sources_tree": hash_sources_tree, "run": run,
    }
    record["jobIdentity"] = {
        name: value is getattr(native_jobs, name) and value is getattr(api, name)
        and getattr(api, name) is getattr(api, name)
        for name, value in imported.items()
    }
    record["signatures"] = {
        name: str(inspect.signature(value)) for name, value in imported.items()
    }
    record["nativeSignatures"] = {
        name: str(inspect.signature(getattr(native_jobs, name))) for name in imported
    }
    namespace = {}
    exec("from capture_analysis import *", namespace)
    record["starNames"] = sorted(set(namespace) - {"__builtins__"})
    record["starIdentity"] = {
        name: namespace[name] is getattr(api, name) for name in api.__all__
    }
    record["defaultParamsEqual"] = (
        JobParams().to_dict() == native_jobs.JobParams().to_dict()
    )
    record["visibleAfterJobAccess"] = [name for name in api.__all__ if name in dir(api)]
    try:
        getattr(api, "qc_receiver_missing_attribute_7879")
    except AttributeError:
        record["unknownAttributeRaisesAttributeError"] = True
    else:
        record["unknownAttributeRaisesAttributeError"] = False
    record["nativeJobsFile"] = str(Path(native_jobs.__file__).resolve())
else:
    raise ValueError("Unknown independent receiving phase")
record["modulesAfter"] = [name for name in names if name in sys.modules]
record["source"] = {}
for relative in [
    "libs/python/capture_analysis/capture_analysis/__init__.py",
    "libs/python/capture_analysis/capture_analysis/qc.py",
    "libs/python/capture_analysis/capture_analysis/qc_packages.py",
    "libs/python/capture_analysis/capture_analysis/jobs.py",
    "libs/python/capture_analysis/capture_analysis/pipeline.py",
    "libs/python/capture_analysis/capture_analysis/plots/style.py",
]:
    raw = (root / relative).read_bytes()
    record["source"][relative] = {
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    }
print("CAPTURE_QC_IMPORT_CHILD " + json.dumps(record, sort_keys=True), flush=True)
"""


def _inventory(root: Path) -> dict[str, Any]:
    directories = ["."]
    files = {}
    assert root.is_dir() and not root.is_symlink()
    for path in sorted(root.rglob("*")):
        assert not path.is_symlink(), f"Unexpected link in owned application state: {path}"
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(relative)
        else:
            assert path.is_file(), f"Unexpected owned state entry: {relative}"
            raw = path.read_bytes()
            files[relative] = {
                "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            }
    return {"directories": directories, "files": files}


def test_qc_import_boundary_receiving_7879(tmp_path: Path, capsys: Any) -> None:
    """One fresh interpreter and new application-state root for each phase."""
    observations = {}
    source_before = Path(__file__).read_bytes()
    probe_hash = hashlib.sha256(PROBE.encode("utf-8")).hexdigest()
    for phase in ("qc", "job-api"):
        state = tmp_path / phase
        state.mkdir()
        env = dict(os.environ)
        for name, suffix in STATE_FOLDERS:
            folder = state / suffix
            folder.mkdir()
            env[name] = str(folder)
        env["CAPTURE_TEST_STATE"] = str(state)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        before = _inventory(state)
        argv = [sys.executable, "-c", PROBE, str(ROOT), phase]
        completed = subprocess.run(
            argv, cwd=tmp_path, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="strict", timeout=90, check=False,
        )
        after = _inventory(state)
        child_lines = [
            line.removeprefix("CAPTURE_QC_IMPORT_CHILD ")
            for line in completed.stdout.splitlines()
            if line.startswith("CAPTURE_QC_IMPORT_CHILD ")
        ]
        child = json.loads(child_lines[0]) if len(child_lines) == 1 else None
        observation = {
            "schema": "capture.qc-import-boundary-receiving/1", "phase": phase,
            "command": {
                "executable": sys.executable, "mode": "-c",
                "probeSha256": probe_hash, "arguments": [str(ROOT), phase],
                "cwd": str(tmp_path),
            },
            "stateRoot": str(state), "stateBefore": before, "stateAfter": after,
            "stateUnchanged": before == after, "exit": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr, "child": child,
            "stateMeaning": (
                "Only this fresh test's relative file/directory/size/hash inventory; "
                "no application-file contents or unrelated environment are captured."
            ),
        }
        observations[phase] = observation
        raw = json.dumps(observation, sort_keys=True)
        assert len(raw.encode("utf-8")) <= 128 * 1024, "Bounded authored import observation"
        # Visible even for a passing test in the unchanged maintained pytest route.
        # Emit both actual phases before asserting the QC state boundary.
        with capsys.disabled():
            print("CAPTURE_QC_IMPORT_RECEIVING " + raw, flush=True)

    assert Path(__file__).read_bytes() == source_before
    for phase, observation in observations.items():
        assert observation["exit"] == 0, observation["stdout"] + observation["stderr"]
        child = observation["child"]
        assert child is not None, f"No unique completed native observation for {phase}"
        assert child["modulesBefore"] == [], "Each phase must start before native analysis import"
        assert child["all"] == EXPECTED_ALL
        assert child["visibleBeforeJobAccess"] == EXPECTED_ALL
        assert Path(child["apiFile"]) == (
            ROOT / "libs/python/capture_analysis/capture_analysis/__init__.py"
        ).resolve()

    qc = observations["qc"]
    assert qc["stateUnchanged"], "QC imports changed fresh isolated application state"
    assert all(qc["child"]["qcIdentity"].values())
    assert qc["child"]["rendererCallable"]
    assert Path(qc["child"]["reviewModuleFile"]) == (
        ROOT / "libs/python/capture_analysis/capture_analysis/qc_packages.py"
    ).resolve()

    api = observations["job-api"]["child"]
    assert all(api["jobIdentity"].values())
    assert api["signatures"] == api["nativeSignatures"]
    assert api["starNames"] == sorted(EXPECTED_ALL)
    assert all(api["starIdentity"].values())
    assert api["defaultParamsEqual"]
    assert api["visibleAfterJobAccess"] == EXPECTED_ALL
    assert api["unknownAttributeRaisesAttributeError"]
    assert Path(api["nativeJobsFile"]) == (
        ROOT / "libs/python/capture_analysis/capture_analysis/jobs.py"
    ).resolve()
