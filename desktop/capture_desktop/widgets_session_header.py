# SPDX-License-Identifier: GPL-3.0-only
"""Persistent session chrome shared across Capture, Review, and Analysis."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme
from .state import CaptureState
from .widgets_analysis_scope import AnalysisScopePicker, ScopeSelection, seconds_text
from .widgets_session_timeline import (
    SessionTimelineWidget,
    TimelineModel,
    timeline_from_capture_state,
    timeline_from_review_summary,
)

_CURRENT_SELECTION = object()


class SessionHeader(QWidget):
    """Session identity + timeline when a package is active (live or sealed)."""

    scope_changed = Signal(str, object)  # resolved package path, ScopeSelection or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SessionHeader")
        self._visible = False
        self.package_path = ""
        self.is_sealed = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 6, 12, 6)
        outer.setSpacing(4)

        row = QHBoxLayout()
        self._session_line = QLabel("No session")
        self._session_line.setFont(theme.ui(10, bold=True))
        self._status_chip = QLabel("")
        self._status_chip.setFont(theme.mono(9, bold=True))
        self._scope = QLabel("Scope: full session")
        self._scope.setObjectName("Dim")
        self._scope.setFont(theme.ui(8))
        self._cursor = QLabel("")
        self._cursor.setFont(theme.mono(8))
        row.addWidget(self._session_line)
        row.addSpacing(12)
        row.addWidget(self._status_chip)
        row.addStretch(1)
        row.addWidget(self._cursor)
        row.addWidget(self._scope)
        outer.addLayout(row)

        self._timeline = SessionTimelineWidget()
        self._timeline.scrubbed.connect(self._on_scrubbed)
        outer.addWidget(self._timeline)
        self._scope_picker = AnalysisScopePicker()
        self._scope_picker.selection_changed.connect(self._on_scope_changed)
        outer.addWidget(self._scope_picker)
        self.setVisible(False)

    def refresh_live(self, state: CaptureState) -> None:
        self.is_sealed = False
        self._scope_picker.hide()
        self._cursor.clear()
        self._scope.setText("Live session")
        active = bool(state.package_path or state.session_id)
        self.setVisible(active)
        if not active:
            return
        sid = state.session_id or "—"
        path = state.package_path or ""
        tail = path.replace("\\", "/").split("/")[-1] if path else ""
        self._session_line.setText(
            f"Session {sid}" + (f"  ·  {tail}" if tail else "")
        )
        status = state.session_state_name()
        if state.review_mode:
            status = "sealed" if status == "finalized" else status
        chip_color = theme.TEXT_DIM
        if state.recording:
            chip_color = theme.RED
        elif state.rehearsal_active:
            chip_color = theme.ACCENT
        elif status in ("finalized_recovered", "recovering"):
            chip_color = theme.ORANGE
        self._status_chip.setText(status.upper())
        self._status_chip.setStyleSheet(f"color: {chip_color.name()};")
        self._timeline.set_model(timeline_from_capture_state(state))

    def refresh_sealed(
        self, summary, *, recovered: bool = False,
        selection: ScopeSelection | None | object = _CURRENT_SELECTION,
    ) -> None:
        path = str(Path(summary.package_path).resolve())
        same_package = path == self.package_path
        playhead = self._timeline._model.playhead_s if same_package else 0.0
        if selection is _CURRENT_SELECTION:
            selection = self._scope_picker.selection if same_package else ScopeSelection()
        self.package_path = path
        self.is_sealed = True
        self.setVisible(True)
        sid = summary.session_id or "—"
        self._session_line.setText(f"Session {sid}  ·  sealed package")
        state_label = summary.state
        if recovered or summary.recovery_reports:
            state_label = "finalized_recovered"
        self._status_chip.setText(state_label.upper())
        color = theme.ORANGE if "recover" in state_label else theme.GREEN
        self._status_chip.setStyleSheet(f"color: {color.name()};")
        self._timeline.set_model(timeline_from_review_summary(summary))
        self._scope_picker.show()
        self._scope_picker.set_summary(summary, selection)
        self._on_scrubbed(playhead)

    def _on_scope_changed(self, selection: ScopeSelection | None) -> None:
        self._scope.setText("Scope: " + (selection.describe() if selection else "invalid bounds"))
        self._timeline.set_selection(
            selection.start_ns / 1e9 if selection and selection.start_ns is not None else None,
            selection.end_ns / 1e9 if selection and selection.end_ns is not None else None,
        )
        if self.is_sealed:
            self.scope_changed.emit(self.package_path, selection)

    def _on_scrubbed(self, seconds: float) -> None:
        if not self.is_sealed:
            return
        nanoseconds = round(seconds * 1e9)
        self._timeline.set_playhead(seconds)
        self._scope_picker.set_cursor(nanoseconds)
        self._cursor.setText(f"Cursor {seconds_text(nanoseconds)} s")

    def clear(self) -> None:
        self.package_path = ""
        self.is_sealed = False
        self.setVisible(False)
        self._session_line.setText("No session")
        self._status_chip.setText("")
        self._cursor.clear()
        self._timeline.set_model(TimelineModel(duration_s=60.0, playhead_s=0.0))
