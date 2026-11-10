# SPDX-License-Identifier: GPL-3.0-only
"""In-app analysis figures — PyQtGraph sync dashboard and PNG gallery."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .analysis_job_comparison import JobParameterError, read_job_manifest
from .widgets_analysis_comparison import JobParameterBar
from .widgets_feature_export import FeatureExportBar
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
        layout.addWidget(self._plot_host, 1)
        self._linked: list = []

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
        t0 = min(int(min(row["t_ns"])) for row in series if row.get("t_ns"))
        t_end = int(window.get("endSessionNs") or max(int(max(row["t_ns"])) for row in series))
        gaps = doc.get("gaps") or []
        accent = theme.ACCENT.name()
        text = theme.TEXT_DIM.name()
        border = theme.BORDER.name()
        pg.setConfigOptions(antialias=True, foreground=text, background=theme.PANEL_DEEP.name())
        prev_plot = None
        for idx, row in enumerate(series):
            plot = pg.PlotWidget()
            plot.setBackground(theme.PANEL_DEEP.name())
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setLabel("left", str(row.get("label") or f"lane {idx + 1}"))
            if idx == len(series) - 1:
                plot.setLabel("bottom", "session time (s)")
            else:
                plot.getAxis("bottom").setStyle(showValues=False)
            t_ns = np.asarray(row.get("t_ns") or [], dtype=np.int64)
            y = np.asarray(row.get("y") or [], dtype=np.float64)
            if t_ns.size and y.size:
                t_s = (t_ns - t0) / 1e9
                color = _hex_color(str(row.get("color") or ""), accent)
                plot.plot(t_s, y, pen=pg.mkPen(color, width=1.2))
            for gap in gaps:
                start = gap.get("startSessionNs")
                if start is None:
                    continue
                end = gap.get("endSessionNs")
                if end is None:
                    end = t_end
                x0 = (int(start) - t0) / 1e9
                x1 = (int(end) - t0) / 1e9
                region = pg.LinearRegionItem(
                    values=(x0, x1),
                    movable=False,
                    brush=pg.mkBrush(theme.RED.name(), 40),
                    pen=pg.mkPen(border, width=0),
                )
                plot.addItem(region)
            if prev_plot is not None:
                plot.setXLink(prev_plot)
            prev_plot = plot
            self._linked.append(plot)
            self._plot_layout.addWidget(plot, 1)
        return True


class _StaticFigure(QScrollArea):
    """Fit a saved figure for reading, retaining the unmodified original for 100%."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.fit = True
        self._original = QPixmap(str(path))
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWidgetResizable(False)
        self.setWidget(self._image)
        if self._original.isNull():
            self._image.setText(f"Could not load {path.name}")
        self._render()

    def set_fit(self, fit: bool) -> None:
        self.fit = fit
        self._render()

    def _render(self) -> None:
        if self._original.isNull():
            return
        size = self.viewport().size()
        if self.fit and (size.width() < self._original.width()
                         or size.height() < self._original.height()):
            pixmap = self._original.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        else:
            pixmap = self._original
        self._image.setPixmap(pixmap)
        self._image.setFixedSize(pixmap.size())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render()


class FigureGallery(QWidget):
    """Tabs for sync dashboard + static PNG figures from a job directory."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout()
        head = QLabel("Figure gallery")
        head.setFont(theme.ui(9, bold=True))
        heading.addWidget(head)
        heading.addStretch(1)
        self._zoom = QComboBox()
        self._zoom.setAccessibleName("Figure viewing scale")
        self._zoom.addItem("Fit figure", True)
        self._zoom.addItem("Actual size (100%)", False)
        self._zoom.setToolTip("Viewing scale only; original figures and exports stay unchanged.")
        self._zoom.setVisible(False)
        heading.addWidget(self._zoom)
        layout.addLayout(heading)
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        layout.addWidget(self._tabs, 1)
        self._sync = SyncDashboardView()
        self._tabs.addTab(self._sync, "Sync")
        self._tabs.currentChanged.connect(self._sync_zoom)
        self._zoom.currentIndexChanged.connect(self._set_zoom)
        self._figure_export = FigureExportBar(self)
        layout.addWidget(self._figure_export)

    def _sync_zoom(self, *_args) -> None:
        page = self._tabs.currentWidget()
        self._zoom.setVisible(isinstance(page, _StaticFigure))
        if isinstance(page, _StaticFigure):
            self._zoom.blockSignals(True)
            self._zoom.setCurrentIndex(0 if page.fit else 1)
            self._zoom.blockSignals(False)

    def _set_zoom(self, *_args) -> None:
        page = self._tabs.currentWidget()
        if isinstance(page, _StaticFigure):
            page.set_fit(bool(self._zoom.currentData()))

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
            scroll = _StaticFigure(png)
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
        self._summary = QLabel("No saved result open")
        self._summary.setWordWrap(True)
        self._summary.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self._summary)
        self._meta = QLabel("No job loaded")
        self._meta.setObjectName("Dim")
        self._meta.setWordWrap(True)
        self._meta.setFont(theme.mono(8))
        self._meta.setTextFormat(Qt.TextFormat.PlainText)
        self._meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._meta.setVisible(False)
        layout.addWidget(self._meta)
        self._parameters = JobParameterBar()
        layout.addWidget(self._parameters)
        self._feature_export = FeatureExportBar(self)
        layout.addWidget(self._feature_export)
        self._provenance = QPushButton("Show provenance and files")
        self._provenance.setCheckable(True)
        layout.addWidget(self._provenance)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._outputs_host = QWidget()
        self._outputs_layout = QVBoxLayout(self._outputs_host)
        self._outputs_layout.setContentsMargins(0, 0, 0, 0)
        self._outputs_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self._outputs_layout.addStretch(1)
        scroll.setWidget(self._outputs_host)
        self._outputs_scroll = scroll
        self._outputs_scroll.setVisible(False)
        layout.addWidget(scroll, 1)
        self._empty_space = QWidget()
        layout.addWidget(self._empty_space, 1)
        self._provenance.toggled.connect(self._show_provenance)

    def _show_provenance(self, visible: bool) -> None:
        self._meta.setVisible(visible)
        self._outputs_scroll.setVisible(visible)
        self._empty_space.setVisible(not visible)

    def clear(self) -> None:
        self._summary.setText("No saved result open")
        self._provenance.setChecked(False)
        self._provenance.setEnabled(False)
        self._meta.setText("No job loaded")
        self._parameters.clear()
        self._feature_export.clear()
        while self._outputs_layout.count():
            item = self._outputs_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._outputs_layout.addStretch(1)

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        self._parameters.load_job_dir(job_dir)
        self._feature_export.load_job_dir(job_dir)
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
        self._summary.setText(
            f"{job_id}\n{str(status).replace('_', ' ').capitalize()} · gap policy: {gap}"
        )
        self._provenance.setEnabled(True)
        self._provenance.setText(f"Provenance and files ({len(outputs)})")
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
