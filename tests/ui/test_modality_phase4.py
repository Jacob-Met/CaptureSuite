# SPDX-License-Identifier: GPL-3.0-only
"""Phase 4 modality depth + preset library tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from capture_desktop import theme
from capture_desktop.screen_presets import PresetLibraryDialog
from capture_desktop.state import CaptureState, SourceRow
from capture_desktop.widgets_modality_expanded import (
    expanded_detail_lines,
    expanded_honesty_footer,
)
from capture_session.registry import AppRegistry
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, setting="dark")
    return app


def _row(**kwargs) -> SourceRow:
    defaults = {
        "source_id": "sim.emg.main",
        "alias": "EMG sim",
        "source_type": "emg",
        "modality": "emg",
        "selected": True,
        "enabled": True,
        "plugin_id": "sim.emg",
        "nominal_rate_hz": 2000.0,
        "metadata": {"channel_count": "8", "units": "a.u."},
    }
    defaults.update(kwargs)
    return SourceRow(**defaults)


def test_emg_expanded_shows_provisional_badge():
    state = CaptureState()
    state.sources = [_row()]
    lines = expanded_detail_lines(state.sources[0], state)
    joined = "\n".join(lines)
    assert "provisional" in joined
    assert "8 ch" in joined
    assert expanded_honesty_footer(state.sources[0]).startswith("Sim/replay")


def test_radar_array_lines_when_multiple_selected():
    state = CaptureState()
    state.sources = [
        _row(
            source_id="sim.radar.a",
            alias="Radar A",
            source_type="radar",
            modality="radar",
            plugin_id="sim.radar",
            nominal_rate_hz=20.0,
        ),
        _row(
            source_id="sim.radar.b",
            alias="Radar B",
            source_type="radar",
            modality="radar",
            plugin_id="sim.radar",
            nominal_rate_hz=20.0,
        ),
    ]
    state.selected_ids = {s.source_id for s in state.sources}
    lines = expanded_detail_lines(state.sources[0], state)
    assert any("software coordinated" in line.lower() for line in lines)


def test_preset_library_lists_all_ten_types(qapp, tmp_path: Path):
    reg_path = tmp_path / "registry.sqlite"
    with AppRegistry(reg_path) as reg:
        for ptype in (
            "device",
            "naming",
            "anatomical_mapping",
            "spatial_layout",
            "radar_array",
            "capture",
            "checkpoint_protocol",
            "hotkey",
            "workspace",
            "export",
        ):
            reg.put_preset(
                preset_id=f"{ptype}-demo",
                preset_type=ptype,
                name=f"demo-{ptype}",
                schema_version="1",
                content_json=json.dumps({"demo": True}),
            )

    persistence = SimpleNamespace(
        registry=AppRegistry(reg_path),
        registry_open=SimpleNamespace(read_only=False, message=""),
    )
    persistence.registry.open()
    dlg = PresetLibraryDialog(persistence, parent=None)  # type: ignore[arg-type]
    dlg.show()
    qapp.processEvents()
    assert dlg._list.count() == 10
    persistence.registry.close()


def test_vendor_replay_fixture_exists():
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "vendor_replay"
        / "emg"
        / "sample_batches.jsonl"
    )
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    doc = json.loads(lines[0])
    assert "channels" in doc
    assert "timestamp_ns" in doc
