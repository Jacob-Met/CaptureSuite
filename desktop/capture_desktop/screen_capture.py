# SPDX-License-Identifier: GPL-3.0-only
"""Capture screen: source rail, Timeline/Focus/Grid centre, right dock."""

from __future__ import annotations

from capture_protocol.generated.capture.v1 import health_pb2
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .persistence import DesktopPersistence
from .state import CaptureState, CheckpointRow, SourceRow, fmt_bytes, fmt_rate, fmt_time
from .widgets_modality_expanded import expanded_detail_lines, expanded_honesty_footer
from .widgets_preview import (
    RADAR_FMCW_VIEWS,
    RADAR_LTR11_VIEWS,
    PreviewHost,
    ScalarSparkline,
)


def panel(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Panel")
    body = QVBoxLayout(frame)
    body.setContentsMargins(8, 8, 8, 8)
    body.setSpacing(6)
    if title:
        label = QLabel(title)
        label.setObjectName("PanelTitle")
        label.setFont(theme.ui(9, bold=True))
        body.addWidget(label)
    return frame, body


class StatusDot(QWidget):
    def __init__(self, diameter: int = 9, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = theme.GREEN
        self.setFixedSize(diameter + 2, diameter + 2)

    def set_status(self, status: str) -> None:
        color = theme.STATUS_COLORS.get(status, theme.TEXT_FAINT)
        if color != self._color:
            self._color = color
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(theme.dim(self._color, 60))
        painter.drawEllipse(self.rect())
        painter.setBrush(self._color)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))


class RailRow(QFrame):
    clicked = Signal(str)
    toggled = Signal(str)

    def __init__(self, source: SourceRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_id = source.source_id
        self._selected_focus = False
        self._enabled = source.selected
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)
        self._dot = StatusDot(8)
        self._alias = QLabel(source.alias)
        self._alias.setFont(theme.ui(9))
        self._badge = QLabel("")
        self._badge.setObjectName("Faint")
        self._badge.setFont(theme.ui(7, bold=True))
        self._badge.setFixedWidth(42)
        color = theme.LANE_COLORS.get(source.kind_key, theme.GREEN)
        self._spark = ScalarSparkline(color)
        self._rate = QLabel("--")
        self._rate.setObjectName("Dim")
        self._rate.setFont(theme.mono(8))
        self._rate.setFixedWidth(46)
        self._rate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._dot)
        layout.addWidget(self._alias, 1)
        layout.addWidget(self._badge)
        layout.addWidget(self._spark)
        layout.addWidget(self._rate)

    def set_focus_selected(self, selected: bool) -> None:
        self._selected_focus = selected
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self.toggled.emit(self._source_id)
        else:
            self.clicked.emit(self._source_id)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._selected_focus:
            painter.setBrush(theme.dim(theme.ACCENT, 42))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())
            painter.setBrush(theme.ACCENT)
            painter.drawRect(0, 0, 3, self.height())
        if not self._enabled:
            painter.setBrush(theme.dim(theme.BG, 120))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())

    def refresh(self, state: CaptureState) -> None:
        src = state.by_id(self._source_id)
        if src is None:
            return
        self._enabled = src.source_id in state.selected_ids
        status = state.health_status(self._source_id)
        self._dot.set_status(status if self._enabled else "disabled")
        self._alias.setStyleSheet(
            f"color: {(theme.TEXT if self._enabled else theme.TEXT_FAINT).name()};"
        )
        snap = state.health.get(self._source_id)
        badge = ""
        tip = src.alias
        if self._enabled:
            if snap is not None and not snap.connected:
                badge = "NO DATA"
            elif state.has_open_gap(self._source_id):
                badge = "GAP"
            elif any(g.source_id == self._source_id for g in state.gaps):
                badge = "N GAP"
            if snap is not None and snap.HasField("last_error") and snap.last_error.message:
                tip = f"{src.alias}\n{snap.last_error.code}: {snap.last_error.message}"
        self._badge.setText(badge)
        self._badge.setStyleSheet(
            f"color: {(theme.RED if badge in ('NO DATA', 'GAP') else theme.TEXT_FAINT).name()};"
        )
        self.setToolTip(tip)
        if snap and snap.connected:
            self._rate.setText(f"{snap.measured_rate_hz:,.0f}")
        else:
            self._rate.setText("--")
        frame = state.previews.get(self._source_id)
        if frame is not None and frame.HasField("trace") and frame.trace.samples:
            ppc = max(1, int(frame.trace.points_per_channel))
            self._spark.set_values(list(frame.trace.samples[:ppc]))
        elif snap is not None:
            level = min(1.0, snap.measured_rate_hz / max(1.0, snap.expected_rate_hz or 1.0))
            prev = getattr(self, "_activity", [0.0] * 32)
            prev = (prev + [level])[-32:]
            self._activity = prev
            self._spark.set_values(prev)


class SourceCard(QFrame):
    clicked = Signal(str)

    def __init__(self, source: SourceRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._source_id = source.source_id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)
        header = QHBoxLayout()
        self._dot = StatusDot()
        title = QLabel(source.alias)
        title.setObjectName("CardTitle")
        badge_text = source.kind_key
        if source.is_virtual_camera:
            badge_text = f"{badge_text} · virtual"
        self._badge = QLabel(badge_text)
        self._badge.setObjectName("Faint")
        self._badge.setFont(theme.ui(8))
        header.addWidget(self._dot)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._badge)
        layout.addLayout(header)
        self._preview = PreviewHost()
        self._preview.set_color(theme.LANE_COLORS.get(source.kind_key, theme.GREEN))
        self._preview.set_timing_only(source.timing_only)
        self._preview.setMinimumHeight(110)
        layout.addWidget(self._preview, 1)
        self._metrics = QLabel("")
        self._metrics.setObjectName("Dim")
        self._metrics.setFont(theme.ui(8))
        layout.addWidget(self._metrics)
        self.setMinimumHeight(190)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.clicked.emit(self._source_id)

    def refresh(self, state: CaptureState) -> None:
        src = state.by_id(self._source_id)
        if src is None:
            return
        self._dot.set_status(state.health_status(self._source_id))
        self._preview.set_timing_only(src.timing_only)
        # Grid tiles never show the radar Fusion combo.
        self._preview.set_radar_views(None)
        frame = state.previews.get(self._source_id)
        if frame is not None:
            self._preview.apply_frame(frame)
        snap = state.health.get(self._source_id)
        if snap and snap.connected:
            self._metrics.setText(
                f"{fmt_rate(snap.measured_rate_hz)}  ·  {snap.dropped_count} dropped"
                f"  ·  {'write OK' if snap.write_ok else 'WRITE FAIL'}"
            )
        else:
            self._metrics.setText("no data arriving")


class FocusPanel(QWidget):
    radar_view_changed = Signal(str, str)  # source_id, preview_view

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_id = ""
        self._radar_views_bound = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self._dot = StatusDot()
        self._title = QLabel("")
        self._title.setFont(theme.ui(11, bold=True))
        self._status = QLabel("")
        self._status.setObjectName("Dim")
        header.addWidget(self._dot)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._status)
        layout.addLayout(header)
        self._preview = PreviewHost()
        self._preview.radar_view_changed.connect(self._on_radar_view)
        layout.addWidget(self._preview, 1)
        self._expanded = QLabel("")
        self._expanded.setObjectName("Dim")
        self._expanded.setFont(theme.mono(9))
        self._expanded.setWordWrap(True)
        self._expanded.setStyleSheet(
            f"background: {theme.PANEL_ALT.name()}; padding: 6px 8px;"
            f"border: 1px solid {theme.BORDER.name()};"
        )
        layout.addWidget(self._expanded)
        self._meta = QLabel("")
        self._meta.setObjectName("Dim")
        self._meta.setFont(theme.mono(9))
        self._meta.setWordWrap(True)
        layout.addWidget(self._meta)

    def set_source(self, source_id: str) -> None:
        if source_id != self._source_id:
            self._preview.set_radar_views(None)
            self._preview.clear()
            self._radar_views_bound = ""
        self._source_id = source_id

    def _on_radar_view(self, view: str) -> None:
        if self._source_id and self._source_id.startswith("radar."):
            self.radar_view_changed.emit(self._source_id, view)

    def refresh(self, state: CaptureState) -> None:
        src = state.by_id(self._source_id)
        if src is None:
            self._title.setText("No source")
            self._preview.set_radar_views(None)
            self._preview.clear()
            self._radar_views_bound = ""
            self._expanded.clear()
            return
        self._title.setText(f"{src.alias}  —  expanded")
        self._dot.set_status(state.health_status(src.source_id))
        self._preview.set_color(theme.LANE_COLORS.get(src.kind_key, theme.GREEN))
        self._preview.set_timing_only(src.timing_only)
        modality = (src.modality or "").lower()
        # Only real ifx boards — sim.radar.* also use modality "radar".
        if src.is_hardware_radar:
            views = (
                RADAR_LTR11_VIEWS
                if modality == "radar_doppler"
                else RADAR_FMCW_VIEWS
            )
            bind_key = f"{src.source_id}:{modality}"
            if bind_key != self._radar_views_bound:
                default = (
                    "motion_trace"
                    if modality == "radar_doppler"
                    else "range_doppler"
                )
                self._preview.set_radar_views(views, default)
                self._radar_views_bound = bind_key
        elif self._radar_views_bound:
            self._preview.set_radar_views(None)
            self._radar_views_bound = ""
        frame = state.previews.get(src.source_id)
        if frame is not None:
            self._preview.apply_frame(frame)
        snap = state.health.get(src.source_id)
        if snap:
            self._status.setText(
                f"{'connected' if snap.connected else 'DISCONNECTED'}"
                f"  ·  data {'arriving' if snap.data_arriving else 'idle'}"
            )
            self._meta.setText(
                f"Measured {fmt_rate(snap.measured_rate_hz)}   "
                f"Nominal {fmt_rate(snap.expected_rate_hz or src.nominal_rate_hz)}\n"
                f"Dropped {snap.dropped_count} ({snap.dropped_last_10s} /10s)   "
                f"Gaps {snap.gap_count}   "
                f"Segment {snap.current_segment or '—'}\n"
                f"Serial {src.serial or '—'}   Firmware {src.firmware or '—'}"
                + (
                    "\nrecording timing only (encode later)"
                    if src.timing_only
                    else ""
                )
            )
        else:
            self._status.setText("awaiting health")
            self._meta.setText(f"Type {src.source_type}  ·  {src.modality or '—'}")
        detail = expanded_detail_lines(src, state)
        detail.append(expanded_honesty_footer(src))
        self._expanded.setText("\n".join(detail))


class TimelinePanel(QWidget):
    """Simple multi-lane timeline from session view + health."""

    picked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state: CaptureState | None = None
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def refresh(self, state: CaptureState) -> None:
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.setBrush(theme.PANEL_DEEP)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        state = self._state
        if state is None:
            return
        sources = state.selected_sources()
        if not sources:
            painter.setPen(theme.TEXT_FAINT)
            painter.setFont(theme.ui(9))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No sources selected")
            return

        gutter = 96
        ruler = 28
        lane_h = 26
        lane_gap = 8
        window = max(60.0, state.elapsed_s * 1.08, 1.0)
        plot_l = rect.left() + gutter
        plot_r = rect.right() - 14
        plot_w = max(1.0, plot_r - plot_l)

        painter.setPen(theme.TEXT_FAINT)
        painter.setFont(theme.mono(8))
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            x = plot_l + plot_w * frac
            t = window * frac
            painter.drawText(int(x - 20), rect.top() + 16, fmt_time(t)[-5:])
            painter.setPen(theme.dim(theme.BORDER, 120))
            painter.drawLine(int(x), rect.top() + ruler, int(x), rect.bottom() - 8)
            painter.setPen(theme.TEXT_FAINT)

        y = rect.top() + ruler + 4
        painter.setFont(theme.ui(8))
        for src in sources:
            color = theme.LANE_COLORS.get(src.kind_key, theme.GREEN)
            painter.setPen(theme.TEXT_DIM)
            painter.drawText(rect.left() + 8, y + 16, src.alias[:14])
            lane = QRectF(plot_l, y, plot_w, lane_h)
            painter.setBrush(theme.dim(color, 50))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(lane, 3, 3)
            # Progress fill to elapsed
            fill_w = plot_w * min(1.0, state.elapsed_s / window)
            painter.setBrush(theme.dim(color, 140))
            painter.drawRoundedRect(lane.adjusted(0, 0, fill_w - plot_w, 0), 3, 3)
            # Closed + open gaps from session view / live GapEvent.
            for gap in state.gaps_for(src.source_id):
                start = gap.start_session_time_ns / 1e9
                end = (
                    gap.end_session_time_ns / 1e9
                    if gap.end_session_time_ns is not None
                    else state.elapsed_s
                )
                gx = plot_l + plot_w * (start / window)
                gw = max(4.0, plot_w * max(0.01, (end - start) / window))
                painter.setBrush(theme.dim(theme.RED, 160 if gap.closed else 220))
                painter.drawRect(int(gx), int(y), int(min(gw, plot_r - gx)), lane_h)
            snap = state.health.get(src.source_id)
            if snap and snap.HasField("open_gap"):
                gap = snap.open_gap
                start = gap.start_session_time_ns / 1e9
                gx = plot_l + plot_w * (start / window)
                painter.setBrush(theme.dim(theme.RED, 220))
                painter.drawRect(int(gx), int(y), max(4, int(plot_w * 0.02)), lane_h)
            # Checkpoints
            painter.setBrush(theme.ACCENT)
            for cp in state.checkpoints:
                cx = plot_l + plot_w * ((cp.effective_timestamp_ns / 1e9) / window)
                if plot_l <= cx <= plot_r:
                    painter.drawRect(int(cx), int(y), 2, lane_h)
            # Sync anchors (session-global marks on every lane)
            painter.setBrush(theme.ORANGE)
            for sync in state.sync_anchors:
                cx = plot_l + plot_w * ((sync.timestamp_ns / 1e9) / window)
                if plot_l <= cx <= plot_r:
                    painter.drawRect(int(cx), int(y), 2, lane_h)
            # Playhead
            px = plot_l + plot_w * min(1.0, state.elapsed_s / window)
            painter.setPen(theme.TEXT)
            painter.drawLine(int(px), int(y), int(px), int(y + lane_h))
            y += lane_h + lane_gap


class CheckpointEditRow(QFrame):
    renamed = Signal(str, str)  # id, name

    def __init__(self, cp: CheckpointRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._id = cp.checkpoint_id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        marker = QLabel("\u2691")
        marker.setStyleSheet(f"color: {theme.ACCENT.name()};")
        stamp = QLabel(fmt_time(cp.effective_timestamp_ns / 1e9))
        stamp.setFont(theme.mono(9))
        stamp.setObjectName("Dim")
        stamp.setFixedWidth(58)
        self.name = QLineEdit(cp.name)
        self.name.setFont(theme.ui(9))
        self.name.editingFinished.connect(self._commit)
        layout.addWidget(marker)
        layout.addWidget(stamp)
        layout.addWidget(self.name, 1)

    def _commit(self) -> None:
        self.renamed.emit(self._id, self.name.text().strip() or "(unnamed)")

    def focus_name(self) -> None:
        self.name.setFocus()
        self.name.selectAll()


class RightDock(QWidget):
    checkpoint_renamed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[CheckpointEditRow] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        cp_frame, cp_body = panel("Checkpoints")
        self._cp_hint = QLabel("Press Checkpoint (C / Space) while recording.")
        self._cp_hint.setObjectName("Faint")
        self._cp_hint.setFont(theme.ui(8))
        self._cp_hint.setWordWrap(True)
        self._cp_body = cp_body
        self._cp_body.addWidget(self._cp_hint)
        self._cp_body.addStretch(1)
        outer.addWidget(cp_frame, 2)

        note_frame, note_body = panel("Annotations / Sync")
        self._notes_label = QLabel("—")
        self._notes_label.setObjectName("Dim")
        self._notes_label.setFont(theme.ui(8))
        self._notes_label.setWordWrap(True)
        self._notes_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        note_body.addWidget(self._notes_label, 1)
        outer.addWidget(note_frame, 1)

        alert_frame, alert_body = panel("Alerts")
        self._alert_label = QLabel("No alerts")
        self._alert_label.setObjectName("Dim")
        self._alert_label.setFont(theme.ui(8))
        self._alert_label.setWordWrap(True)
        self._alert_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        alert_body.addWidget(self._alert_label, 1)
        outer.addWidget(alert_frame, 1)

        disk_frame, disk_body = panel("Disk")
        self._disk_label = QLabel("—")
        self._disk_label.setObjectName("Dim")
        self._disk_label.setFont(theme.mono(8))
        self._disk_label.setWordWrap(True)
        disk_body.addWidget(self._disk_label)
        outer.addWidget(disk_frame, 0)

    def focus_checkpoint(self, checkpoint_id: str) -> None:
        for row in self._rows:
            if row._id == checkpoint_id:  # noqa: SLF001
                row.focus_name()
                return

    def refresh(self, state: CaptureState) -> None:
        ids = [r._id for r in self._rows]  # noqa: SLF001
        new_ids = [c.checkpoint_id for c in state.checkpoints]
        if ids != new_ids:
            for row in self._rows:
                row.setParent(None)
            self._rows.clear()
            for cp in state.checkpoints:
                row = CheckpointEditRow(cp)
                row.renamed.connect(self.checkpoint_renamed.emit)
                self._cp_body.insertWidget(self._cp_body.count() - 1, row)
                self._rows.append(row)
            self._cp_hint.setVisible(not state.checkpoints)

        note_lines: list[str] = []
        for ann in state.annotations[-8:]:
            t = fmt_time(ann.timestamp_ns / 1e9)
            note_lines.append(f"A {t} {ann.category or 'note'}: {ann.text[:48]}")
        for sync in state.sync_anchors[-6:]:
            t = fmt_time(sync.timestamp_ns / 1e9)
            note_lines.append(f"S {t} {sync.mechanism or 'sync'}")
        self._notes_label.setText("\n".join(note_lines) if note_lines else "—")

        pending = [a for a in state.alerts if not a.acknowledged]
        if not pending:
            self._alert_label.setText("No alerts")
            self._alert_label.setStyleSheet(f"color: {theme.TEXT_DIM.name()};")
        else:
            lines = []
            for a in pending[:12]:
                color = theme.LEVEL_COLORS.get(a.level, theme.TEXT_DIM)
                lines.append(
                    f"<span style='color:{color.name()}'>{a.level}</span> "
                    f"{a.source_id or 'session'}: {a.message}"
                )
            self._alert_label.setText("<br>".join(lines))

        disk = state.disk
        if disk is None:
            self._disk_label.setText("awaiting disk status")
            self._disk_label.setStyleSheet(f"color: {theme.TEXT_DIM.name()};")
        else:
            level = int(getattr(disk, "headroom_level", 0) or 0)
            color = theme.TEXT_DIM
            if level >= health_pb2.ALERT_LEVEL_CRITICAL:
                color = theme.RED
            elif level >= health_pb2.ALERT_LEVEL_WARNING:
                color = theme.ORANGE
            elif level >= health_pb2.ALERT_LEVEL_INFO:
                color = theme.ACCENT
            reserve = getattr(disk, "reserve_bytes", 0) or 0
            self._disk_label.setStyleSheet(f"color: {color.name()};")
            self._disk_label.setText(
                f"Free {fmt_bytes(disk.free_bytes)}\n"
                f"Reserve {fmt_bytes(reserve)}\n"
                f"Write {disk.write_mb_per_s:.1f} MB/s\n"
                f"Est. {disk.estimated_remaining_minutes:.0f} min remaining\n"
                f"{'WRITERS BLOCKED' if disk.writers_blocked else 'writers ok'}"
            )


class CaptureScreen(QWidget):
    """Main capture surface wired to CaptureState."""

    focus_changed = Signal(str)
    selection_toggled = Signal(str)
    checkpoint_renamed = Signal(str, str)
    view_mode_changed = Signal(int)
    radar_view_changed = Signal(str, str)  # source_id, preview_view
    alert_ack_requested = Signal(str)
    alert_show_source = Signal(str)
    radar_array_edit_requested = Signal()

    def __init__(
        self,
        state: CaptureState,
        persistence: DesktopPersistence | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._persistence = persistence
        self._rail_rows: dict[str, RailRow] = {}
        self._cards: list[SourceCard] = []
        self._card_sig: tuple[str, ...] = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        self._alert_bar = QFrame()
        self._alert_bar.setObjectName("Card")
        self._alert_bar.setVisible(False)
        alert_row = QHBoxLayout(self._alert_bar)
        alert_row.setContentsMargins(10, 6, 10, 6)
        self._alert_text = QLabel("")
        self._alert_text.setWordWrap(True)
        self._alert_text.setFont(theme.ui(9))
        self._btn_ack = QPushButton("Acknowledge")
        self._btn_ack.setObjectName("Ghost")
        self._btn_show = QPushButton("Show source")
        self._btn_show.setObjectName("Ghost")
        self._btn_ack.clicked.connect(self._ack_current_alert)
        self._btn_show.clicked.connect(self._show_alert_source)
        alert_row.addWidget(self._alert_text, 1)
        alert_row.addWidget(self._btn_show)
        alert_row.addWidget(self._btn_ack)
        root.addWidget(self._alert_bar)

        self._rehearse_banner = QLabel("Rehearsal — previews only, not recording.")
        self._rehearse_banner.setObjectName("Dim")
        self._rehearse_banner.setFont(theme.ui(8, bold=True))
        self._rehearse_banner.setVisible(False)
        self._rehearse_banner.setStyleSheet(
            f"color: {theme.ACCENT.name()}; padding: 2px 4px;"
        )
        root.addWidget(self._rehearse_banner)

        self._honesty_strip = QLabel(
            "Native device timestamps · no resample during capture · raw sealed to package"
        )
        self._honesty_strip.setObjectName("HonestyBanner")
        self._honesty_strip.setFont(theme.ui(8))
        self._honesty_strip.setWordWrap(True)
        root.addWidget(self._honesty_strip)

        self._array_card = QWidget()
        self._array_card.setVisible(False)
        array_row = QHBoxLayout(self._array_card)
        array_row.setContentsMargins(8, 6, 8, 6)
        self._array_label = QLabel("")
        self._array_label.setObjectName("Dim")
        self._array_label.setFont(theme.ui(8))
        self._array_label.setWordWrap(True)
        self._btn_array = QPushButton("Save array preset…")
        self._btn_array.setObjectName("Ghost")
        self._btn_array.clicked.connect(self.radar_array_edit_requested.emit)
        array_row.addWidget(self._array_label, 1)
        array_row.addWidget(self._btn_array)
        self._array_card.setStyleSheet(
            f"background: {theme.PANEL_ALT.name()};"
            f"border: 1px solid {theme.BORDER.name()};"
        )
        root.addWidget(self._array_card)

        body = QHBoxLayout()
        body.setSpacing(8)
        body.addWidget(self._build_rail(), 0)
        body.addWidget(self._build_centre(), 1)
        self._dock = RightDock()
        self._dock.setFixedWidth(272)
        self._dock.checkpoint_renamed.connect(self.checkpoint_renamed.emit)
        body.addWidget(self._dock, 0)
        root.addLayout(body, 1)

    def focus_checkpoint(self, checkpoint_id: str) -> None:
        self._dock.focus_checkpoint(checkpoint_id)

    def _build_rail(self) -> QWidget:
        frame, body = panel("Sources")
        frame.setFixedWidth(220)
        self._rail_title = frame.findChild(QLabel, "PanelTitle")
        self._rail_body = body
        self._rail_stretch_at = body.count()
        body.addStretch(1)
        hint = QLabel("Click to focus · right-click to toggle select")
        hint.setObjectName("Faint")
        hint.setFont(theme.ui(8))
        hint.setWordWrap(True)
        body.addWidget(hint)
        return frame

    def _build_centre(self) -> QWidget:
        frame, body = panel()
        header = QHBoxLayout()
        header.setSpacing(4)
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        for index, name in enumerate(("Timeline", "Focus", "Grid")):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setObjectName("Ghost")
            button.setChecked(index == 0)
            button.clicked.connect(lambda _=False, i=index: self.set_view_mode(i))
            self._view_group.addButton(button, index)
            header.addWidget(button)
        header.addStretch(1)
        body.addLayout(header)

        self._stack = QStackedWidget()
        self._timeline = TimelinePanel()
        self._focus = FocusPanel()
        self._focus.radar_view_changed.connect(self.radar_view_changed.emit)
        grid_host = QWidget()
        grid_outer = QVBoxLayout(grid_host)
        grid_outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        scroll.setWidget(self._grid_host)
        grid_outer.addWidget(scroll)
        self._stack.addWidget(self._timeline)
        self._stack.addWidget(self._focus)
        self._stack.addWidget(grid_host)
        body.addWidget(self._stack, 1)
        return frame

    def view_mode(self) -> int:
        return self._stack.currentIndex()

    def set_view_mode(self, index: int) -> None:
        index = max(0, min(2, index))
        self._stack.setCurrentIndex(index)
        btn = self._view_group.button(index)
        if btn is not None:
            btn.setChecked(True)
        self.view_mode_changed.emit(index)
        self.refresh()

    def rebuild_rail(self) -> None:
        for row in self._rail_rows.values():
            row.setParent(None)
        self._rail_rows.clear()
        # Insert above stretch (second-to-last before hint... we keep stretch then hint)
        insert_at = max(0, self._rail_body.count() - 2)
        for src in self._state.sources:
            row = RailRow(src)
            row.clicked.connect(self._on_focus)
            row.toggled.connect(self.selection_toggled.emit)
            self._rail_body.insertWidget(insert_at, row)
            insert_at += 1
            self._rail_rows[src.source_id] = row
        title = self.findChildren(QLabel)
        for label in title:
            if label.objectName() == "PanelTitle" and label.text().startswith("Sources"):
                label.setText(f"Sources ({len(self._state.sources)})")

    def _on_focus(self, source_id: str) -> None:
        self._state.focus_id = source_id
        self._focus.set_source(source_id)
        self.focus_changed.emit(source_id)
        if self.view_mode() == 2:
            self.set_view_mode(1)
        self.refresh()

    def _rebuild_grid(self) -> None:
        selected = self._state.selected_sources()
        sig = tuple(s.source_id for s in selected)
        if sig == self._card_sig:
            return
        self._card_sig = sig
        for card in self._cards:
            card.setParent(None)
        self._cards.clear()
        configured = int(getattr(self._state, "preview_grid_columns", 0) or 0)
        n = max(1, len(selected))
        columns = configured if configured > 0 else min(3, n)
        for index, src in enumerate(selected):
            card = SourceCard(src)
            card.clicked.connect(self._on_focus)
            self._grid.addWidget(card, index // columns, index % columns)
            self._cards.append(card)
        for column in range(columns):
            self._grid.setColumnStretch(column, 1)

    def _ack_current_alert(self) -> None:
        alert = self._state.highest_unacked_alert()
        if alert is not None:
            self.alert_ack_requested.emit(alert.alert_id)

    def _show_alert_source(self) -> None:
        alert = self._state.highest_unacked_alert()
        if alert is not None and alert.source_id:
            self.alert_show_source.emit(alert.source_id)
            self._on_focus(alert.source_id)

    def refresh(self) -> None:
        if len(self._rail_rows) != len(self._state.sources):
            self.rebuild_rail()
        for sid, row in self._rail_rows.items():
            row.set_focus_selected(sid == self._state.focus_id)
            row.refresh(self._state)
        self._focus.set_source(self._state.focus_id)
        mode = self.view_mode()
        if mode == 0:
            self._timeline.refresh(self._state)
        elif mode == 1:
            self._focus.refresh(self._state)
        else:
            self._rebuild_grid()
            for card in self._cards:
                card.refresh(self._state)
        self._dock.refresh(self._state)

        alert = self._state.highest_unacked_alert()
        if alert is None:
            self._alert_bar.setVisible(False)
        else:
            self._alert_bar.setVisible(True)
            color = theme.RED if alert.level == "CRITICAL" else theme.ACCENT
            self._alert_text.setStyleSheet(f"color: {color.name()};")
            src = f" · {alert.source_id}" if alert.source_id else ""
            self._alert_text.setText(f"{alert.level}{src}: {alert.message}")
            self._btn_show.setEnabled(bool(alert.source_id))
        self._rehearse_banner.setVisible(
            self._state.rehearsal_active and not self._state.recording
        )
        radars = [
            s
            for s in self._state.selected_sources()
            if s.modality in ("radar", "radar_doppler") or s.is_hardware_radar
        ]
        if len(radars) >= 2:
            names = ", ".join(s.alias for s in radars)
            self._array_label.setText(
                f"Radar array (session_radar) — software coordinated · {names}"
            )
            self._array_card.setVisible(True)
            self._btn_array.setEnabled(self._persistence is not None)
        else:
            self._array_card.setVisible(False)
