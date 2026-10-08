# SPDX-License-Identifier: GPL-3.0-only
"""Actual offline eval jobs with authored, independently supplied predictions."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from capture_analysis.jobs import JobParams, run
from capture_session.package_reader import load_review_summary

from tests.analysis.test_pose_job import _write_pose_package

ROOT = Path(__file__).resolve().parents[2]
ANGLE = "theta_elbow_flex_L"
VELOCITY = "omega_elbow_flex_L"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    package = _write_pose_package(tmp_path / "session")
    folder = package / "processing" / "jobs" / "bundle" / "ml_bundle"
    folder.mkdir(parents=True)
    windows = folder / "windows.parquet"
    pd.DataFrame(
        {
            "window_id": [f"w{i:05d}" for i in range(6)],
            "session_time_ns": [10**18 + i * 100_000_000 for i in range(6)],
            "valid_mask": [True, True, False, True, True, True],
            ANGLE: [0.0, 3.0, 6.0, 9.0, 12.0, 15.0],
            VELOCITY: [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
        }
    ).to_parquet(windows, index=False)
    manifest = folder / "manifest.json"
    _write_json(
        manifest,
        {
            "schemaId": "capture.ml_bundle/1",
            "sessionIds": [load_review_summary(package).session_id],
            "targetColumns": [ANGLE, VELOCITY],
            "sha256": {"windows.parquet": _sha(windows)},
            "provisional": True,
        },
    )
    values_angle = [1.0, 1.0, 999.0, 13.0, None, 20.0]
    values_velocity = [2.0, 5.0, -999.0, 6.0, 11.0, 13.0]
    document = {
        "schemaId": "capture.eval_predictions/1",
        "modelId": "synthetic-offset-control",
        "windowsSha256": _sha(windows),
        "manifestSha256": _sha(manifest),
        "predictions": [
            {
                "window_id": f"w{i:05d}",
                "session_time_ns": 10**18 + i * 100_000_000,
                "values": {ANGLE: values_angle[i], VELOCITY: values_velocity[i]},
            }
            for i in reversed(range(6))
        ],
    }
    predictions = tmp_path / "predictions.json"
    _write_json(predictions, document)
    return package, predictions, windows, manifest


def _run(package: Path, predictions: Path, job_id: str = "actual-eval"):
    return run(
        package,
        JobParams(
            command="eval",
            overwrite_job_id=job_id,
            extra={"ml_bundle_job_id": "bundle", "prediction_path": str(predictions)},
        ),
    )


def _report(result) -> dict:
    return json.loads((result.job_dir / "eval" / "eval_report.json").read_text())


def _inputs(package: Path, predictions: Path) -> dict[str, str]:
    paths = [p for p in package.rglob("*") if p.is_file() and "actual-eval" not in p.parts]
    return {str(p): _sha(p) for p in paths + [predictions]}


def _rebind(predictions: Path, windows: Path, manifest: Path) -> None:
    source = json.loads(manifest.read_text())
    source["sha256"]["windows.parquet"] = _sha(windows)
    _write_json(manifest, source)
    doc = json.loads(predictions.read_text())
    doc["windowsSha256"] = _sha(windows)
    doc["manifestSha256"] = _sha(manifest)
    _write_json(predictions, doc)


def test_external_predictions_measure_errors_and_preserve_identity(tmp_path: Path) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    before = _inputs(package, predictions)
    result = _run(package, predictions)
    report = _report(result)
    assert report["evaluationMode"] == "external_predictions"
    assert report["baseline"] is None
    assert report["modelId"] == "synthetic-offset-control"
    assert report["provisional"] is True
    assert report["windowCount"] == 6
    assert report["validWindowCount"] == 5
    angle = report["metrics"][ANGLE]
    assert angle["n"] == 4
    assert angle["mae"] == pytest.approx(3.0)
    assert angle["rmse"] == pytest.approx(math.sqrt(11.5))
    assert angle["pearsonR"] == pytest.approx(np.corrcoef([0, 3, 9, 15], [1, 1, 13, 20])[0, 1])
    assert angle["units"] == "deg"
    assert angle["excluded"] == {"invalidWindow": 1, "nonfiniteTeacher": 0, "missingPrediction": 1}
    velocity = report["metrics"][VELOCITY]
    assert velocity["n"] == 5
    assert velocity["mae"] == pytest.approx(1.0)
    assert velocity["rmse"] == pytest.approx(math.sqrt(7 / 5))
    assert velocity["units"] == "deg/s"
    table = pd.read_parquet(result.job_dir / "eval" / "predictions.parquet")
    assert table["window_id"].tolist() == [f"w{i:05d}" for i in range(6)]
    assert table["session_time_ns"].tolist() == list(pd.read_parquet(windows)["session_time_ns"])
    assert table[f"err_{ANGLE}"].iloc[[0, 1, 3, 5]].tolist() == [1.0, -2.0, 4.0, 5.0]
    assert table[f"err_{ANGLE}"].iloc[[2, 4]].isna().all()
    assert table[f"valid_{ANGLE}"].tolist() == [True, True, False, True, False, True]
    assert report["inputProvenance"]["windowsSha256"] == _sha(windows)
    assert report["inputProvenance"]["manifestSha256"] == _sha(manifest)
    assert report["inputProvenance"]["predictionsSha256"] == _sha(predictions)
    assert (
        (result.job_dir / "eval" / "prediction_input.json").read_bytes()
        == predictions.read_bytes()
    )
    figures = list((result.job_dir / "eval" / "figures").glob("*"))
    assert len([p for p in figures if p.suffix == ".png"]) == 2
    assert len([p for p in figures if p.suffix == ".pdf"]) == 2
    for row in result.manifest["outputs"]:
        if row["relativePath"].startswith("eval/"):
            path = result.job_dir / row["relativePath"]
            assert row["bytes"] == path.stat().st_size
            assert row["sha256"] == _sha(path)
    assert _inputs(package, predictions) == before


@pytest.mark.parametrize(
    "mutation",
    ["windows_digest", "manifest_digest", "missing", "duplicate", "foreign",
     "timestamp", "float_time", "bool_time", "missing_target", "foreign_target",
     "bool_value", "infinite_value", "wrong_schema"],
)
def test_invalid_predictions_refused_before_eval_outputs(tmp_path: Path, mutation: str) -> None:
    package, predictions, _windows, _manifest = _fixture(tmp_path)
    doc = json.loads(predictions.read_text())
    row = doc["predictions"][0]
    if mutation == "windows_digest":
        doc["windowsSha256"] = "0" * 64
    elif mutation == "manifest_digest":
        doc["manifestSha256"] = "0" * 64
    elif mutation == "missing":
        doc["predictions"].pop()
    elif mutation == "duplicate":
        doc["predictions"][1] = dict(row)
    elif mutation == "foreign":
        row["window_id"] = "foreign-window"
    elif mutation == "timestamp":
        row["session_time_ns"] += 1
    elif mutation == "float_time":
        row["session_time_ns"] = float(row["session_time_ns"])
    elif mutation == "bool_time":
        row["session_time_ns"] = True
    elif mutation == "missing_target":
        del row["values"][ANGLE]
    elif mutation == "foreign_target":
        row["values"]["not-a-target"] = 1.0
    elif mutation == "bool_value":
        row["values"][ANGLE] = True
    elif mutation == "infinite_value":
        row["values"][ANGLE] = float("inf")
    elif mutation == "wrong_schema":
        doc["schemaId"] = "capture.eval_predictions/2"
    _write_json(predictions, doc)
    before = _inputs(package, predictions)
    with pytest.raises(ValueError):
        _run(package, predictions)
    assert not list((package / "processing" / "jobs").glob("*/eval"))
    assert all(Path(p).is_file() and _sha(Path(p)) == sha for p, sha in before.items())


@pytest.mark.parametrize("mutation", ["integer_mask", "null_mask", "float_time", "duplicate_id",
                                     "foreign_session", "stale_windows_digest"])
def test_invalid_bound_bundle_refused(tmp_path: Path, mutation: str) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    frame = pd.read_parquet(windows)
    if mutation == "integer_mask":
        frame["valid_mask"] = frame["valid_mask"].astype(int)
    elif mutation == "null_mask":
        frame["valid_mask"] = pd.Series([True, None, False, True, True, True], dtype="boolean")
    elif mutation == "float_time":
        frame["session_time_ns"] = frame["session_time_ns"].astype(float)
    elif mutation == "duplicate_id":
        frame.loc[1, "window_id"] = frame.loc[0, "window_id"]
    elif mutation == "foreign_session":
        doc = json.loads(manifest.read_text())
        doc["sessionIds"] = ["another-session"]
        _write_json(manifest, doc)
    frame.to_parquet(windows, index=False)
    _rebind(predictions, windows, manifest)
    if mutation == "stale_windows_digest":
        doc = json.loads(manifest.read_text())
        doc["sha256"]["windows.parquet"] = "0" * 64
        _write_json(manifest, doc)
        doc = json.loads(predictions.read_text())
        doc["manifestSha256"] = _sha(manifest)
        _write_json(predictions, doc)
    before = _inputs(package, predictions)
    with pytest.raises(ValueError):
        _run(package, predictions)
    assert not list((package / "processing" / "jobs").glob("*/eval"))
    assert all(_sha(Path(p)) == sha for p, sha in before.items())


def test_unavailable_teacher_is_excluded_per_target(tmp_path: Path) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    frame = pd.read_parquet(windows)
    frame.loc[0, ANGLE] = np.nan
    frame.to_parquet(windows, index=False)
    _rebind(predictions, windows, manifest)
    metrics = _report(_run(package, predictions))["metrics"]
    assert metrics[ANGLE]["n"] == 3
    assert metrics[ANGLE]["excluded"]["nonfiniteTeacher"] == 1
    assert metrics[VELOCITY]["n"] == 5


def test_no_valid_pairs_are_unavailable_not_zero_error(tmp_path: Path) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    frame = pd.read_parquet(windows)
    frame["valid_mask"] = False
    frame.to_parquet(windows, index=False)
    _rebind(predictions, windows, manifest)
    report = _report(_run(package, predictions))
    for metric in report["metrics"].values():
        assert metric["n"] == 0
        assert metric["mae"] is None
        assert metric["rmse"] is None
        assert metric["pearsonR"] is None
        assert metric["pearsonReason"] == "insufficient_pairs"
        assert metric["excluded"]["invalidWindow"] == 6


def test_constant_target_has_undefined_correlation(tmp_path: Path) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    frame = pd.read_parquet(windows)
    frame[ANGLE] = 5.0
    frame.to_parquet(windows, index=False)
    _rebind(predictions, windows, manifest)
    metric = _report(_run(package, predictions))["metrics"][ANGLE]
    assert metric["n"] == 4
    assert metric["pearsonR"] is None
    assert metric["pearsonReason"] == "constant_series"
    assert metric["mae"] == pytest.approx((4 + 4 + 8 + 15) / 4)


def test_unrepresentable_residual_refused_before_output(tmp_path: Path) -> None:
    package, predictions, windows, manifest = _fixture(tmp_path)
    frame = pd.read_parquet(windows)
    frame.loc[0, ANGLE] = 1e308
    frame.to_parquet(windows, index=False)
    _rebind(predictions, windows, manifest)
    doc = json.loads(predictions.read_text())
    doc["predictions"][-1]["values"][ANGLE] = -1e308
    _write_json(predictions, doc)
    with pytest.raises(ValueError, match="residual"):
        _run(package, predictions)
    assert not list((package / "processing" / "jobs").glob("*/eval"))


def test_actual_cli_receives_prediction_file(tmp_path: Path) -> None:
    package, predictions, _windows, _manifest = _fixture(tmp_path)
    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_analysis.py"), "eval", str(package),
         "--ml-bundle-job", "bundle", "--predictions", str(predictions),
         "--overwrite-job-id", "actual-eval"],
        capture_output=True, text=True, check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    doc = json.loads(
        (package / "processing" / "jobs" / "actual-eval" / "eval" / "eval_report.json").read_text()
    )
    assert doc["evaluationMode"] == "external_predictions"
    assert doc["metrics"][ANGLE]["mae"] == pytest.approx(3.0)


def test_default_identity_fixture_remains_explicit(tmp_path: Path) -> None:
    package, _predictions, _windows, _manifest = _fixture(tmp_path)
    result = run(package, JobParams(command="eval", extra={"ml_bundle_job_id": "bundle"}))
    doc = _report(result)
    assert doc["baseline"] == "identity_teacher_sim"
    assert doc["provisional"] is True
    assert doc["metrics"][ANGLE]["mae"] == 0.0


def test_real_pose_kinematics_bundle_to_external_eval(tmp_path: Path) -> None:
    from tests.analysis.test_kinematics_ml_bundle import _write_radar_energy_features_job

    package = _write_pose_package(tmp_path / "pipeline-session")
    features_id = _write_radar_energy_features_job(package)
    pose = run(package, JobParams(command="pose", overwrite_job_id="pose"))
    kin = run(package, JobParams(command="kinematics", overwrite_job_id="kin",
                                extra={"pose_job_id": pose.job_id}))
    bundle = run(
        package,
        JobParams(command="ml_bundle", overwrite_job_id="bundle",
                  extra={"features_job_id": features_id, "kinematics_job_id": kin.job_id,
                         "window_sec": 0.1, "hop_sec": 0.05}),
    )
    folder = bundle.job_dir / "ml_bundle"
    windows = pd.read_parquet(folder / "windows.parquet")
    manifest = json.loads((folder / "manifest.json").read_text())
    columns = manifest["targetColumns"]
    doc = {
        "schemaId": "capture.eval_predictions/1",
        "modelId": "synthetic-two-unit-offset",
        "windowsSha256": _sha(folder / "windows.parquet"),
        "manifestSha256": _sha(folder / "manifest.json"),
        "predictions": [
            {"window_id": row["window_id"], "session_time_ns": int(row["session_time_ns"]),
             "values": {c: float(row[c]) + 2.0 for c in columns}}
            for _, row in windows.iterrows()
        ],
    }
    predictions = tmp_path / "pipeline-predictions.json"
    _write_json(predictions, doc)
    result = _run(package, predictions)
    for metric in _report(result)["metrics"].values():
        assert metric["n"] > 0
        assert metric["mae"] == pytest.approx(2.0)
        assert metric["rmse"] == pytest.approx(2.0)


def test_model_label_is_literal_text(tmp_path: Path) -> None:
    package, predictions, _windows, _manifest = _fixture(tmp_path)
    doc = json.loads(predictions.read_text())
    doc["modelId"] = r"$\not_a_math_command$"
    _write_json(predictions, doc)
    result = _run(package, predictions)
    assert _report(result)["modelId"] == doc["modelId"]
    assert _report(result)["metrics"][ANGLE]["mae"] == pytest.approx(3.0)


def test_versioned_prediction_schema_accepts_actual_input(tmp_path: Path) -> None:
    import jsonschema

    _package, predictions, _windows, _manifest = _fixture(tmp_path)
    schema = json.loads((ROOT / "schemas/eval/predictions.schema.json").read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(json.loads(predictions.read_text()), schema)

@pytest.mark.parametrize(
    "values",
    [[1.0, 0.9999999999999999], [180.0, 179.99999999999997]],
)
def test_pearson_near_constant_reversed_pairs(values: list[float]) -> None:
    # Every nonconstant reversed two-point series has exact correlation -1.
    from capture_analysis.eval.predictions import _scores

    teacher = np.asarray(values)
    metric, errors = _scores(teacher, teacher[::-1].copy())
    assert metric["n"] == 2
    assert metric["mae"] > 0.0
    assert np.isfinite(errors).all()
    assert metric["pearsonR"] == pytest.approx(-1.0, abs=1e-14)
    assert metric["pearsonReason"] is None


def test_pearson_large_finite_pairs_keep_overflow_resistance() -> None:
    from capture_analysis.eval.predictions import _scores

    teacher = np.asarray([-1e308, 0.0, 1e308])
    metric, errors = _scores(teacher, teacher.copy())
    assert metric["pearsonR"] == pytest.approx(1.0, abs=1e-14)
    assert metric["pearsonReason"] is None
    assert metric["mae"] == metric["rmse"] == 0.0
    assert errors.tolist() == [0.0, 0.0, 0.0]
