# SPDX-License-Identifier: GPL-3.0-only
"""Read-only Review tab: package summary, gaps, checkpoints, export."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .state import CaptureState, fmt_time


class ReviewScreen(QWidget):
    export_requested = Signal(str)  # package_path

    def __init__(self, state: CaptureState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._package = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("Review")
        title.setFont(theme.ui(14, bold=True))
        root.addWidget(title)

        self._banner = QLabel("Open a finalized session to review gaps and export.")
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
        root.addLayout(cards)

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
        root.addLayout(lists, 1)

        actions = QHBoxLayout()
        self._btn_export = QPushButton("Export…")
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._emit_export)
        self._path_label = QLabel("")
        self._path_label.setObjectName("Faint")
        self._path_label.setWordWrap(True)
        actions.addWidget(self._btn_export)
        actions.addWidget(self._path_label, 1)
        root.addLayout(actions)

    def load_package(self, package_path: str, *, recovered: bool = False) -> None:
        self._package = package_path
        self._path_label.setText(package_path)
        self._btn_export.setEnabled(bool(package_path))
        try:
            from capture_session import load_review_summary

            summary = load_review_summary(package_path)
        except Exception as exc:  # noqa: BLE001
            self._banner.setText(f"Could not load package: {exc}")
            return

        recover_note = ""
        if recovered or summary.recovery_reports:
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
            ts = int(cp.get("effectiveTimestampNs") or cp.get("originalTimestampNs") or 0)
            self._checkpoints.addItem(
                QListWidgetItem(f"{fmt_time(ts / 1e9)}  {name}")
            )

    def _emit_export(self) -> None:
        if self._package:
            self.export_requested.emit(self._package)

    def refresh_from_state(self) -> None:
        if self._state.package_path and self._state.review_mode:
            self.load_package(self._state.package_path)
