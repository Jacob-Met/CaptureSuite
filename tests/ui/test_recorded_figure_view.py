# SPDX-License-Identifier: GPL-3.0-only
"""Recorded figure axes stay visible at initial fit and remain inspectable at 100%."""

from pathlib import Path

from capture_desktop.widgets_recorded_figure import RecordedFigureView
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest


def make_figure(path: Path) -> Path:
    image = QImage(2400, 1600, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    assert image.save(str(path))
    return path


def assert_fits(widget: RecordedFigureView) -> None:
    bounds = widget._view.mapFromScene(widget._item.boundingRect()).boundingRect()
    viewport = widget._view.viewport().rect()
    assert bounds.width() <= viewport.width()
    assert bounds.height() <= viewport.height()
    assert bounds.left() >= viewport.left() - 1
    assert bounds.top() >= viewport.top() - 1
    assert bounds.right() <= viewport.right() + 1
    assert bounds.bottom() <= viewport.bottom() + 1


def test_initial_fit_and_resizing_show_entire_recorded_figure(qapp, tmp_path: Path) -> None:
    widget = RecordedFigureView(make_figure(tmp_path / "axes.png"))
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    qapp.processEvents()
    assert widget._view.viewport().width() > 500
    assert_fits(widget)
    initial_zoom = widget.zoom_factor()
    widget.resize(950, 750)
    qapp.processEvents()
    assert widget.zoom_factor() > initial_zoom
    assert_fits(widget)


def test_native_pixels_deliberate_zoom_and_return_to_fit(qapp, tmp_path: Path) -> None:
    path = make_figure(tmp_path / "original.png")
    original = path.read_bytes()
    widget = RecordedFigureView(path)
    widget.resize(600, 400)
    widget.show()
    qapp.processEvents()
    QTest.mouseClick(widget._actual, Qt.MouseButton.LeftButton)
    assert widget.zoom_factor() == 1.0
    assert not widget._fit.isChecked()
    assert widget._view.horizontalScrollBar().maximum() > 0
    QTest.mouseClick(widget._in, Qt.MouseButton.LeftButton)
    assert widget.zoom_factor() == 1.25
    widget.resize(750, 500)
    assert widget.zoom_factor() == 1.25
    QTest.mouseClick(widget._fit, Qt.MouseButton.LeftButton)
    assert widget._fit.isChecked()
    assert_fits(widget)
    assert path.read_bytes() == original


def test_unavailable_png_has_clear_state(qapp, tmp_path: Path) -> None:
    widget = RecordedFigureView(tmp_path / "missing.png")
    widget.show()
    qapp.processEvents()
    assert widget._scale_label.text() == "Figure unavailable"
    assert not widget._actual.isEnabled()
    assert not widget._fit.isEnabled()
