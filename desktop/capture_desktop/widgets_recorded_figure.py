# SPDX-License-Identifier: GPL-3.0-only
"""Fit and inspect retained PNG figures without changing their original pixels."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _ImageViewport(QGraphicsView):
    resized = Signal()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()


class RecordedFigureView(QWidget):
    """Initial fit keeps axes visible; deliberate zoom provides native-pixel detail."""

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        controls = QHBoxLayout()
        self._fit = QPushButton("Fit figure")
        self._fit.setCheckable(True)
        self._fit.setChecked(True)
        self._fit.setToolTip("Show the complete recorded figure, including titles and axes")
        self._actual = QPushButton("100%")
        self._actual.setToolTip("Inspect original pixels; drag the figure to pan")
        self._out = QPushButton("−")
        self._out.setAccessibleName("Zoom out")
        self._out.setToolTip("Zoom out")
        self._in = QPushButton("+")
        self._in.setAccessibleName("Zoom in")
        self._in.setToolTip("Zoom in")
        self._scale_label = QLabel()
        self._scale_label.setObjectName("Dim")
        for button in (self._fit, self._out, self._in, self._actual):
            controls.addWidget(button)
        controls.addWidget(self._scale_label)
        controls.addStretch(1)
        layout.addLayout(controls)
        self._scene = QGraphicsScene(self)
        self._view = _ImageViewport(self._scene, self)
        self._view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setAccessibleName("Recorded figure")
        self._view.setToolTip("Fit shows the entire figure. At larger zoom, drag to pan.")
        layout.addWidget(self._view, 1)
        self._pixmap = QPixmap(str(path))
        self._item = None
        self._fit.clicked.connect(self.fit_figure)
        self._actual.clicked.connect(lambda: self.set_zoom(1.0))
        self._out.clicked.connect(lambda: self.set_zoom(self.zoom_factor() / 1.25))
        self._in.clicked.connect(lambda: self.set_zoom(self.zoom_factor() * 1.25))
        self._view.resized.connect(self._fit_after_resize)
        if self._pixmap.isNull():
            self._scene.addText(f"Could not load {path.name}")
            self._scale_label.setText("Figure unavailable")
            for button in (self._fit, self._out, self._in, self._actual):
                button.setEnabled(False)
        else:
            self._item = self._scene.addPixmap(self._pixmap)
            self._scene.setSceneRect(self._item.boundingRect())
            self.fit_figure()

    def zoom_factor(self) -> float:
        return self._view.transform().m11()

    def _fit_after_resize(self) -> None:
        if self._fit.isChecked():
            self.fit_figure()

    def fit_figure(self) -> None:
        if self._item is None:
            return
        self._fit.setChecked(True)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.fitInView(self._item, Qt.AspectRatioMode.KeepAspectRatio)
        self._update_scale()

    def set_zoom(self, factor: float) -> None:
        if self._item is None:
            return
        factor = max(0.05, min(8.0, factor))
        self._fit.setChecked(False)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._view.resetTransform()
        self._view.scale(factor, factor)
        self._update_scale()

    def _update_scale(self) -> None:
        self._scale_label.setText(
            f"{self.zoom_factor():.0%} · {self._pixmap.width()} × {self._pixmap.height()} px"
        )
