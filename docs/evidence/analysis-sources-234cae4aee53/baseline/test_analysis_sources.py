# SPDX-License-Identifier: GPL-3.0-only
"""Real recorded-source selection, Qt admission and MCAP job provenance."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")


def _package(path: Path) -> Path:
    from tests.analysis.test_numeric_cli_receiving import make_package, write_json

    package = make_package(path)
    # The review reader reports folder-a, but the pipeline filters sampler.a.
    # Keep the actual sealed MCAP bytes and descriptor identities intact.
    (package / "sources" / "sampler.a").rename(package / "sources" / "folder-a")
    integrity = json.loads((package / "integrity.json").read_text(encoding="utf-8"))
    for entry in integrity["files"]:
        entry["path"] = entry["path"].replace("sources/sampler.a/", "sources/folder-a/")
    write_json(package / "integrity.json", integrity)
    return package


def _screen(qapp, package: Path):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    screen.resize(1200, 900)
    screen.show()
    qapp.processEvents()
    return screen


def _close(qapp, screen):
    from tests.ui.test_analysis_scope import _close_widgets

    _close_widgets(qapp, screen)


def test_operator_can_choose_exact_recorded_sources(qapp, tmp_path: Path):
    from capture_analysis.discover import discover_streams
    from capture_session import load_review_summary
    from PySide6.QtWidgets import QComboBox

    package = _package(tmp_path / "sources μ.mmsession")
    assert load_review_summary(package).source_ids == ["folder-a", "sampler.b"]
    assert sorted({ref.source_id for ref in discover_streams(package)}) == [
        "sampler.a", "sampler.b",
    ]
    screen = _screen(qapp, package)
    try:
        modes = [w for w in screen.findChildren(QComboBox)
                 if w.accessibleName() == "Analysis source mode"]
        assert len(modes) == 1, "Analysis has no operator-accessible recorded-source picker"
        assert [modes[0].itemText(i) for i in range(modes[0].count())] == [
            "All recorded sources", "Selected sources",
        ]
    finally:
        _close(qapp, screen)
