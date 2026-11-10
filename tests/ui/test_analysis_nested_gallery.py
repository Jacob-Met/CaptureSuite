# SPDX-License-Identifier: GPL-3.0-only
"""Native saved PNG discovery across current nested and legacy flat layouts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def _png(path: Path, color: str) -> None:
    from PySide6.QtGui import QColor, QImage

    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(16, 12, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    assert image.save(str(path), "PNG")


def _hashes(path: Path) -> dict[str, str]:
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


def _numeric_path(job: Path, source: str, stream: str, channel: int = 0) -> Path:
    return (job / "figures/numeric" / f"source-{source.encode().hex()}"
            / f"stream-{stream.encode().hex()}" / f"channel_{channel}.png")


def _titles(gallery) -> list[str]:
    return [gallery._tabs.tabText(i) for i in range(gallery._tabs.count())]


def _color(gallery, index: int) -> str:
    label = gallery._tabs.widget(index).widget()
    return label.pixmap().toImage().pixelColor(0, 0).name()


def test_flat_figures_and_sync_dashboard_keep_their_existing_behavior(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    _png(tmp_path / "figures/legacy_signal.png", "#2855cc")
    _png(tmp_path / "figures/sync_dashboard.png", "#000000")
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(tmp_path)
    assert _titles(gallery) == ["Sync", "legacy signal"]
    assert _color(gallery, 1) == "#2855cc"
    assert gallery._tabs.tabToolTip(1) == "legacy_signal.png"
    assert _hashes(tmp_path) == before
    gallery.close()


def test_nested_numeric_figures_preserve_channels_and_linked_series(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    for channel, color in enumerate(("#cc3322", "#22aa55")):
        _png(_numeric_path(tmp_path, "lsl", "numeric.stream", channel), color)
    doc = {
        "schemaId": "capture.sync_dashboard_series/1", "title": "retained numeric",
        "window": {"startSessionNs": 0, "endSessionNs": 1_000_000_000}, "gaps": [],
        "series": [{"label": f"channel {i}", "t_ns": [0, 500_000_000, 1_000_000_000],
                    "y": [i, i + 1, i + 2]} for i in range(2)],
    }
    (tmp_path / "figures/sync_dashboard_series.json").write_text(json.dumps(doc))
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(tmp_path)
    assert _titles(gallery) == ["Sync", "lsl / numeric.stream / channel 0",
                                "lsl / numeric.stream / channel 1"]
    assert [_color(gallery, i) for i in (1, 2)] == ["#cc3322", "#22aa55"]
    assert len(gallery._sync._linked) == 2
    assert gallery._sync._title.text() == "retained numeric"
    for i in (1, 2):
        expected = _numeric_path(tmp_path, "lsl", "numeric.stream", i - 1)
        assert gallery._tabs.tabToolTip(i) == expected.relative_to(tmp_path / "figures").as_posix()
    assert _hashes(tmp_path) == before
    gallery.close()


def test_same_filename_retains_case_unicode_and_stream_identity(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    identities = [("Arm", "force", "#aabbcc"), ("arm", "force", "#bbccdd"),
                  ("café", "force / left", "#ccddee")]
    for source, stream, color in identities:
        _png(_numeric_path(tmp_path, source, stream), color)
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(tmp_path)
    by_title = {gallery._tabs.tabText(i): _color(gallery, i)
                for i in range(1, gallery._tabs.count())}
    assert by_title == {f"{source} / {stream} / channel 0": color
                        for source, stream, color in identities}
    tips = [gallery._tabs.tabToolTip(i) for i in range(1, gallery._tabs.count())]
    assert len(set(tips)) == 3
    assert _hashes(tmp_path) == before
    gallery.close()


def test_unknown_nested_paths_and_nested_dashboard_png_remain_inspectable(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    _png(tmp_path / "figures/custom/sync_dashboard.png", "#ddeeff")
    _png(tmp_path / "figures/numeric/source-zz/stream-e9/channel_0.png", "#eeff11")
    _png(tmp_path / "figures/sync_dashboard.png", "#000000")
    gallery = FigureGallery()
    gallery.load_job_dir(tmp_path)
    assert _titles(gallery) == ["Sync", "custom / sync dashboard",
                                "numeric / source-zz / stream-e9 / channel 0"]
    assert [_color(gallery, i) for i in (1, 2)] == ["#ddeeff", "#eeff11"]
    gallery.close()


def test_reloading_a_job_replaces_nested_and_flat_tabs(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    first, second, empty = (tmp_path / name for name in ("first", "second", "empty"))
    _png(_numeric_path(first, "a", "b"), "#112233")
    _png(first / "figures/flat.png", "#223344")
    _png(second / "figures/new_signal.png", "#334455")
    empty.mkdir()
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(first)
    assert gallery._tabs.count() == 3
    gallery.load_job_dir(second)
    assert _titles(gallery) == ["Sync", "new signal"]
    assert _color(gallery, 1) == "#334455"
    gallery.load_job_dir(empty)
    assert _titles(gallery) == ["Sync"]
    assert not gallery._sync._linked
    assert _hashes(tmp_path) == before
    gallery.close()


def test_one_unreadable_png_does_not_hide_other_saved_figures(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    _png(tmp_path / "figures/nested/good.png", "#445566")
    bad = tmp_path / "figures/nested/bad.png"
    bad.write_bytes(b"not an image")
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(tmp_path)
    assert _titles(gallery) == ["Sync", "nested / bad", "nested / good"]
    assert gallery._tabs.widget(1).widget().text() == "Could not load bad.png"
    assert _color(gallery, 2) == "#445566"
    assert _hashes(tmp_path) == before
    gallery.close()


def test_png_discovery_refuses_external_file_links_and_directories(qapp, tmp_path):
    from capture_desktop.widgets_analysis_plots import FigureGallery

    job = tmp_path / "job"
    outside = tmp_path / "external.png"
    _png(outside, "#aa1122")
    _png(job / "figures/nested/good.png", "#22aa55")
    foreign = job / "figures/foreign.png"
    try:
        foreign.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"This filesystem cannot create the symlink fixture: {exc}")
    link_before = foreign.readlink()
    assert foreign.samefile(outside)
    (job / "figures/not_a_file.png").mkdir()
    before = _hashes(tmp_path)
    gallery = FigureGallery()
    gallery.load_job_dir(job)
    assert _titles(gallery) == ["Sync", "nested / good"]
    assert _color(gallery, 1) == "#22aa55"
    assert gallery._tabs.tabToolTip(1) == "nested/good.png"
    # Windows may retain an extended-length prefix in the link target.
    assert foreign.readlink() == link_before
    assert _hashes(tmp_path) == before
    gallery.close()
