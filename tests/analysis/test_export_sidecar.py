# SPDX-License-Identifier: GPL-3.0-only
"""Phase 1 export wizard / provenance sidecar on mini_session fixture."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


def test_export_writes_manifest_and_sidecar(tmp_path: Path) -> None:
    from capture_desktop.export_wizard import ExportOptions, run_export

    out = tmp_path / "export_out"
    out.mkdir()
    code, _tail = run_export(
        str(FIXTURE),
        ExportOptions(out_dir=str(out), verify=False),
        repo_root=ROOT,
    )
    assert code == 0
    manifest = out / "export_manifest.json"
    assert manifest.is_file()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    assert doc.get("export_schema") == "capture.export_manifest/1"
    sidecar = out / "provenance_sidecar.json"
    assert sidecar.is_file()
    prov = json.loads(sidecar.read_text(encoding="utf-8"))
    assert prov.get("schemaId") == "capture.export_provenance_sidecar/1"
    assert prov.get("exportManifest") == "export_manifest.json"

# ---------------------------------------------------------------------------
# T68 (D064) modality-selection tests — muse-coord-a8b9, 2026-10-01.
# Verifies that export modality selections control actual modality output.
# ---------------------------------------------------------------------------

import importlib.util
import sys
import types

import pytest


def _load_export_session():
    """Import tools/export_session.py standalone (no package install needed)."""
    spec = importlib.util.spec_from_file_location(
        "t68_export_session", ROOT / "tools" / "export_session.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_wizard():
    """Import desktop/capture_desktop/export_wizard.py.

    Uses the real import when PySide6 is installed (CI); otherwise stubs the
    Qt layer so the pure selection/sidecar logic stays testable here.
    """
    if importlib.util.find_spec("PySide6") is not None:
        from capture_desktop import export_wizard

        return export_wizard
    pyside6 = types.ModuleType("PySide6")
    qtw = types.ModuleType("PySide6.QtWidgets")

    class _Dummy:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, name):
            return _Dummy()

        def __call__(self, *a, **k):
            return _Dummy()

    for _n in (
        "QCheckBox",
        "QDialog",
        "QDialogButtonBox",
        "QFileDialog",
        "QFormLayout",
        "QLabel",
        "QLineEdit",
        "QMessageBox",
        "QVBoxLayout",
        "QWidget",
    ):
        setattr(qtw, _n, _Dummy)
    pyside6.QtWidgets = qtw
    sys.modules.setdefault("PySide6", pyside6)
    sys.modules.setdefault("PySide6.QtWidgets", qtw)
    pkg = types.ModuleType("capture_desktop")
    pkg.__path__ = []
    theme_stub = types.ModuleType("capture_desktop.theme")
    theme_stub.ui = lambda *a, **k: None
    sys.modules.setdefault("capture_desktop", pkg)
    sys.modules.setdefault("capture_desktop.theme", theme_stub)
    path = ROOT / "desktop" / "capture_desktop" / "export_wizard.py"
    spec = importlib.util.spec_from_file_location("capture_desktop.export_wizard", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_desktop.export_wizard"] = module
    spec.loader.exec_module(module)
    return module


def _make_radar_package(path: Path) -> Path:
    """Synthetic package holding one radar stream.json (no mcap/mkv needed)."""
    pkg = path / "synth_pkg"
    src = pkg / "sources" / "radar.0"
    src.mkdir(parents=True)
    (src / "stream.json").write_text(
        json.dumps({"schema": "radar.stream", "num_chirps": 32, "board_uuid": "t68"}),
        encoding="utf-8",
    )
    return pkg


def _read_manifest(out: Path) -> dict:
    return json.loads((out / "export_manifest.json").read_text(encoding="utf-8"))


# --- --modalities parsing --------------------------------------------------


def test_parse_modalities_defaults_to_all() -> None:
    es = _load_export_session()
    assert es._parse_modalities(None) == frozenset({"radar", "video", "emg", "imu"})


def test_parse_modalities_subset() -> None:
    es = _load_export_session()
    assert es._parse_modalities("radar,emg") == frozenset({"radar", "emg"})
    assert es._parse_modalities("  Video ,IMU ") == frozenset({"video", "imu"})


def test_parse_modalities_empty_rejected() -> None:
    es = _load_export_session()
    with pytest.raises(ValueError):
        es._parse_modalities("")
    with pytest.raises(ValueError):
        es._parse_modalities(" , ")


def test_parse_modalities_unknown_rejected() -> None:
    es = _load_export_session()
    with pytest.raises(ValueError):
        es._parse_modalities("radar,lidar")


# --- selection propagation through main() ----------------------------------


def test_main_rejects_empty_selection(tmp_path: Path) -> None:
    es = _load_export_session()
    pkg = _make_radar_package(tmp_path)
    with pytest.raises(SystemExit):
        es.main([str(pkg), str(tmp_path / "out"), "--modalities", ""])
    # Validation happens before output creation.
    assert not (tmp_path / "out").exists()


def test_main_rejects_unknown_modality(tmp_path: Path) -> None:
    es = _load_export_session()
    pkg = _make_radar_package(tmp_path)
    with pytest.raises(SystemExit):
        es.main([str(pkg), str(tmp_path / "out"), "--modalities", "radar,lidar"])


def test_main_radar_only_selection(tmp_path: Path) -> None:
    es = _load_export_session()
    pkg = _make_radar_package(tmp_path)
    out = tmp_path / "out"
    assert es.main([str(pkg), str(out), "--modalities", "radar"]) == 0
    doc = _read_manifest(out)
    assert doc["modalities"] == ["radar"]
    assert len(doc["radar"]) == 1
    assert doc["video"] == []
    assert doc["imu"] == []
    assert doc["emg"] == []
    assert not (out / "video").exists()
    assert not (out / "imu").exists()
    assert not (out / "emg").exists()


def test_main_no_flag_exports_all_modalities(tmp_path: Path) -> None:
    """Backward compatibility: no --modalities flag behaves as before."""
    es = _load_export_session()
    pkg = _make_radar_package(tmp_path)
    out = tmp_path / "out"
    assert es.main([str(pkg), str(out)]) == 0
    doc = _read_manifest(out)
    assert doc["modalities"] == ["emg", "imu", "radar", "video"]
    assert len(doc["radar"]) == 1


def test_main_dispatches_only_selected_modalities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    es = _load_export_session()
    calls: list = []
    monkeypatch.setattr(
        es, "export_radar_mcaps", lambda r, o, m: calls.append("radar")
    )
    monkeypatch.setattr(es, "export_video", lambda r, o, m: calls.append("video"))
    monkeypatch.setattr(
        es,
        "export_imu_emg",
        lambda r, o, m, modalities=None: calls.append(("imu_emg", modalities)),
    )
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    out = tmp_path / "out"
    assert es.main([str(pkg), str(out), "--modalities", "video,emg"]) == 0
    kinds = [c if isinstance(c, str) else c[0] for c in calls]
    assert kinds == ["video", "imu_emg"]
    assert calls[1][1] == frozenset({"video", "emg"})


# --- IMU/EMG independent gating ---------------------------------------------


def test_imu_emg_kind_filter() -> None:
    es = _load_export_session()
    assert es._imu_emg_specs_for(None) == ("imu", "emg")
    assert es._imu_emg_specs_for(frozenset({"emg"})) == ("emg",)
    assert es._imu_emg_specs_for(frozenset({"imu"})) == ("imu",)
    assert es._imu_emg_specs_for(frozenset({"radar", "video"})) == ()


# --- wizard flag building + requested-vs-actual sidecar ---------------------


def test_wizard_builds_modalities_flag() -> None:
    wiz = _load_wizard()
    opts = wiz.ExportOptions(
        out_dir="/tmp/x",
        include_radar=True,
        include_video=False,
        include_emg=True,
        include_imu=False,
    )
    assert wiz._build_modalities_args(opts) == ["--modalities", "radar,emg"]
    assert wiz._build_modalities_args(wiz.ExportOptions(out_dir="/tmp/x")) == [
        "--modalities",
        "radar,video,emg,imu",
    ]
    none = wiz.ExportOptions(
        out_dir="/tmp/x",
        include_radar=False,
        include_video=False,
        include_emg=False,
        include_imu=False,
    )
    assert wiz._build_modalities_args(none) == ["--modalities", ""]


def test_wizard_run_export_propagates_selection_and_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiz = _load_wizard()
    captured: dict = {}

    class _Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        outdir = Path(cmd[3])
        (outdir / "export_manifest.json").write_text(
            json.dumps(
                {
                    "export_schema": "capture.export_manifest/1",
                    "radar": [{"source_id": "r0"}],
                    "video": [],
                    "imu": [],
                    "emg": [],
                }
            ),
            encoding="utf-8",
        )
        return _Result()

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", fake_run)
    out = tmp_path / "wout"
    out.mkdir()
    opts = wiz.ExportOptions(
        out_dir=str(out),
        include_radar=True,
        include_video=False,
        include_emg=False,
        include_imu=False,
        verify=False,
        write_sidecar=True,
    )
    code, _tail = wiz.run_export(str(FIXTURE), opts, repo_root=ROOT)
    assert code == 0
    cmd = captured["cmd"]
    assert cmd[cmd.index("--modalities") + 1] == "radar"
    sidecar = json.loads((out / "provenance_sidecar.json").read_text(encoding="utf-8"))
    # Requested streams stay verbatim...
    assert sidecar["streams"] == {
        "radar": True,
        "video": False,
        "emg": False,
        "imu": False,
    }
    # ...and actual output is recorded separately (requested != actual).
    assert sidecar["actualStreams"] == {
        "radar": True,
        "video": False,
        "emg": False,
        "imu": False,
    }
