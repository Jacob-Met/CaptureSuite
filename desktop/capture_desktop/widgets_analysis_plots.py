# SPDX-License-Identifier: GPL-3.0-only
"""In-app analysis figures — PyQtGraph sync dashboard and PNG gallery."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_job_comparison import JobParameterError, read_job_manifest
from .widgets_analysis_comparison import JobParameterBar
from .widgets_figure_export import FigureExportBar

try:
    import numpy as np
    import pyqtgraph as pg

    _HAS_PYQTGRAPH = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore
    pg = None  # type: ignore
    _HAS_PYQTGRAPH = False


def _hex_color(name: str, fallback: str) -> str:
    if name.startswith("#") and len(name) in (4, 7):
        return name
    return fallback


class SyncDashboardView(QWidget):
    """Interactive multi-lane sync dashboard (PyQtGraph)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._title = QLabel("Sync dashboard")
        self._title.setFont(theme.ui(9, bold=True))
        layout.addWidget(self._title)
        self._placeholder = QLabel("Run a features/plots job to populate the sync dashboard.")
        self._placeholder.setObjectName("Dim")
        self._placeholder.setWordWrap(True)
        layout.addWidget(self._placeholder)
        self._plot_host = QWidget()
        self._plot_layout = QVBoxLayout(self._plot_host)
        self._plot_layout.setContentsMargins(0, 0, 0, 0)
        self._plot_layout.setSpacing(4)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._plot_host)
        layout.addWidget(self._scroll, 1)
        self._linked: list = []
        self._support_range = None
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_support)

    def _fit_support(self) -> None:
        if self._linked and self._support_range is not None:
            self._linked[0].setXRange(*self._support_range, padding=0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._fit_timer.start(0)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_timer.start(0)

    def clear(self) -> None:
        self._placeholder.setVisible(True)
        self._title.setText("Sync dashboard")
        while self._plot_layout.count():
            item = self._plot_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._linked.clear()

    def load_json_path(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        return self.load_document(doc)

    def load_document(self, doc: dict) -> bool:
        if not _HAS_PYQTGRAPH:
            self._placeholder.setText(
                "Install pyqtgraph to view the interactive sync dashboard (pip install pyqtgraph)."
            )
            self._placeholder.setVisible(True)
            return False
        series = doc.get("series") or []
        if not series:
            return False
        self.clear()
        self._placeholder.setVisible(False)
        self._title.setText(str(doc.get("title") or "Sync dashboard"))
        window = doc.get("window") or {}
        timed = [row for row in series if row.get("t_ns")]
        if not timed:
            self._placeholder.setText("No recorded samples in this saved dashboard.")
            self._placeholder.setVisible(True)
            return False
        first = min(min(row["t_ns"]) for row in timed)
        last = max(max(row["t_ns"]) for row in timed)
        start_ns = int(window.get("startSessionNs", first))
        end_ns = int(window.get("endSessionNs", last))
        if end_ns <= start_ns:
            start_ns, end_ns = int(first), int(last)
        legacy = any("gaps" not in row for row in timed)
        if legacy and doc.get("gaps"):
            self._placeholder.setText(
                "Saved dashboard lacks lane-specific gap evidence. Rerun plots to inspect "
                "missing intervals; legacy points are shown without connecting lines."
            )
            self._placeholder.setVisible(True)
        accent = theme.ACCENT.name()
        text = theme.TEXT_DIM.name()
        border = theme.BORDER.name()
        pg.setConfigOptions(antialias=True, foreground=text, background=theme.PANEL_DEEP.name())
        prev_plot = None
        for idx, row in enumerate(timed):
            heading = QLabel(str(row.get("label") or f"lane {idx + 1}"))
            heading.setTextFormat(Qt.TextFormat.PlainText)
            heading.setWordWrap(True)
            heading.setFont(theme.ui(9, bold=True))
            self._plot_layout.addWidget(heading)
            plot = pg.PlotWidget()
            plot.setMinimumHeight(115)
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
            plot.setBackground(theme.PANEL_DEEP.name())
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setLabel("left", str(row.get("ylabel") or "units unspecified"))
            plot.getAxis("left").setWidth(80)
            if idx == len(timed) - 1:
                plot.setLabel("bottom", "session time (s)")
            else:
                plot.getAxis("bottom").setStyle(showValues=False)
            t_ns = np.asarray(row.get("t_ns") or [], dtype=np.int64)
            y = np.asarray(row.get("y") or [], dtype=np.float64)
            if y.shape != t_ns.shape:
                self.clear()
                self._placeholder.setText("Saved dashboard has mismatched timestamps and values.")
                return False
            lane_gaps = row.get("gaps") or []
            valid = np.isfinite(y) & (t_ns >= start_ns) & (t_ns <= end_ns)
            connected = t_ns[1:] > t_ns[:-1]
            for gap in lane_gaps:
                a = int(gap["startSessionNs"])
                b = int(gap["endSessionNs"]) if gap.get("endSessionNs") is not None else end_ns
                valid &= ~((t_ns >= a) & (t_ns <= b))
                connected &= ~((t_ns[:-1] <= b) & (t_ns[1:] >= a))
                x0, x1 = max(a, start_ns), min(b, end_ns)
                if x1 > x0:
                    region = pg.LinearRegionItem(
                        values=(x0 / 1e9, x1 / 1e9),
                        movable=False,
                        brush=pg.mkBrush((*theme.RED.getRgb()[:3], 40)),
                        pen=pg.mkPen(border, width=0),
                    )
                    plot.addItem(region)
            connected &= valid[:-1] & valid[1:]
            starts = np.flatnonzero(valid & np.r_[True, ~connected])
            ends = np.flatnonzero(valid & np.r_[~connected, True]) + 1
            color = _hex_color(str(row.get("color") or ""), accent)
            for a, b in zip(starts, ends, strict=True):
                uncertain = "gaps" not in row and bool(doc.get("gaps"))
                plot.plot(
                    t_ns[a:b] / 1e9,
                    y[a:b],
                    pen=None if uncertain else pg.mkPen(color, width=1.2),
                    symbol="o" if uncertain or b - a == 1 else None,
                    symbolSize=3,
                )
            if prev_plot is not None:
                plot.setXLink(prev_plot)
            self._support_range = (max(start_ns, first) / 1e9, min(end_ns, last) / 1e9)
            plot.setXRange(*self._support_range, padding=0)
            self._fit_timer.start(0)
            prev_plot = plot
            self._linked.append(plot)
            self._plot_layout.addWidget(plot, 1)
        return True


class FigureView(QScrollArea):
    """Show the entire saved figure first; preserve actual pixels on request."""

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._original = QPixmap(str(path))
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setWidget(self._image)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 34, 0, 0)
        self._tools = QWidget(self)
        bar = QHBoxLayout(self._tools)
        bar.setContentsMargins(8, 2, 8, 2)
        self._scale = QLabel()
        self._scale.setObjectName("Dim")
        self._actual = QPushButton("Actual size")
        self._actual.setCheckable(True)
        self._actual.setAccessibleName("Switch between fitted figure and actual size")
        self._actual.toggled.connect(self._render)
        bar.addWidget(self._scale, 1)
        bar.addWidget(self._actual)
        if self._original.isNull():
            self._image.setText(f"Could not load {path.name}")
            self._actual.setEnabled(False)
        self._render()

    def _render(self, *_args) -> None:
        if self._original.isNull():
            return
        actual = self._actual.isChecked()
        self.setWidgetResizable(not actual)
        if actual:
            self._image.setPixmap(self._original)
            self._image.resize(self._original.size())
            self._scale.setText("100% · scroll to inspect")
            self._actual.setText("Fit figure")
        else:
            size = self.viewport().size()
            if size.width() <= 8 or size.height() <= 8:
                return
            pixmap = self._original.scaled(
                size.width() - 8, size.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._image.setPixmap(pixmap)
            self._scale.setText(f"{pixmap.width() / self._original.width():.0%} · entire figure")
            self._actual.setText("Actual size")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._tools.setGeometry(0, 0, self.width(), 34)
        self._render()


class FigureGallery(QWidget):
    """Tabs for sync dashboard + static PNG figures from a job directory."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        head = QLabel("Figure gallery")
        head.setFont(theme.ui(9, bold=True))
        layout.addWidget(head)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        layout.addWidget(self._tabs, 1)
        self._sync = SyncDashboardView()
        self._tabs.addTab(self._sync, "Sync")
        self._figure_export = FigureExportBar(self)
        layout.addWidget(self._figure_export)

    def clear(self) -> None:
        self._figure_export.clear()
        while self._tabs.count() > 1:
            page = self._tabs.widget(1)
            self._tabs.removeTab(1)
            page.deleteLater()
        self._sync.clear()

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        self._figure_export.load_job_dir(job_dir)
        series_path = job_dir / "figures" / "sync_dashboard_series.json"
        if series_path.is_file():
            self._sync.load_json_path(series_path)
        figures_dir = job_dir / "figures"
        if not figures_dir.is_dir():
            return
        try:
            figures_root = figures_dir.resolve(strict=True)
        except (OSError, RuntimeError):
            return
        for png in sorted(figures_dir.rglob("*.png")):
            relative = png.relative_to(figures_dir)
            if relative == Path("sync_dashboard.png"):
                continue
            try:
                if not png.is_file() or not png.resolve(strict=True).is_relative_to(figures_root):
                    continue
            except (OSError, RuntimeError):
                continue
            parts = list(relative.with_suffix("").parts)
            parts[-1] = parts[-1].replace("_", " ")
            if (
                len(parts) == 4
                and parts[0] == "numeric"
                and parts[1].startswith("source-")
                and parts[2].startswith("stream-")
            ):
                try:
                    source = bytes.fromhex(parts[1][7:]).decode("utf-8")
                    stream = bytes.fromhex(parts[2][7:]).decode("utf-8")
                except (ValueError, UnicodeError):
                    pass
                else:
                    parts = [source, stream, parts[-1]]
            title = " / ".join(parts)
            if len(relative.parts) == 1:
                title = title[:24]
            scroll = FigureView(png)
            index = self._tabs.addTab(scroll, title)
            self._tabs.setTabToolTip(index, relative.as_posix())


class JobInspector(QWidget):
    """Job outputs + provenance from job_manifest.json."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        head = QLabel("Job inspector")
        head.setFont(theme.ui(9, bold=True))
        layout.addWidget(head)
        self._meta = QLabel("No job loaded")
        self._meta.setObjectName("Dim")
        self._meta.setWordWrap(True)
        self._meta.setFont(theme.mono(8))
        layout.addWidget(self._meta)
        self._parameters = JobParameterBar()
        layout.addWidget(self._parameters)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._outputs_host = QWidget()
        self._outputs_layout = QVBoxLayout(self._outputs_host)
        self._outputs_layout.setContentsMargins(0, 0, 0, 0)
        self._outputs_layout.addStretch(1)
        scroll.setWidget(self._outputs_host)
        layout.addWidget(scroll, 1)

    def clear(self) -> None:
        self._meta.setText("No job loaded")
        self._parameters.clear()
        while self._outputs_layout.count():
            item = self._outputs_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._outputs_layout.addStretch(1)

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        self._parameters.load_job_dir(job_dir)
        manifest_path = job_dir / "job_manifest.json"
        if not manifest_path.is_file():
            self._meta.setText(f"No job_manifest.json in {job_dir}")
            return
        try:
            manifest = read_job_manifest(job_dir)
        except (JobParameterError, OSError) as exc:
            self._meta.setText(f"manifest error: {exc}")
            return
        outputs = manifest.get("outputs") or []
        if not isinstance(outputs, list) or any(not isinstance(row, dict) for row in outputs):
            self._meta.setText("manifest error: invalid output inventory")
            return
        job_id = manifest.get("jobId", "?")
        status = manifest.get("status", "?")
        gap = manifest.get("gapPolicy", "?")
        plug = manifest.get("pluginManifestVersion", "?")
        self._meta.setText(
            f"job_id={job_id}\nstatus={status}\ngap_policy={gap}\n"
            f"plugin_manifest={plug}\npath={job_dir}"
        )
        self._outputs_layout.takeAt(self._outputs_layout.count() - 1)
        if not outputs:
            empty = QLabel("(no outputs recorded)")
            empty.setObjectName("Faint")
            self._outputs_layout.addWidget(empty)
        for row in outputs:
            rel = str(row.get("relativePath") or "")
            kind = str(row.get("kind") or "")
            sha = str(row.get("sha256") or "")[:12]
            lab = QLabel(f"[{kind}] {rel}\nsha256:{sha}…")
            lab.setObjectName("Dim")
            lab.setFont(theme.mono(8))
            lab.setWordWrap(True)
            self._outputs_layout.addWidget(lab)
        self._outputs_layout.addStretch(1)
