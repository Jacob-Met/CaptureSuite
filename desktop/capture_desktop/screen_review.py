# SPDX-License-Identifier: GPL-3.0-only
"""Read-only Review tab: package summary, gaps, checkpoints, export."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .review_events import checkpoint_time
from .state import CaptureState, fmt_time
from .widgets_review_events import ReviewEventBrowser
from .widgets_review_video import RecordedVideoReview


class ReviewScreen(QWidget):
    export_requested = Signal(str)  # package_path
    package_loaded = Signal(object)  # ReviewSummary or None

    def __init__(self, state: CaptureState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._package = ""
        self.summary = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("Review")
        title.setFont(theme.ui(14, bold=True))
        title_row = QHBoxLayout()
        title_row.addWidget(title, 1)
        self._btn_open = QPushButton("Open recorded session…")
        self._btn_open.setObjectName("ReviewOpenPackage")
        self._btn_open.clicked.connect(self._browse)
        title_row.addWidget(self._btn_open)
        root.addLayout(title_row)

        self._banner = QLabel("Open a finalized session to inspect recorded notes, gaps and video.")
        self._banner.setObjectName("HonestyBanner")
        self._banner.setWordWrap(True)
        self._banner.setFont(theme.ui(8))
        root.addWidget(self._banner)

        self._recovered_banner = QLabel("")
        self._recovered_banner.setObjectName("HonestyBanner")
        self._recovered_banner.setWordWrap(True)
        self._recovered_banner.setFont(theme.ui(8, bold=True))
        self._recovered_banner.setVisible(False)
        self._recovered_banner.setStyleSheet(f"color: {theme.ORANGE.name()};")
        root.addWidget(self._recovered_banner)

        cards = QHBoxLayout()
        self._card_session = QLabel("—")
        self._card_sources = QLabel("—")
        self._card_gaps = QLabel("—")
        self._card_checkpoints = QLabel("—")
        for label, widget in (
            ("Session", self._card_session),
            ("Sources", self._card_sources),
            ("Gaps", self._card_gaps),
            ("Checkpoints", self._card_checkpoints),
        ):
            box = QWidget()
            box.setObjectName("Card")
            col = QVBoxLayout(box)
            col.setContentsMargins(10, 8, 10, 8)
            head = QLabel(label)
            head.setObjectName("Faint")
            head.setFont(theme.ui(8))
            widget.setFont(theme.ui(11, bold=True))
            widget.setWordWrap(True)
            col.addWidget(head)
            col.addWidget(widget)
            cards.addWidget(box, 1)


        lists = QHBoxLayout()
        self._streams = QListWidget()
        self._gaps = QListWidget()
        self._checkpoints = QListWidget()
        for heading, widget in (
            ("Stream inventory", self._streams),
            ("Gaps", self._gaps),
            ("Checkpoints", self._checkpoints),
        ):
            col = QVBoxLayout()
            lab = QLabel(heading)
            lab.setFont(theme.ui(9, bold=True))
            col.addWidget(lab)
            col.addWidget(widget, 1)
            lists.addLayout(col, 1)
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.addLayout(cards)
        overview_layout.addLayout(lists, 1)
        self._review_tabs = QTabWidget()
        self._review_tabs.setObjectName("ReviewViews")
        self._review_tabs.addTab(overview, "Overview")
        self._events = ReviewEventBrowser()
        self._review_tabs.addTab(self._events, "Events")
        root.addWidget(self._review_tabs, 1)

        self._recorded_video = RecordedVideoReview()
        root.addWidget(self._recorded_video)

        actions = QHBoxLayout()
        self._btn_export = QPushButton("Export…")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._emit_export)
        self._path_label = QLabel("")
        self._path_label.setObjectName("Faint")
        self._path_label.setTextFormat(Qt.TextFormat.PlainText)
        self._path_label.setWordWrap(True)
        actions.addWidget(self._btn_export)
        actions.addWidget(self._path_label, 1)
        root.addLayout(actions)

    @property
    def package_path(self) -> str:
        return self._package

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Open recorded .mmsession package", self._package,
        )
        if path:
            self.load_package(path)

    def load_package(self, package_path: str, *, recovered: bool = False) -> None:
        self._recorded_video.reset("Loading package…")
        self._package = ""
        self.summary = None
        self.package_loaded.emit(None)
        self._path_label.setText(package_path)
        self._btn_export.setEnabled(False)
        self._events.clear()
        self._streams.clear()
        self._gaps.clear()
        self._checkpoints.clear()
        self._recovered_banner.hide()
        for card in (
            self._card_session, self._card_sources, self._card_gaps, self._card_checkpoints,
        ):
            card.setText("—")
        try:
            from capture_session import load_review_summary

            summary = load_review_summary(package_path)
            if summary.state not in {"finalized", "finalized_recovered"}:
                raise ValueError("Choose a finalized session. Stop recording or recover it first.")
            self._events.set_summary(summary)
        except Exception as exc:  # noqa: BLE001
            self._banner.setText(f"Could not load package: {exc}")
            return

        self._package = summary.package_path
        self.summary = summary
        self._btn_export.setEnabled(True)
        self._recorded_video.load_package(package_path, state=summary.state)

        recover_note = ""
        if recovered or summary.state == "finalized_recovered" or summary.recovery_reports:
            recover_note = " · recovered"
            self._recovered_banner.setText(
                "Recovered package — gaps and incomplete segments are explicit; "
                "do not treat as a clean capture."
            )
            self._recovered_banner.setVisible(True)
        else:
            self._recovered_banner.setVisible(False)
        self._banner.setText(
            f"State {summary.state}{recover_note}. "
            "Gaps are never hidden. Export writes continuous streams offline. "
            "Radar arrays are software-coordinated unless marked hardware-validated."
        )
        self._card_session.setText(
            f"{summary.session_id}\n{fmt_time(summary.duration_ns / 1e9)}"
        )
        self._card_sources.setText(str(len(summary.source_ids)))
        self._card_gaps.setText(
            f"{len(summary.gaps)} total\n"
            f"{summary.open_gap_count} open · {summary.closed_gap_count} closed"
        )
        self._card_checkpoints.setText(str(len(summary.checkpoints)))

        self._streams.clear()
        try:
            from capture_analysis.discover import discover_streams

            for ref in discover_streams(package_path):
                dims = "×".join(str(d) for d in ref.dimensions) if ref.dimensions else "—"
                units = ref.units or "—"
                segs = len(ref.mcap_paths) + len(ref.mkv_paths)
                text = (
                    f"{ref.source_id}/{ref.stream_id} · {ref.modality or '?'} · "
                    f"{ref.data_schema_id or 'no-schema'} · "
                    f"{ref.nominal_rate_hz:g} Hz · dims {dims} · units {units} · "
                    f"{segs} segment(s)"
                )
                self._streams.addItem(QListWidgetItem(text))
        except Exception as exc:  # noqa: BLE001
            self._streams.addItem(QListWidgetItem(f"(inventory unavailable: {exc})"))

        self._gaps.clear()
        for g in summary.gaps:
            end = (
                fmt_time(g.end_session_time_ns / 1e9)
                if g.end_session_time_ns is not None
                else "open"
            )
            text = (
                f"{g.source_id} · {g.cause} · "
                f"{fmt_time(g.start_session_time_ns / 1e9)} → {end}"
            )
            self._gaps.addItem(QListWidgetItem(text))
        self._checkpoints.clear()
        for cp in summary.checkpoints:
            name = cp.get("name") or cp.get("checkpointId") or "(unnamed)"
            ts, _basis = checkpoint_time(cp)
            time_label = f"{ts} ns" if ts is not None else "Unavailable time"
            self._checkpoints.addItem(QListWidgetItem(f"{time_label}  {name}"))
        self.package_loaded.emit(summary)

    def _emit_export(self) -> None:
        if self._package:
            self.export_requested.emit(self._package)

    def refresh_from_state(self) -> None:
        if self._state.package_path and self._state.review_mode:
            self.load_package(self._state.package_path)
