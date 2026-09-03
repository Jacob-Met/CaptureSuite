# SPDX-License-Identifier: GPL-3.0-only
"""In-app analysis figures — PyQtGraph sync dashboard and PNG gallery."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QLabel,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme

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
                "Install pyqtgraph to view the interactive sync dashboard "
                "(pip install pyqtgraph)."
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

    def clear(self) -> None:
        while self._tabs.count() > 1:
            self._tabs.removeTab(1)
        self._sync.clear()

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        series_path = job_dir / "figures" / "sync_dashboard_series.json"
        if series_path.is_file():
            self._sync.load_json_path(series_path)
        figures_dir = job_dir / "figures"
        if not figures_dir.is_dir():
            return
        for png in sorted(figures_dir.glob("*.png")):
            if png.name == "sync_dashboard.png":
                continue
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            img = QLabel()
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(png))
            if not pix.isNull():
                img.setPixmap(pix)
            else:
                img.setText(f"Could not load {png.name}")
            scroll.setWidget(img)
            self._tabs.addTab(scroll, png.stem.replace("_", " ")[:24])


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
        while self._outputs_layout.count():
            item = self._outputs_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._outputs_layout.addStretch(1)

    def load_job_dir(self, job_dir: Path) -> None:
        self.clear()
        manifest_path = job_dir / "job_manifest.json"
        if not manifest_path.is_file():
            self._meta.setText(f"No job_manifest.json in {job_dir}")
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            self._meta.setText(f"manifest error: {exc}")
            return
        job_id = manifest.get("jobId", "?")
        status = manifest.get("status", "?")
        gap = manifest.get("gapPolicy", "?")
        plug = manifest.get("pluginManifestVersion", "?")
        self._meta.setText(
            f"job_id={job_id}\nstatus={status}\ngap_policy={gap}\n"
            f"plugin_manifest={plug}\npath={job_dir}"
        )
        outputs = manifest.get("outputs") or []
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
