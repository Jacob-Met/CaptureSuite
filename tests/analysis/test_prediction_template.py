# SPDX-License-Identifier: GPL-3.0-only
"""Exact external-prediction templates, maintained consumer admission and publication."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from capture_analysis.eval import predictions
from capture_analysis.eval.template import prepare_prediction_template

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ["theta_elbow_flex_L", "omega_elbow_flex_L"]
TIMES = [2**53 + 1, -1, 2**63 - 1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    return {str(p.relative_to(root)): sha(p) for p in root.rglob("*") if p.is_file()}


def seed(tmp_path):
    package = tmp_path / "session.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", package)
    session_manifest = package / "manifest.json"
    selected = json.loads(session_manifest.read_bytes())
    selected["sessionId"] = "template-root-reference-session"
    session_manifest.write_text(json.dumps(selected) + "\n", encoding="utf-8")
    bundle = package / "processing/jobs/bundle/ml_bundle"
    bundle.mkdir(parents=True)
    frame = pd.DataFrame({
        "window_id": ["w2", "w0", "w9"],
        "session_time_ns": pd.Series(TIMES, dtype="int64"),
        "valid_mask": [True, False, True],
        TARGETS[0]: [1.25, 9.5, -17.0],
        TARGETS[1]: [7.5, -2.75, 0.125],
    })
    frame.to_parquet(bundle / "windows.parquet", index=False)
    manifest = {
        "schemaId": "capture.ml_bundle/1", "bundleVersion": "1.0.0",
        "sessionIds": ["template-root-reference-session"],
        "sourceJobIds": {"kinematics": "kin", "features": "feat"},
        "analysisGrids": [{"gridId": "fixture", "rateHz": 20,
                          "method": "fixture", "sourceStreams": ["fixture"]}],
        "window": {"windowSec": 1, "hopSec": .05, "targetTime": "center"},
        "targetColumns": list(TARGETS),
        "inputFeatures": {"kind": "motion_energy"},
        "normalization": {"input": "none", "target": "none"},
        "sha256": {"windows.parquet": sha(bundle / "windows.parquet"),
                   "manifest.json": "0" * 64},
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                        encoding="utf-8")
    return package, bundle, tmp_path / "predictions.json"


def write_frame(bundle, frame):
    frame.to_parquet(bundle / "windows.parquet", index=False)
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest["sha256"]["windows.parquet"] = sha(bundle / "windows.parquet")
    path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")


def refuse(package, output, *, bundle_id="bundle", model_id="model"):
    before = files(package)
    with pytest.raises((ValueError, TypeError, FileNotFoundError)):
        prepare_prediction_template(package, bundle_id, model_id, output)
    assert not os.path.lexists(output)
    assert files(package) == before
    assert sorted(p.name for p in output.parent.iterdir()) == ["session.mmsession"]


def test_exact_order_int64_nulls_label_digests_and_determinism(tmp_path):
    package, bundle, output = seed(tmp_path)
    before = files(package)
    label = "  external-model Δ  "
    prepare_prediction_template(package, "bundle", label, output)
    doc = json.loads(output.read_bytes())
    assert set(doc) == {"schemaId", "modelId", "windowsSha256",
                        "manifestSha256", "predictions"}
    assert doc["schemaId"] == "capture.eval_predictions/1"
    assert doc["modelId"] == label
    assert doc["windowsSha256"] == sha(bundle / "windows.parquet")
    assert doc["manifestSha256"] == sha(bundle / "manifest.json") != "0" * 64
    assert [r["window_id"] for r in doc["predictions"]] == ["w2", "w0", "w9"]
    assert [r["session_time_ns"] for r in doc["predictions"]] == TIMES
    assert all(type(r["session_time_ns"]) is int for r in doc["predictions"])
    assert all(r["values"] == dict.fromkeys(TARGETS) for r in doc["predictions"])
    assert all(set(r) == {"window_id", "session_time_ns", "values"}
               for r in doc["predictions"])
    import jsonschema
    jsonschema.validate(doc, json.loads(
        (ROOT / "schemas/eval/predictions.schema.json").read_bytes()))
    other = output.with_name("again.json")
    prepare_prediction_template(package, "bundle", label, other)
    assert output.read_bytes() == other.read_bytes()
    assert files(package) == before
    assert set(p.name for p in tmp_path.iterdir()) == {
        "session.mmsession", "predictions.json", "again.json"}


def test_final_manifest_whitespace_controls_the_digest(tmp_path):
    package, bundle, output = seed(tmp_path)
    path = bundle / "manifest.json"
    path.write_bytes(path.read_bytes() + b" \n")
    prepare_prediction_template(package, "bundle", "model", output)
    assert json.loads(output.read_bytes())["manifestSha256"] == sha(path)


@pytest.mark.parametrize("change", ["wrong-session", "wrong-schema", "bad-digest",
                                    "duplicate-target", "unknown-target", "empty-target"])
def test_manifest_admission_is_preserved(tmp_path, change):
    package, bundle, output = seed(tmp_path)
    path = bundle / "manifest.json"
    doc = json.loads(path.read_bytes())
    if change == "wrong-session":
        doc["sessionIds"] = ["different-package"]
    elif change == "wrong-schema":
        doc["schemaId"] = "foreign/1"
    elif change == "bad-digest":
        doc["sha256"]["windows.parquet"] = "f" * 64
    elif change == "duplicate-target":
        doc["targetColumns"] = [TARGETS[0], TARGETS[0]]
    elif change == "unknown-target":
        doc["targetColumns"] = ["unknown"]
    else:
        doc["targetColumns"] = []
    path.write_text(json.dumps(doc), encoding="utf-8")
    refuse(package, output)


@pytest.mark.parametrize("content", [b"not-json", b"\xff",
    b'{"schemaId":"capture.ml_bundle/1","schemaId":"other"}',
    b'{"schemaId":"capture.ml_bundle/1","bad":NaN}'])
def test_malformed_manifest_is_not_published(tmp_path, content):
    package, bundle, output = seed(tmp_path)
    (bundle / "manifest.json").write_bytes(content)
    refuse(package, output)


@pytest.mark.parametrize("change", ["duplicate-id", "empty-id", "numeric-id",
    "empty", "missing-time", "float-time", "bool-time", "null-time",
    "out-of-int64", "missing-target", "bool-target", "string-target",
    "missing-validity", "string-validity", "null-validity"])
def test_window_and_target_admission_is_preserved(tmp_path, change):
    package, bundle, output = seed(tmp_path)
    frame = pd.read_parquet(bundle / "windows.parquet")
    if change == "duplicate-id":
        frame["window_id"] = ["w2", "w2", "w9"]
    elif change == "empty-id":
        frame["window_id"] = ["w2", "", "w9"]
    elif change == "numeric-id":
        frame["window_id"] = [1, 2, 3]
    elif change == "empty":
        frame = frame.iloc[:0]
    elif change == "missing-time":
        frame = frame.drop(columns=["session_time_ns"])
    elif change == "float-time":
        frame["session_time_ns"] = [1., 2., 3.]
    elif change == "bool-time":
        frame["session_time_ns"] = [True, False, True]
    elif change == "null-time":
        frame["session_time_ns"] = pd.Series([1, None, 3], dtype="Int64")
    elif change == "out-of-int64":
        frame["session_time_ns"] = pd.Series([2**63, 2**63+1, 2**63+2], dtype="uint64")
    elif change == "missing-target":
        frame = frame.drop(columns=[TARGETS[0]])
    elif change == "bool-target":
        frame[TARGETS[0]] = [True, False, True]
    elif change == "string-target":
        frame[TARGETS[0]] = ["1", "2", "3"]
    elif change == "missing-validity":
        frame = frame.drop(columns=["valid_mask"])
    elif change == "string-validity":
        frame["valid_mask"] = ["True", "False", "True"]
    else:
        frame["valid_mask"] = pd.Series([True, None, True], dtype="boolean")
    write_frame(bundle, frame)
    refuse(package, output)


@pytest.mark.parametrize("label", ["", "   ", "a"*121, "line\nbreak", None, 17])
def test_model_label_refusal(tmp_path, label):
    package, bundle, output = seed(tmp_path)
    refuse(package, output, model_id=label)


def test_missing_and_external_bundle_are_refused(tmp_path):
    package, bundle, output = seed(tmp_path)
    refuse(package, output, bundle_id="missing")
    external = tmp_path / "outside"
    shutil.copytree(bundle.parent, external)
    before = files(package)
    with pytest.raises(ValueError):
        prepare_prediction_template(package, str(external), "model", output)
    assert not output.exists()
    assert files(package) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["outside", "session.mmsession"]


@pytest.mark.parametrize("kind", ["file", "directory", "live-link", "dangling-link"])
def test_existing_destination_is_never_replaced(tmp_path, kind):
    package, bundle, output = seed(tmp_path)
    sentinel = tmp_path / "sentinel"
    if kind == "file":
        output.write_bytes(b"KEEP EXISTING")
    elif kind == "directory":
        output.mkdir()
    else:
        if kind == "live-link":
            sentinel.write_bytes(b"KEEP LINK TARGET")
        try:
            output.symlink_to(sentinel)
        except OSError as exc:
            pytest.skip(f"host cannot create this filesystem control: {exc}")
    before = files(package)
    link = os.readlink(output) if output.is_symlink() else None
    with pytest.raises(FileExistsError):
        prepare_prediction_template(package, "bundle", "model", output)
    if kind == "file":
        assert output.read_bytes() == b"KEEP EXISTING"
    elif kind == "directory":
        assert output.is_dir() and not list(output.iterdir())
    else:
        assert output.is_symlink() and os.readlink(output) == link
        if kind == "live-link":
            assert sentinel.read_bytes() == b"KEEP LINK TARGET"
        else:
            assert not sentinel.exists()
    assert files(package) == before


def test_package_destination_is_refused_without_changes(tmp_path):
    package, bundle, output = seed(tmp_path)
    before = files(package)
    with pytest.raises(ValueError):
        prepare_prediction_template(package, "bundle", "model", package / "new.json")
    assert files(package) == before


def test_late_source_change_refuses_publication(tmp_path, monkeypatch):
    package, bundle, output = seed(tmp_path)
    original = predictions._load_inputs
    def changed(*args, **kwargs):
        p = bundle / "manifest.json"
        p.write_bytes(p.read_bytes() + b" \n")
        return original(*args, **kwargs)
    monkeypatch.setattr(predictions, "_load_inputs", changed)
    with pytest.raises(ValueError, match="manifestSha256"):
        prepare_prediction_template(package, "bundle", "model", output)
    assert not output.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["session.mmsession"]


def test_race_created_destination_is_preserved(tmp_path, monkeypatch):
    package, bundle, output = seed(tmp_path)
    original = predictions._load_inputs
    def raced(*args, **kwargs):
        result = original(*args, **kwargs)
        output.write_bytes(b"OTHER WRITER")
        return result
    monkeypatch.setattr(predictions, "_load_inputs", raced)
    with pytest.raises(FileExistsError):
        prepare_prediction_template(package, "bundle", "model", output)
    assert output.read_bytes() == b"OTHER WRITER"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["predictions.json", "session.mmsession"]


def test_failed_publication_leaves_no_partial_output(tmp_path, monkeypatch):
    package, bundle, output = seed(tmp_path)
    before = files(package)
    def failed(*args, **kwargs):
        raise OSError("publication fault")
    monkeypatch.setattr(os, "link", failed)
    with pytest.raises(OSError, match="publication fault"):
        prepare_prediction_template(package, "bundle", "model", output)
    assert not output.exists()
    assert files(package) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["session.mmsession"]


def test_original_size_bound_is_preserved(tmp_path):
    package, bundle, output = seed(tmp_path)
    assert predictions.MAX_INPUT_BYTES == 64 * 1024 * 1024
    with (bundle / "windows.parquet").open("wb") as stream:
        stream.seek(predictions.MAX_INPUT_BYTES)
        stream.write(b"x")
    refuse(package, output)


def test_authored_prediction_size_is_checked_before_publication(tmp_path, monkeypatch):
    package, bundle, output = seed(tmp_path)
    frame = pd.read_parquet(bundle / "windows.parquet")
    frame["window_id"] = ["w"*5000 + str(i) for i in range(3)]
    write_frame(bundle, frame)
    limit = max((bundle / "windows.parquet").stat().st_size,
                (bundle / "manifest.json").stat().st_size) + 1
    # Scaled control of the unchanged evaluator's per-file limit; not a RAM bound.
    monkeypatch.setattr(predictions, "MAX_INPUT_BYTES", limit)
    refuse(package, output)


def test_real_cli_and_maintained_evaluation_artifacts(tmp_path):
    package, bundle, output = seed(tmp_path)
    before = files(package)
    command = [sys.executable, "-B", str(ROOT / "tools/prepare_predictions.py"),
               str(package), "--bundle-job", "bundle", "--model-id",
               "  external-model Δ  ", "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    (tmp_path / "template.stdout").write_text(result.stdout)
    (tmp_path / "template.stderr").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert "placeholder" in result.stdout.lower()
    assert "unavailable" in result.stdout.lower()
    assert files(package) == before
    template_bytes = output.read_bytes()
    evaluated = subprocess.run([
        sys.executable, "-B", str(ROOT / "tools/run_analysis.py"), "eval",
        str(package), "--ml-bundle-job", "bundle", "--predictions", str(output),
        "--overwrite-job-id", "template-evaluation",
    ], capture_output=True, text=True, timeout=60)
    (tmp_path / "eval.stdout").write_text(evaluated.stdout)
    (tmp_path / "eval.stderr").write_text(evaluated.stderr)
    assert evaluated.returncode == 0, evaluated.stderr
    folder = package / "processing/jobs/template-evaluation/eval"
    report = json.loads((folder / "eval_report.json").read_bytes())
    assert report["evaluationMode"] == "external_predictions"
    assert report["windowCount"] == 3
    assert report["baseline"] is None
    for target in TARGETS:
        metric = report["metrics"][target]
        assert metric["n"] == 0
        assert metric["mae"] is metric["rmse"] is metric["pearsonR"] is None
        assert metric["pearsonReason"] == "insufficient_pairs"
        assert metric["excluded"] == {
            "invalidWindow": 1, "nonfiniteTeacher": 0, "missingPrediction": 2}
    assert (folder / "prediction_input.json").read_bytes() == template_bytes
    assert (folder / "source_bundle_manifest.json").read_bytes() == (
        bundle / "manifest.json"
    ).read_bytes()
    assert {name: sha(package / name) for name in before} == before


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX child-only file-size fault control")
def test_actual_failed_write_never_publishes_partial_json(tmp_path):
    package, bundle, output = seed(tmp_path)
    before = files(package)
    script = (
        "import resource,runpy,sys;"
        "resource.setrlimit(resource.RLIMIT_FSIZE,(256,256));"
        "sys.argv=" + repr([str(ROOT / "tools/prepare_predictions.py"),
            str(package), "--bundle-job", "bundle", "--model-id", "model",
            "--output", str(output)]) + ";"
        "runpy.run_path(sys.argv[0],run_name='__main__')"
    )
    result = subprocess.run([sys.executable, "-B", "-c", script],
                            capture_output=True, timeout=45)
    assert result.returncode != 0
    assert not output.exists()
    assert files(package) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["session.mmsession"]
