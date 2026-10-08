# SPDX-License-Identifier: GPL-3.0-only
"""Saved-parameter viewing keeps exact identity, types and read-only behavior."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from capture_desktop.analysis_job_comparison import (
    MAX_JSON_BYTES,
    JobParameterError,
    compare_job_parameters,
    load_job_parameters,
    revalidate_job_parameters,
)

ROOT = Path(__file__).resolve().parents[2]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _job(parent: Path, name: str, params: dict, *, session: str = "synthetic-session") -> Path:
    job = parent / name
    job.mkdir(parents=True)
    raw = (json.dumps(params, indent=2, ensure_ascii=False) + "\n").encode()
    manifest = {
        "schemaId": "capture.analysis_job/1",
        "jobId": name,
        "sessionId": session,
        "status": "completed_with_warnings",
        "captureAnalysisVersion": "synthetic-test-version",
        "manifestSha256": "a" * 64,
        "paramsDigest": _sha(json.dumps(params, sort_keys=True, separators=(",", ":")).encode()),
        "outputs": [
            {
                "relativePath": "params.json",
                "kind": "params",
                "bytes": len(raw),
                "sha256": _sha(raw),
            },
            {
                "relativePath": "job_manifest.json",
                "kind": "manifest",
                "bytes": 1,
                "sha256": "0" * 64,
            },
            {"relativePath": "unused.png", "kind": "figure", "bytes": 7, "sha256": "1" * 64},
        ],
        "warnings": ["Synthetic receiving fixture; not a scientific measurement."],
    }
    (job / "params.json").write_bytes(raw)
    (job / "job_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return job


def _manifest(job: Path, update) -> None:
    path = job / "job_manifest.json"
    doc = json.loads(path.read_bytes())
    update(doc)
    path.write_text(json.dumps(doc) + "\n")


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_original_bytes_provenance_and_decoded_views_are_immutable(tmp_path):
    job = _job(tmp_path, "loaded", {"command": "qc", "extra": {"日本語": [True, None, 0.0]}})
    before = _files(tmp_path)
    snapshot = load_job_parameters(job)
    assert snapshot.params_bytes == before["loaded/params.json"]
    assert snapshot.manifest_bytes == before["loaded/job_manifest.json"]
    assert snapshot.params_sha256 == _sha(snapshot.params_bytes)
    assert snapshot.manifest_sha256 == _sha(snapshot.manifest_bytes)
    # A historical self-entry is not current verification.
    assert snapshot.manifest_sha256 != "0" * 64
    snapshot.params["extra"]["日本語"].clear()
    snapshot.manifest["outputs"].clear()
    assert snapshot.params["extra"]["日本語"] == [True, None, 0.0]
    assert len(snapshot.manifest["outputs"]) == 3
    revalidate_job_parameters(snapshot)
    assert _files(tmp_path) == before


def test_structured_diff_preserves_paths_types_absence_and_array_order(tmp_path):
    other = {
        "same": 2,
        "a/b": {"~key": [1, None, "tail"]},
        "removed": None,
        "typed": True,
        "number": 1,
        "zero": -0.0,
        "empty": {},
        "unicode": "日本語",
    }
    loaded = {
        "same": 2,
        "a/b": {"~key": [None, 1]},
        "added": None,
        "typed": 1,
        "number": 1.0,
        "zero": 0.0,
        "empty": [],
        "unicode": "日本語",
    }
    a = load_job_parameters(_job(tmp_path, "other", other))
    b = load_job_parameters(_job(tmp_path, "loaded", loaded))
    rows = compare_job_parameters(a, b)
    actual = {r.pointer: (r.change, r.other_json, r.loaded_json) for r in rows}
    assert actual == {
        "/a~1b/~0key/0": ("changed", "1", "null"),
        "/a~1b/~0key/1": ("changed", "null", "1"),
        "/a~1b/~0key/2": ("only_other", '"tail"', None),
        "/added": ("only_loaded", None, "null"),
        "/empty": ("changed", "{}", "[]"),
        "/number": ("changed", "1", "1.0"),
        "/removed": ("only_other", "null", None),
        "/typed": ("changed", "true", "1"),
        "/zero": ("changed", "-0.0", "0.0"),
    }
    assert [r.pointer for r in rows] == list(actual)


def test_equal_settings_do_not_require_equal_job_or_recorded_capture_hashes(tmp_path):
    a = _job(tmp_path, "other", {"extra": {"a": 1, "b": [1, 2]}})
    b = _job(tmp_path, "loaded", {"extra": {"b": [1, 2], "a": 1}})
    _manifest(b, lambda doc: doc.update(manifestSha256="b" * 64))
    assert compare_job_parameters(load_job_parameters(a), load_job_parameters(b)) == ()


def test_manifest_numeric_overflow_is_not_infinite_provenance(tmp_path):
    job = _job(tmp_path, "job", {"command": "qc"})
    path = job / "job_manifest.json"
    raw = path.read_text().replace('"synthetic-test-version"', "1e999")
    path.write_text(raw)
    with pytest.raises(JobParameterError, match="finite"):
        load_job_parameters(job)


def test_oversized_diff_is_refused_as_a_whole(tmp_path):
    other = _job(tmp_path, "other", {str(i): 0 for i in range(5001)})
    loaded = _job(tmp_path, "loaded", {str(i): 1 for i in range(5001)})
    with pytest.raises(JobParameterError, match="5,000"):
        compare_job_parameters(load_job_parameters(other), load_job_parameters(loaded))


@pytest.mark.parametrize(
    "target,payload",
    [
        ("params.json", b"[]"),
        ("params.json", b'{"a":1,"a":2}'),
        ("params.json", b'{"value":NaN}'),
        ("params.json", b'{"value":Infinity}'),
        ("params.json", b'{"value":1e999}'),
        ("params.json", b'{"invalid":"\xff"}'),
        ("job_manifest.json", b"[]"),
        ("job_manifest.json", b'{"a":1,"a":2}'),
        ("job_manifest.json", b"{"),
    ],
)
def test_malformed_input_is_refused_without_changing_any_other_bytes(tmp_path, target, payload):
    job = _job(tmp_path, "job", {"command": "qc"})
    (job / target).write_bytes(payload)
    before = _files(tmp_path)
    with pytest.raises(JobParameterError):
        load_job_parameters(job)
    assert _files(tmp_path) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("schemaId", "capture.analysis_job/999"),
        ("jobId", "different-job"),
        ("status", "failed"),
        ("status", ["completed"]),
        ("sessionId", ""),
        ("sessionId", 1),
        ("paramsDigest", "0" * 64),
        ("outputs", []),
        ("outputs", [0]),
        ("outputs", "params.json"),
    ],
)
def test_invalid_manifest_admission(tmp_path, field, value):
    job = _job(tmp_path, "job", {"command": "qc"})
    _manifest(job, lambda doc: doc.update({field: value}))
    with pytest.raises(JobParameterError):
        load_job_parameters(job)


@pytest.mark.parametrize("change", ["duplicate", "kind", "bytes", "bool-bytes", "sha"])
def test_parameter_output_entry_must_bind_actual_bytes_once(tmp_path, change):
    job = _job(tmp_path, "job", {"command": "qc"})

    def alter(doc):
        row = doc["outputs"][0]
        if change == "duplicate":
            doc["outputs"].append(dict(row))
        else:
            row.update(
                {
                    {"kind": "kind", "bytes": "bytes", "bool-bytes": "bytes", "sha": "sha256"}[
                        change
                    ]: {"kind": "other", "bytes": 1, "bool-bytes": True, "sha": "f" * 64}[change]
                }
            )

    _manifest(job, alter)
    with pytest.raises(JobParameterError):
        load_job_parameters(job)


def test_bound_size_depth_and_ambiguous_json_are_not_displayed(tmp_path):
    job = _job(tmp_path, "large", {"command": "qc"})
    with (job / "params.json").open("wb") as stream:
        stream.truncate(MAX_JSON_BYTES + 1)
    with pytest.raises(JobParameterError, match="4 MiB"):
        load_job_parameters(job)
    value: object = 1
    for _ in range(60):
        value = [value]
    deep = _job(tmp_path, "deep", {"nested": value})
    with pytest.raises(JobParameterError, match="depth"):
        load_job_parameters(deep)


@pytest.mark.parametrize("target", ["params.json", "job_manifest.json"])
def test_stale_inputs_are_refused_then_explicit_reload_reads_current_bytes(tmp_path, target):
    a = _job(tmp_path, "other", {"n": 1})
    b = _job(tmp_path, "loaded", {"n": 2})
    before, after = load_job_parameters(a), load_job_parameters(b)
    old = (a / target).read_bytes()
    (a / target).write_bytes(old + b" ")
    with pytest.raises(JobParameterError, match="changed"):
        compare_job_parameters(before, after)
    (a / target).write_bytes(old)
    assert compare_job_parameters(load_job_parameters(a), after)[0].pointer == "/n"


def test_directory_replacement_is_not_the_original_snapshot(tmp_path):
    job = _job(tmp_path, "loaded", {"n": 1})
    snapshot = load_job_parameters(job)
    job.rename(tmp_path / "retained-original")
    shutil.copytree(tmp_path / "retained-original", job)
    with pytest.raises(JobParameterError, match="replaced"):
        revalidate_job_parameters(snapshot)
    assert load_job_parameters(job).params == {"n": 1}


def test_linked_input_files_are_refused(tmp_path):
    job = _job(tmp_path, "loaded", {"n": 1})
    params = job / "params.json"
    params.rename(tmp_path / "retained-params.json")
    try:
        params.symlink_to(tmp_path / "retained-params.json")
    except OSError as exc:
        pytest.skip(f"This host cannot create the link fixture: {exc}")
    with pytest.raises(JobParameterError, match="regular"):
        load_job_parameters(job)


@pytest.mark.parametrize("elsewhere", [False, True])
def test_comparison_requires_the_same_session_and_physical_jobs_parent(tmp_path, elsewhere):
    a = _job(tmp_path / "jobs", "other", {"n": 1})
    b = _job(
        tmp_path / ("elsewhere" if elsewhere else "jobs"),
        "loaded",
        {"n": 2},
        session="synthetic-session" if elsewhere else "different-session",
    )
    with pytest.raises(JobParameterError, match="same session"):
        compare_job_parameters(load_job_parameters(a), load_job_parameters(b))


def _open_inspector(qapp, job):
    from capture_desktop.widgets_analysis_plots import JobInspector
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    inspector = JobInspector()
    inspector.load_job_dir(job)
    inspector.show()
    button = inspector._parameters._button
    assert button.isEnabled()
    button.setFocus()
    QTest.keyClick(button, Qt.Key.Key_Space)
    qapp.processEvents()
    dialog = inspector._parameters._dialog
    assert dialog is not None and dialog.isVisible()
    return inspector, dialog


def _choose(qapp, dialog, monkeypatch, path):
    from capture_desktop import widgets_analysis_comparison as ui
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    monkeypatch.setattr(ui.QFileDialog, "getExistingDirectory", lambda *_args: str(path))
    QTest.mouseClick(dialog._choose, Qt.MouseButton.LeftButton)
    qapp.processEvents()


def test_native_keyboard_selection_cancellation_full_values_and_clear_reload(
    qapp, tmp_path, monkeypatch
):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    other = _job(tmp_path, "other", {"a/b": None, "long": "x" * 350})
    loaded = _job(tmp_path, "loaded", {"long": "y" * 350, "null": None})
    before = _files(tmp_path)
    inspector, dialog = _open_inspector(qapp, loaded)
    assert json.loads(dialog._params.toPlainText()) == {"long": "y" * 350, "null": None}
    _choose(qapp, dialog, monkeypatch, other)
    assert dialog._table.rowCount() == 3
    assert not dialog._error.text()
    assert '"/a~1b"' in dialog._selected.text()
    assert dialog._other_value.toPlainText() == "null"
    assert "absent" in dialog._loaded_value.toPlainText()
    QTest.keyClick(dialog._table, Qt.Key.Key_Down)
    qapp.processEvents()
    assert json.loads(dialog._other_value.toPlainText()) == "x" * 350
    assert json.loads(dialog._loaded_value.toPlainText()) == "y" * 350
    old_rows = dialog._rows
    _choose(qapp, dialog, monkeypatch, "")
    assert dialog._rows == old_rows
    inspector.clear()
    qapp.processEvents()
    assert inspector._parameters._dialog is None
    assert not inspector._parameters._button.isEnabled()
    inspector.load_job_dir(other)
    assert inspector._parameters._source.job_id == "other"
    assert _files(tmp_path) == before
    inspector.close()


def test_native_invalid_choice_clears_comparison_and_reload_recovers(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    other = _job(tmp_path, "other", {"n": 1})
    loaded = _job(tmp_path, "loaded", {"n": 2})
    inspector, dialog = _open_inspector(qapp, loaded)
    _choose(qapp, dialog, monkeypatch, other)
    original = (loaded / "params.json").read_bytes()
    (loaded / "params.json").write_bytes(original + b" ")
    _choose(qapp, dialog, monkeypatch, other)
    assert dialog._table.rowCount() == 0
    assert not dialog._params.toPlainText()
    assert not dialog._choose.isEnabled()
    assert "Reload" in dialog._error.text()
    (loaded / "params.json").write_bytes(original)
    QTest.mouseClick(dialog._reload, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert dialog._table.rowCount() == 1
    assert not dialog._error.text()
    _choose(qapp, dialog, monkeypatch, loaded)
    assert dialog._table.rowCount() == 0
    assert "different job" in dialog._error.text()
    assert dialog._params.toPlainText()
    inspector.close()


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"outputs":[3]}',
        b"\xff",
        b'{"nested":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
    ],
    ids=["array-root", "invalid-output-row", "invalid-utf8", "deep-unknown-identity"],
)
def test_inspector_displays_malformed_manifest_refusal_without_a_comparison(
    qapp, tmp_path, payload
):
    from capture_desktop.widgets_analysis_plots import JobInspector

    job = _job(tmp_path, "loaded", {"n": 1})
    (job / "job_manifest.json").write_bytes(payload)
    inspector = JobInspector()
    inspector.load_job_dir(job)
    assert not inspector._parameters._button.isEnabled()
    assert "manifest error" in inspector._meta.text()
    inspector.close()


def test_inspector_refuses_linked_manifest_before_showing_external_metadata(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import JobInspector

    job = _job(tmp_path, "loaded", {"n": 1})
    manifest = job / "job_manifest.json"
    target = tmp_path / "outside-manifest.json"
    manifest.rename(target)
    try:
        manifest.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"This host cannot create the link fixture: {exc}")
    before = target.read_bytes()
    inspector = JobInspector()
    inspector.load_job_dir(job)
    assert "manifest error" in inspector._meta.text()
    assert not inspector._parameters._button.isEnabled()
    assert target.read_bytes() == before
    inspector.close()


def test_inspector_keeps_failed_job_metadata_and_outputs_without_saved_parameters(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import JobInspector

    job = _job(tmp_path, "failed-job", {"n": 1})
    (job / "params.json").unlink()

    def failed(document):
        document.pop("paramsDigest")
        document.update(
            status="failed",
            gapPolicy="fail",
            pluginManifestVersion="retained-plugin-version",
            outputs=[{"relativePath": "logs/job.log", "kind": "log", "sha256": "a" * 64}],
        )

    _manifest(job, failed)
    before = _files(tmp_path)
    inspector = JobInspector()
    inspector.load_job_dir(job)
    assert inspector._meta.text() == (
        "job_id=failed-job\nstatus=failed\ngap_policy=fail\n"
        f"plugin_manifest=retained-plugin-version\npath={job}"
    )
    assert inspector._outputs_layout.itemAt(0).widget().text() == (
        "[log] logs/job.log\nsha256:aaaaaaaaaaaa…"
    )
    assert not inspector._parameters._button.isEnabled()
    assert _files(tmp_path) == before
    inspector.close()


def test_native_real_qc_pair_keeps_all_saved_source_bytes(qapp, tmp_path, monkeypatch):
    from capture_analysis import JobParams, run

    package = tmp_path / "synthetic.mmsession"
    shutil.copytree(ROOT / "tests/fixtures/mini_session", package)
    other = run(
        package,
        JobParams(
            command="qc", overwrite_job_id="other-qc", extra={"threshold": 0.25, "side": "left"}
        ),
    )
    loaded = run(
        package,
        JobParams(
            command="qc",
            overwrite_job_id="loaded-qc",
            extra={"threshold": 0.5, "side": "right", "include": True},
        ),
    )
    assert other.status == loaded.status == "completed"
    before = _files(package)
    inspector, dialog = _open_inspector(qapp, loaded.job_dir)
    _choose(qapp, dialog, monkeypatch, other.job_dir)
    assert not dialog._error.text()
    assert {r.pointer for r in dialog._rows} == {
        "/extra/include",
        "/extra/side",
        "/extra/threshold",
        "/overwriteJobId",
    }
    assert json.loads(dialog._params.toPlainText()) == json.loads(
        (loaded.job_dir / "params.json").read_bytes()
    )
    assert "Actual params.json SHA-256:" in dialog._comparison_provenance.toPlainText()
    inspector.clear()
    qapp.processEvents()
    assert _files(package) == before
    inspector.close()
