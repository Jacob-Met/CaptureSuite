# SPDX-License-Identifier: GPL-3.0-only
"""Persistent session chrome shared across Capture, Review, and Analysis."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme
from .state import CaptureState
from .widgets_session_timeline import (
    SessionTimelineWidget,
    TimelineModel,
    timeline_from_capture_state,
    timeline_from_review_summary,
)


class SessionHeader(QWidget):
    """Session identity + timeline when a package is active (live or sealed)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SessionHeader")
        self._visible = False
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
        row.addWidget(self._session_line)
        row.addSpacing(12)
        row.addWidget(self._status_chip)
        row.addStretch(1)
        row.addWidget(self._scope)
        outer.addLayout(row)

        self._timeline = SessionTimelineWidget()
        outer.addWidget(self._timeline)
        self.setVisible(False)

    def refresh_live(self, state: CaptureState) -> None:
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

    def refresh_sealed(self, summary, *, recovered: bool = False) -> None:
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

    def clear(self) -> None:
        self.setVisible(False)
        self._session_line.setText("No session")
        self._status_chip.setText("")
        self._timeline.set_model(TimelineModel(duration_s=60.0, playhead_s=0.0))
