# SPDX-License-Identifier: GPL-3.0-only
"""Shared session timeline for live capture and sealed review."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import theme
from .state import CaptureState, fmt_time


@dataclass
class TimelineGap:
    source_id: str
    start_s: float
    end_s: float | None
    closed: bool


@dataclass
class TimelineCheckpoint:
    time_s: float
    name: str


@dataclass
class TimelineModel:
    duration_s: float
    playhead_s: float
    lanes: list[tuple[str, str, str]] = field(default_factory=list)
    """(source_id, label, kind_key) per lane."""
    gaps: list[TimelineGap] = field(default_factory=list)
    checkpoints: list[TimelineCheckpoint] = field(default_factory=list)
    sync_anchors_s: list[float] = field(default_factory=list)
    empty_message: str = "No session timeline data"


def timeline_from_capture_state(state: CaptureState) -> TimelineModel:
    sources = state.selected_sources()
    if not sources and state.sources:
        sources = [s for s in state.sources if s.enabled][:8]
    duration = max(60.0, state.elapsed_s * 1.08, 1.0)
    lanes = [(s.source_id, s.alias[:18], s.kind_key) for s in sources]
    gaps: list[TimelineGap] = []
    for src in sources:
        for gap in state.gaps_for(src.source_id):
            start = gap.start_session_time_ns / 1e9
            end = (
                gap.end_session_time_ns / 1e9
                if gap.end_session_time_ns is not None
                else state.elapsed_s
            )
            gaps.append(
                TimelineGap(
                    source_id=src.source_id,
                    start_s=start,
                    end_s=end,
                    closed=gap.closed,
                )
            )
        snap = state.health.get(src.source_id)
        if snap and snap.HasField("open_gap"):
            start = snap.open_gap.start_session_time_ns / 1e9
            gaps.append(
                TimelineGap(
                    source_id=src.source_id,
                    start_s=start,
                    end_s=None,
                    closed=False,
                )
            )
    checkpoints = [
        TimelineCheckpoint(
            time_s=cp.effective_timestamp_ns / 1e9,
            name=cp.name or cp.checkpoint_id,
        )
        for cp in state.checkpoints
    ]
    sync_anchors = [sync.timestamp_ns / 1e9 for sync in state.sync_anchors]
    empty = "No sources selected" if not lanes else ""
    return TimelineModel(
        duration_s=duration,
        playhead_s=state.elapsed_s,
        lanes=lanes,
        gaps=gaps,
        checkpoints=checkpoints,
        sync_anchors_s=sync_anchors,
        empty_message=empty or "No session timeline data",
    )


def timeline_from_review_summary(summary) -> TimelineModel:
    duration = max(1.0, summary.duration_ns / 1e9)
    lanes = [
        (sid, sid.split(".")[-1][:18], _kind_from_source_id(sid))
        for sid in summary.source_ids
    ]
    gaps = [
        TimelineGap(
            source_id=g.source_id,
            start_s=g.start_session_time_ns / 1e9,
            end_s=(
                g.end_session_time_ns / 1e9 if g.end_session_time_ns is not None else duration
            ),
            closed=g.closed,
        )
        for g in summary.gaps
    ]
    checkpoints = []
    for cp in summary.checkpoints:
        ts = int(cp.get("effectiveTimestampNs") or cp.get("originalTimestampNs") or 0)
        name = str(cp.get("name") or cp.get("checkpointId") or "(unnamed)")
        checkpoints.append(TimelineCheckpoint(time_s=ts / 1e9, name=name))
    sync_anchors = []
    for row in summary.sync_anchors:
        ts = int(row.get("timestampNs") or row.get("timestamp_ns") or 0)
        if ts:
            sync_anchors.append(ts / 1e9)
    return TimelineModel(
        duration_s=duration,
        playhead_s=0.0,
        lanes=lanes,
        gaps=gaps,
        checkpoints=checkpoints,
        sync_anchors_s=sync_anchors,
        empty_message="No sources in package",
    )


def _kind_from_source_id(source_id: str) -> str:
    if source_id.startswith("sim.emg") or ".emg." in source_id:
        return "emg"
    if source_id.startswith("sim.imu") or ".imu." in source_id:
        return "imu"
    if source_id.startswith("sim.radar") or source_id.startswith("radar."):
        return "radar"
    if "camera" in source_id or "video" in source_id:
        return "camera"
    return "mixed"


class SessionTimelineWidget(QWidget):
    """Multi-lane session clock with gaps, checkpoints, and playhead."""

    scrubbed = Signal(float)  # session time seconds

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = TimelineModel(duration_s=60.0, playhead_s=0.0)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setToolTip("Session timeline — gaps in red, checkpoints in accent")

    def set_model(self, model: TimelineModel) -> None:
        self._model = model
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, theme.PANEL_DEEP)
        model = self._model
        if not model.lanes:
            painter.setPen(theme.TEXT_FAINT)
            painter.setFont(theme.ui(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, model.empty_message)
            return

        gutter = 96
        ruler = 24
        lane_h = 22
        lane_gap = 6
        window = max(1.0, model.duration_s)
        plot_l = rect.left() + gutter
        plot_r = rect.right() - 12
        plot_w = max(1.0, plot_r - plot_l)

        painter.setPen(theme.TEXT_FAINT)
        painter.setFont(theme.mono(8))
        for frac in (0.0, 0.5, 1.0):
            x = plot_l + plot_w * frac
            t = window * frac
            painter.drawText(int(x - 20), rect.top() + 14, fmt_time(t)[-5:])
            painter.setPen(theme.dim(theme.BORDER, 120))
            painter.drawLine(int(x), rect.top() + ruler, int(x), rect.bottom() - 6)
            painter.setPen(theme.TEXT_FAINT)

        gaps_by_source: dict[str, list[TimelineGap]] = {}
        for gap in model.gaps:
            gaps_by_source.setdefault(gap.source_id, []).append(gap)

        y = rect.top() + ruler + 2
        painter.setFont(theme.ui(8))
        for source_id, label, kind_key in model.lanes:
            color = theme.LANE_COLORS.get(kind_key, theme.GREEN)
            painter.setPen(theme.TEXT_DIM)
            painter.drawText(rect.left() + 8, y + 15, label)
            lane = QRectF(plot_l, y, plot_w, lane_h)
            painter.setBrush(theme.dim(color, 50))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(lane, 3, 3)
            fill_w = plot_w * min(1.0, model.playhead_s / window)
            painter.setBrush(theme.dim(color, 140))
            painter.drawRoundedRect(lane.adjusted(0, 0, fill_w - plot_w, 0), 3, 3)
            for gap in gaps_by_source.get(source_id, []):
                gx = plot_l + plot_w * (gap.start_s / window)
                end_s = gap.end_s if gap.end_s is not None else model.playhead_s
                gw = max(4.0, plot_w * max(0.008, (end_s - gap.start_s) / window))
                alpha = 160 if gap.closed else 220
                painter.setBrush(theme.dim(theme.RED, alpha))
                painter.drawRect(int(gx), int(y), int(min(gw, plot_r - gx)), lane_h)
            painter.setBrush(theme.ACCENT)
            for cp in model.checkpoints:
                cx = plot_l + plot_w * (cp.time_s / window)
                if plot_l <= cx <= plot_r:
                    painter.drawRect(int(cx), int(y), 2, lane_h)
            painter.setBrush(theme.ORANGE)
            for sync_s in model.sync_anchors_s:
                cx = plot_l + plot_w * (sync_s / window)
                if plot_l <= cx <= plot_r:
                    painter.drawRect(int(cx), int(y), 2, lane_h)
            if model.playhead_s > 0:
                px = plot_l + plot_w * min(1.0, model.playhead_s / window)
                painter.setPen(theme.TEXT)
                painter.drawLine(int(px), int(y), int(px), int(y + lane_h))
            y += lane_h + lane_gap

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._model.lanes or self._model.duration_s <= 0:
            return
        gutter = 96
        plot_l = self.rect().left() + gutter
        plot_r = self.rect().right() - 12
        plot_w = max(1.0, plot_r - plot_l)
        x = event.position().x()
        if x < plot_l or x > plot_r:
            return
        frac = (x - plot_l) / plot_w
        self.scrubbed.emit(max(0.0, min(self._model.duration_s, frac * self._model.duration_s)))
