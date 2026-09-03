# SPDX-License-Identifier: GPL-3.0-only
"""Painted preview widgets for daemon PreviewFrame payloads."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import ClassVar

from capture_protocol.generated.capture.v1 import preview_pb2
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme

# Fusion-style worker preview_view options (radar.ifx/3).
RADAR_FMCW_VIEWS: list[tuple[str, str]] = [
    ("range_doppler", "Range-Doppler"),
    ("range_doppler_hd", "Range-Doppler (HD)"),
    ("range_spectrum", "Range spectrum"),
    ("range_spectrogram", "Range spectrogram"),
    ("time_domain", "Time domain"),
]
RADAR_LTR11_VIEWS: list[tuple[str, str]] = [
    ("motion_trace", "Motion trace"),
    ("doppler_spectrogram", "Doppler spectrogram"),
]

# Heatmap ramp, gamma 0.65 so weak returns are not crushed into the floor.
_HEAT_LUT: list[bytes] = [
    bytes(
        (
            int(16 + 50 * t),
            int(28 + 200 * t),
            int(70 + 160 * (1.0 - t) * (0.35 + 0.65 * t)),
        )
    )
    for t in ((i / 255.0) ** 0.65 for i in range(256))
]

# Kinds that keep a native painter but can optionally switch to a graph.
_GRAPHABLE_KINDS = frozenset(
    {
        preview_pb2.PREVIEW_KIND_ORIENTATION,
        preview_pb2.PREVIEW_KIND_MATRIX_2D,
    }
)
_HISTORY = 96


def _bg(painter: QPainter, rect: QRectF) -> None:
    painter.setBrush(theme.PANEL_DEEP)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, 4, 4)


def _trace_polyline(
    samples: list[float], box: QRectF, centre: float, amplitude: float
) -> QPolygonF:
    if len(samples) < 2:
        return QPolygonF()
    step = box.width() / (len(samples) - 1)
    return QPolygonF(
        [
            QPointF(box.left() + i * step, centre - v * amplitude)
            for i, v in enumerate(samples)
        ]
    )


class TracePreview(QWidget):
    """TRACE_SINGLE / TRACE_BLOCK / VECTOR_PROFILE / SCALAR_SERIES."""

    def __init__(self, parent: QWidget | None = None, *, color: QColor | None = None) -> None:
        super().__init__(parent)
        self._color = color or theme.GREEN
        self._names: list[str] = []
        self._channels: list[list[float]] = []
        self._display_min = -1.0
        self._display_max = 1.0
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self._names = []
        self._channels = []
        self.update()

    def set_trace(self, trace: preview_pb2.PreviewTrace) -> None:
        n_ch = max(1, int(trace.channel_count) or 1)
        ppc = int(trace.points_per_channel)
        samples = list(trace.samples)
        self._names = list(trace.channel_names) or [f"ch{i}" for i in range(n_ch)]
        self._display_min = trace.display_min if trace.display_min != trace.display_max else -1.0
        self._display_max = trace.display_max if trace.display_min != trace.display_max else 1.0
        channels: list[list[float]] = []
        if ppc > 0 and samples:
            for c in range(n_ch):
                start = c * ppc
                chunk = samples[start : start + ppc]
                if chunk:
                    channels.append(chunk)
        self._channels = channels
        self.update()

    def set_samples(self, samples: list[float], name: str = "ch0") -> None:
        self._names = [name]
        self._channels = [samples] if samples else []
        self.update()

    def set_channels(
        self,
        channels: list[list[float]],
        *,
        names: list[str] | None = None,
        display_min: float = 0.0,
        display_max: float = 1.0,
    ) -> None:
        self._channels = [list(ch) for ch in channels if ch]
        self._names = list(names) if names else [f"ch{i}" for i in range(len(self._channels))]
        if display_min == display_max:
            display_min, display_max = 0.0, 1.0
        self._display_min = display_min
        self._display_max = display_max
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        _bg(painter, rect)
        if not self._channels:
            painter.setPen(theme.TEXT_FAINT)
            painter.setFont(theme.ui(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for preview")
            return

        n = len(self._channels)
        plot = rect.adjusted(6, 5, -6, -5)
        lane_h = plot.height() / n
        span = max(1e-6, abs(self._display_max - self._display_min))
        painter.setFont(theme.ui(8))
        for index, values in enumerate(self._channels):
            top = plot.top() + index * lane_h
            centre = top + lane_h / 2
            painter.setPen(QPen(theme.dim(theme.BORDER, 110), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), centre), QPointF(plot.right(), centre))
            if n > 1 and index < len(self._names):
                painter.setPen(theme.TEXT_DIM)
                painter.drawText(
                    QRectF(plot.left() + 2, top, 48, lane_h),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    self._names[index],
                )
            # Normalize around midpoint of display range.
            mid = (self._display_max + self._display_min) / 2
            normed = [(v - mid) / (span / 2) for v in values]
            amplitude = (lane_h / 2) * 0.82
            painter.setPen(QPen(self._color, 1.1))
            painter.drawPolyline(_trace_polyline(normed, plot, centre, amplitude))


class ImagePreview(QWidget):
    """IMAGE_THUMBNAIL — RGB24 or JPEG."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._caption = ""
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self._pixmap = QPixmap()
        self.update()

    def set_caption(self, text: str) -> None:
        self._caption = text
        self.update()

    def set_image(self, image: preview_pb2.PreviewImage) -> None:
        fmt = (image.pixel_format or "").lower()
        data = bytes(image.data)
        pix = QPixmap()
        if fmt == "jpeg" or (not fmt and len(data) >= 2 and data[:2] == b"\xff\xd8"):
            pix.loadFromData(data, "JPEG")
        elif fmt in ("rgb24", "rgb") and image.width and image.height:
            expected = int(image.width) * int(image.height) * 3
            if len(data) >= expected:
                # Keep buffer alive until after copy (QImage does not own `data`).
                self._rgb_buf = data[:expected]
                qimg = QImage(
                    self._rgb_buf,
                    int(image.width),
                    int(image.height),
                    int(image.width) * 3,
                    QImage.Format.Format_RGB888,
                )
                pix = QPixmap.fromImage(qimg.copy())
        else:
            pix.loadFromData(data)
        self._pixmap = pix
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        _bg(painter, rect)
        if self._pixmap.isNull():
            painter.setPen(theme.TEXT_FAINT)
            painter.setFont(theme.ui(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for preview")
        else:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        if self._caption:
            painter.setPen(theme.ORANGE)
            painter.setFont(theme.ui(8, bold=True))
            painter.drawText(
                rect.adjusted(8, 6, -8, -6),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                self._caption,
            )


class OrientationPreview(QWidget):
    """ORIENTATION — wireframe cube from quaternion."""

    VERTICES = [
        (-1, -1, -1),
        (1, -1, -1),
        (1, 1, -1),
        (-1, 1, -1),
        (-1, -1, 1),
        (1, -1, 1),
        (1, 1, 1),
        (-1, 1, 1),
    ]
    EDGES = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._q = (1.0, 0.0, 0.0, 0.0)
        self._accel = 0.0
        self._gyro = 0.0
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self._q = (1.0, 0.0, 0.0, 0.0)
        self.update()

    def set_orientation(self, ori: preview_pb2.PreviewOrientation) -> None:
        self._q = (ori.qw, ori.qx, ori.qy, ori.qz)
        self._accel = ori.accel_magnitude
        self._gyro = ori.gyro_magnitude
        self.update()

    def _rotate(self, v: tuple[float, float, float]) -> tuple[float, float, float]:
        qw, qx, qy, qz = self._q
        x, y, z = v
        # v' = q * v * q^{-1}
        ix = qw * x + qy * z - qz * y
        iy = qw * y + qz * x - qx * z
        iz = qw * z + qx * y - qy * x
        iw = -qx * x - qy * y - qz * z
        return (
            ix * qw + iw * -qx + iy * -qz - iz * -qy,
            iy * qw + iw * -qy + iz * -qx - ix * -qz,
            iz * qw + iw * -qz + ix * -qy - iy * -qx,
        )

    def _project(self, v, scale, centre: QPointF) -> QPointF:
        x, y, z = self._rotate(v)
        depth = 3.4 / (3.4 + z * 0.55)
        return QPointF(centre.x() + x * scale * depth, centre.y() - y * scale * depth)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        _bg(painter, rect)
        centre = rect.center()
        scale = min(rect.width(), rect.height()) * 0.24
        projected = [self._project(v, scale, centre) for v in self.VERTICES]
        painter.setPen(QPen(theme.dim(theme.PURPLE, 190), 1.3))
        for a, b in self.EDGES:
            painter.drawLine(projected[a], projected[b])
        painter.setFont(theme.mono(8))
        painter.setPen(theme.TEXT_DIM)
        painter.drawText(
            rect.adjusted(8, 6, -8, -6),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            f"|a| {self._accel:.2f}\n|ω| {self._gyro:.2f}",
        )


class MatrixPreview(QWidget):
    """MATRIX_2D heatmap."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows = 0
        self._cols = 0
        self._values: list[float] = []
        self._lo = 0.0
        self._hi = 1.0
        self._buffer: bytes | None = None  # QImage does not own its pixels
        self._image: QImage | None = None
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def clear(self) -> None:
        self._rows = 0
        self._cols = 0
        self._values = []
        self._image = None
        self._buffer = None
        self.update()

    def set_matrix(self, matrix: preview_pb2.PreviewMatrix) -> None:
        rows = int(matrix.rows)
        cols = int(matrix.cols)
        values = matrix.values
        lo = matrix.display_min
        hi = matrix.display_max
        if lo == hi and values:
            lo = min(values)
            hi = max(values)
        self._rows = rows
        self._cols = cols
        self._lo = lo
        self._hi = hi
        self._image = None
        self._buffer = None
        if rows <= 0 or cols <= 0 or not values:
            self.update()
            return
        # Colourise once per frame into an RGB888 buffer; painting only scales
        # it. A per-pixel loop inside paintEvent re-ran on every resize and was
        # far too slow for the 128×128 HD view.
        scale = 255.0 / max(1e-9, hi - lo)
        buf = bytearray(rows * cols * 3)
        pos = 0
        for v in values:
            i = int((v - lo) * scale)
            if i < 0:
                i = 0
            elif i > 255:
                i = 255
            buf[pos : pos + 3] = _HEAT_LUT[i]
            pos += 3
            if pos >= len(buf):
                break
        self._buffer = bytes(buf)
        self._image = QImage(
            self._buffer, cols, rows, cols * 3, QImage.Format.Format_RGB888
        )
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        _bg(painter, rect)
        if self._image is None:
            painter.setPen(theme.TEXT_FAINT)
            painter.setFont(theme.ui(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for preview")
            return
        plot = rect.adjusted(4, 4, -4, -4)
        scaled = QPixmap.fromImage(self._image).scaled(
            int(plot.width()),
            int(plot.height()),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(int(plot.left()), int(plot.top()), scaled)


class ScalarSparkline(QWidget):
    """Compact SCALAR_SERIES strip for the source rail."""

    def __init__(self, color: QColor | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color or theme.GREEN
        self._values: list[float] = []
        self.setFixedHeight(18)
        self.setMinimumWidth(54)

    def set_values(self, values: list[float]) -> None:
        self._values = list(values)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        peak = max(max(self._values), 0.001)
        step = rect.width() / (len(self._values) - 1)
        points = [
            QPointF(rect.left() + i * step, rect.bottom() - (v / peak) * rect.height())
            for i, v in enumerate(self._values)
        ]
        painter.setPen(QPen(self._color, 1.2))
        painter.drawPolyline(QPolygonF(points))


def _kind_style_key(kind: int) -> str | None:
    if kind == preview_pb2.PREVIEW_KIND_ORIENTATION:
        return "ORIENTATION"
    if kind == preview_pb2.PREVIEW_KIND_MATRIX_2D:
        return "MATRIX_2D"
    return None


def _range_profile(matrix: preview_pb2.PreviewMatrix) -> list[float]:
    """Collapse range-Doppler to a range profile (max across Doppler per bin)."""
    rows = int(matrix.rows)
    cols = int(matrix.cols)
    values = list(matrix.values)
    if rows <= 0 or cols <= 0 or not values:
        return []
    profile: list[float] = []
    for c in range(cols):
        peak = 0.0
        for r in range(rows):
            idx = r * cols + c
            if idx < len(values):
                peak = max(peak, float(values[idx]))
        profile.append(peak)
    return profile


class PreviewHost(QWidget):
    """Routes a PreviewFrame to the right painter; optional timing-only caption.

    ORIENTATION and MATRIX_2D keep their native painters by default. A small
    Graph toggle switches to a rolling-line view that is easier to read at a
    glance; the choice is shared across hosts and can be persisted via
    ``configure_styles``.

    Radar sources can also pick a Fusion-style ``preview_view`` via the combo;
    that applies through ``radar_view_changed`` → ApplyConfig on the worker.
    """

    radar_view_changed = Signal(str)  # preview_view wire value

    _kind_styles: ClassVar[dict[str, str]] = {}
    _on_style_changed: ClassVar[Callable[[str, str], None] | None] = None

    @classmethod
    def configure_styles(
        cls,
        styles: dict[str, str] | None,
        *,
        on_changed: Callable[[str, str], None] | None = None,
    ) -> None:
        cleaned: dict[str, str] = {}
        for key, value in (styles or {}).items():
            if value in ("native", "graph"):
                cleaned[str(key)] = value
        cls._kind_styles = cleaned
        cls._on_style_changed = on_changed

    @classmethod
    def kind_styles(cls) -> dict[str, str]:
        return dict(cls._kind_styles)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = preview_pb2.PREVIEW_KIND_UNSPECIFIED
        self._timing_only = False
        self._last_frame: preview_pb2.PreviewFrame | None = None
        self._accel_hist: deque[float] = deque(maxlen=_HISTORY)
        self._gyro_hist: deque[float] = deque(maxlen=_HISTORY)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._toolbar = QWidget()
        self._toolbar.setVisible(False)
        toolbar = QHBoxLayout(self._toolbar)
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(4)
        self._style_hint = QLabel("Preview")
        self._style_hint.setObjectName("Dim")
        self._style_hint.setFont(theme.ui(8))
        self._btn_native = QPushButton("Cube")
        self._btn_graph = QPushButton("Graph")
        for btn in (self._btn_native, self._btn_graph):
            btn.setObjectName("PreviewStyle")
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.setFont(theme.ui(9, bold=True))
        self._style_group = QButtonGroup(self)
        self._style_group.setExclusive(True)
        self._style_group.addButton(self._btn_native, 0)
        self._style_group.addButton(self._btn_graph, 1)
        self._style_group.idClicked.connect(self._on_style_id)
        self._view_combo = QComboBox()
        self._view_combo.setObjectName("PreviewStyle")
        self._view_combo.setFixedHeight(26)
        self._view_combo.setMinimumWidth(180)
        self._view_combo.setFont(theme.ui(9))
        self._view_combo.setVisible(False)
        self._view_combo.currentIndexChanged.connect(self._on_view_combo)
        toolbar.addWidget(self._style_hint)
        toolbar.addWidget(self._view_combo, 1)
        toolbar.addWidget(self._btn_native)
        toolbar.addWidget(self._btn_graph)
        toolbar.addStretch(1)
        layout.addWidget(self._toolbar)
        self._radar_views: list[tuple[str, str]] = []
        self._radar_view_current = ""

        self._trace = TracePreview()
        self._image = ImagePreview()
        self._orient = OrientationPreview()
        self._matrix = MatrixPreview()
        self._empty = QLabel("no preview")
        self._empty.setObjectName("Faint")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self._trace, self._image, self._orient, self._matrix, self._empty):
            layout.addWidget(w)
            w.hide()
        self._empty.show()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_timing_only(self, value: bool) -> None:
        self._timing_only = value
        caption = "recording timing only (encode later)" if value else ""
        self._image.set_caption(caption)

    def set_color(self, color: QColor) -> None:
        self._trace._color = color  # noqa: SLF001 — shared paint color

    def set_radar_views(
        self, views: list[tuple[str, str]] | None, current: str = ""
    ) -> None:
        """Show a Fusion-style preview view combo, or hide when ``views`` is None."""
        self._radar_views = list(views or [])
        self._view_combo.blockSignals(True)
        self._view_combo.clear()
        if not self._radar_views:
            self._view_combo.setVisible(False)
            self._radar_view_current = ""
            self._view_combo.blockSignals(False)
            self._toolbar.setVisible(
                self._btn_native.isVisible() or self._btn_graph.isVisible()
            )
            return
        for value, label in self._radar_views:
            self._view_combo.addItem(label, value)
        idx = 0
        for i, (value, _) in enumerate(self._radar_views):
            if value == current:
                idx = i
                break
        self._view_combo.setCurrentIndex(idx)
        self._radar_view_current = self._radar_views[idx][0]
        self._view_combo.setVisible(True)
        self._toolbar.setVisible(True)
        self._view_combo.blockSignals(False)

    def clear(self) -> None:
        self._last_frame = None
        self._accel_hist.clear()
        self._gyro_hist.clear()
        self._trace.clear()
        self._image.clear()
        self._orient.clear()
        self._matrix.clear()
        self._toolbar.setVisible(bool(self._radar_views))
        self._show_only(self._empty)

    def _show_only(self, widget: QWidget) -> None:
        for w in (self._trace, self._image, self._orient, self._matrix, self._empty):
            w.setVisible(w is widget)

    def _style_for(self, kind: int) -> str:
        key = _kind_style_key(kind)
        if key is None:
            return "native"
        return self._kind_styles.get(key, "native")

    def _on_view_combo(self, index: int) -> None:
        if index < 0 or not self._radar_views:
            return
        value = self._view_combo.itemData(index)
        if not isinstance(value, str) or value == self._radar_view_current:
            return
        self._radar_view_current = value
        self.radar_view_changed.emit(value)

    def _sync_style_button(self, kind: int, *, spectrogram: bool = False) -> None:
        # Radar Fusion-style views live entirely in the combo — no Heatmap/Graph
        # twin buttons (range spectrum is its own dropdown entry).
        if self._radar_views:
            self._btn_native.setVisible(False)
            self._btn_graph.setVisible(False)
            self._view_combo.setVisible(True)
            self._toolbar.setVisible(True)
            return
        graphable = kind in _GRAPHABLE_KINDS and not spectrogram
        self._btn_native.setVisible(graphable)
        self._btn_graph.setVisible(graphable)
        self._toolbar.setVisible(graphable)
        if not graphable:
            return
        if kind == preview_pb2.PREVIEW_KIND_ORIENTATION:
            self._btn_native.setText("Cube")
            self._btn_native.setToolTip("Orientation cube (default)")
            self._btn_graph.setToolTip("Rolling |a| / |ω| graph")
        else:
            self._btn_native.setText("Heatmap")
            self._btn_native.setToolTip("Range-Doppler heatmap (default)")
            self._btn_graph.setToolTip("Range-profile graph")
        graph = self._style_for(kind) == "graph"
        self._style_group.blockSignals(True)
        self._btn_native.setChecked(not graph)
        self._btn_graph.setChecked(graph)
        self._style_group.blockSignals(False)

    def _on_style_id(self, button_id: int) -> None:
        key = _kind_style_key(self._kind)
        if key is None:
            return
        style = "graph" if button_id == 1 else "native"
        if self._kind_styles.get(key, "native") == style:
            return
        self._kind_styles[key] = style
        if self._on_style_changed is not None:
            self._on_style_changed(key, style)
        if self._last_frame is not None:
            self.apply_frame(self._last_frame)

    def apply_frame(self, frame: preview_pb2.PreviewFrame | None) -> None:
        if frame is None:
            # Keep the last painted frame; callers clear() when the source changes.
            if self._last_frame is None:
                self._show_only(self._empty)
                self._toolbar.setVisible(False)
            return
        self._last_frame = frame
        kind = frame.kind
        self._kind = kind
        spectrogram = bool(
            frame.HasField("matrix") and frame.matrix.row_axis == "time"
        )
        # Camera / non-radar payloads must never keep a leftover radar combo.
        if kind == preview_pb2.PREVIEW_KIND_IMAGE_THUMBNAIL and self._radar_views:
            self.set_radar_views(None)
        self._sync_style_button(kind, spectrogram=spectrogram)
        # Radar uses the combo for all views; never apply the old Heatmap/Graph style.
        style = "native" if self._radar_views else self._style_for(kind)

        if kind == preview_pb2.PREVIEW_KIND_IMAGE_THUMBNAIL and frame.HasField("image"):
            self._image.set_image(frame.image)
            self.set_timing_only(self._timing_only)
            self._show_only(self._image)
        elif kind == preview_pb2.PREVIEW_KIND_ORIENTATION and frame.HasField("orientation"):
            ori = frame.orientation
            self._accel_hist.append(float(ori.accel_magnitude))
            self._gyro_hist.append(float(ori.gyro_magnitude))
            if style == "graph":
                peak = max(
                    max(self._accel_hist, default=0.0),
                    max(self._gyro_hist, default=0.0),
                    1.0,
                )
                self._trace.set_channels(
                    [list(self._accel_hist), list(self._gyro_hist)],
                    names=["|a|", "|ω|"],
                    display_min=0.0,
                    display_max=peak,
                )
                self._show_only(self._trace)
            else:
                self._orient.set_orientation(ori)
                self._show_only(self._orient)
        elif kind == preview_pb2.PREVIEW_KIND_MATRIX_2D and frame.HasField("matrix"):
            if style == "graph" and not spectrogram:
                profile = _range_profile(frame.matrix)
                peak = max(profile) if profile else 1.0
                self._trace.set_channels(
                    [profile],
                    names=["range"],
                    display_min=0.0,
                    display_max=max(peak, 1e-6),
                )
                self._show_only(self._trace)
            else:
                self._matrix.set_matrix(frame.matrix)
                self._show_only(self._matrix)
        elif frame.HasField("trace"):
            self._trace.set_trace(frame.trace)
            self._show_only(self._trace)
        else:
            self._show_only(self._empty)
