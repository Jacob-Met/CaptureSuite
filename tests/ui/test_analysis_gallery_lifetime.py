# SPDX-License-Identifier: GPL-3.0-only
"""Keep native image memory bounded when saved results are reopened."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_reloaded_gallery_releases_replaced_native_image_pages(qapp, tmp_path: Path):
    from capture_desktop.widgets_analysis_plots import FigureGallery
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QLabel, QScrollArea
    from shiboken6 import isValid

    for number in range(3):
        path = tmp_path / "figures" / "nested" / f"channel_{number}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image = QImage(16, 12, QImage.Format.Format_RGB32)
        image.fill(QColor("#2855cc"))
        assert image.save(str(path), "PNG")

    def drain():
        qapp.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qapp.processEvents()

    def pages(gallery):
        return [
            area for area in gallery._tabs.findChildren(QScrollArea)
            if isinstance(area.widget(), QLabel)
        ]

    gallery = FigureGallery()
    previous = []
    try:
        for _ in range(4):
            gallery.load_job_dir(tmp_path)
            drain()
            assert gallery._tabs.count() == 4
            assert len(pages(gallery)) == 3
            assert all(not isValid(page) for page in previous)
            previous.extend(gallery._tabs.widget(i) for i in range(1, 4))
        sync = gallery._tabs.widget(0)
        gallery.clear()
        drain()
        assert gallery._tabs.count() == 1
        assert gallery._tabs.widget(0) is sync
        assert not pages(gallery)
        assert all(not isValid(page) for page in previous)
    finally:
        gallery.close()
        gallery.deleteLater()
        drain()
