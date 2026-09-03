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
