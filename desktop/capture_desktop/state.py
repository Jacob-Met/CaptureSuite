# SPDX-License-Identifier: GPL-3.0-only
"""Simple in-memory model for the capture UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from capture_protocol.generated.capture.v1 import (
    control_pb2,
    health_pb2,
    preview_pb2,
    source_pb2,
)

SESSION_STATE_NAMES = {
    control_pb2.SESSION_STATE_UNSPECIFIED: "unspecified",
    control_pb2.SESSION_STATE_IDLE: "idle",
    control_pb2.SESSION_STATE_PREPARING: "preparing",
    control_pb2.SESSION_STATE_ARMING: "arming",
    control_pb2.SESSION_STATE_RECORDING: "recording",
    control_pb2.SESSION_STATE_STOPPING: "stopping",
    control_pb2.SESSION_STATE_FINALIZED: "finalized",
    control_pb2.SESSION_STATE_RECOVERING: "recovering",
    control_pb2.SESSION_STATE_FAILED: "failed",
}

HEALTH_NAMES = {
    health_pb2.HEALTH_LEVEL_UNSPECIFIED: "disabled",
    health_pb2.HEALTH_LEVEL_OK: "ready",
    health_pb2.HEALTH_LEVEL_WARNING: "warning",
    health_pb2.HEALTH_LEVEL_ERROR: "error",
}


def fmt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_rate(hz: float) -> str:
    if hz >= 1000:
        return f"{hz / 1000:.1f} kHz"
    if hz >= 10:
        return f"{hz:.0f} Hz"
    return f"{hz:.1f} Hz"


def fmt_bytes(n: int) -> str:
    value = float(max(0, n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


@dataclass
class SourceRow:
    source_id: str
    alias: str
    source_type: str
    modality: str
    selected: bool
    enabled: bool
    metadata: dict[str, str] = field(default_factory=dict)
    nominal_rate_hz: float = 0.0
    serial: str = ""
    firmware: str = ""
    preview_kind: int = 0
    plugin_id: str = ""

    @property
    def timing_only(self) -> bool:
        return (
            self.metadata.get("record_mode") == "timing_only"
            or self.metadata.get("encoding") == "deferred"
        )

    @property
    def is_real_camera(self) -> bool:
        """Hardware camera (not sim.* plugin / source)."""
        if self.plugin_id.startswith("sim."):
            return False
        hw = self.metadata.get("hardware", "").lower()
        caps = {
            c.strip() for c in self.metadata.get("capabilities", "").split(",") if c.strip()
        }
        if hw in ("1", "true", "yes") or "hardware" in caps:
            return self.source_type == "camera" or self.modality == "video"
        if self.source_type == "camera":
            return True
        if self.modality == "video" and bool(self.plugin_id):
            return True
        return self.plugin_id.startswith("camera.")

    @property
    def is_hardware_radar(self) -> bool:
        """Hardware radar worker — not sim.radar.* stand-ins."""
        if self.plugin_id.startswith("sim."):
            return False
        hw = self.metadata.get("hardware", "").lower()
        caps = {
            c.strip() for c in self.metadata.get("capabilities", "").split(",") if c.strip()
        }
        if hw in ("1", "true", "yes") or "hardware" in caps:
            return (
                self.source_type == "radar"
                or self.modality in ("radar", "radar_doppler")
                or self.source_id.startswith("radar.")
            )
        if self.plugin_id.startswith("radar."):
            return True
        if self.source_id.startswith("radar."):
            return True
        return bool(self.plugin_id) and self.modality in ("radar", "radar_doppler")

    @property
    def is_virtual_camera(self) -> bool:
        """Phone-bridge or screen-capture driver rather than attached hardware.

        These enumerate identically to a webcam but usually need a companion
        app running, so they are poor defaults. Daemon may also tag them via
        metadata ``virtual_camera=true``.
        """
        if not self.is_real_camera:
            return False
        if self.metadata.get("virtual_camera", "").lower() in ("1", "true", "yes"):
            return True
        name = self.alias.casefold()
        return any(
            marker in name
            for marker in (
                "iriun",
                "droidcam",
                "camo",
                "epoccam",
                "manycam",
                "xsplit",
                "obs",
                "virtual",
                "ndi",
            )
        )

    @property
    def kind_key(self) -> str:
        if self.modality:
            return self.modality
        if self.source_type.startswith("sim."):
            return self.source_type.removeprefix("sim.")
        return self.source_type


def default_preferred_camera(sources: list[SourceRow]) -> SourceRow | None:
    """One physical camera to open on first connect.

    Selecting every enumerated camera would open all of them and start a worker
    process each, so the default is a single device: prefer a USB webcam
    (e.g. MX Brio) over the laptop FHD module, and never a virtual camera.
    """
    cameras = [s for s in sources if s.enabled and s.is_real_camera]
    if not cameras:
        return None
    physical = [s for s in cameras if not s.is_virtual_camera]
    pool = physical or cameras

    def _score(src: SourceRow) -> int:
        name = src.alias.casefold()
        key = (src.serial or "").casefold()
        score = 100
        if "usb#" in key:
            score += 50
        if "brio" in name or "logitech" in name:
            score += 20
        if "fhd camera" in name or "integrated" in name or "ir camera" in name:
            score -= 30
        return score

    return max(pool, key=_score)


def default_selected_source_ids(sources: list[SourceRow]) -> list[str]:
    """One physical camera plus the enabled non-camera sources."""
    camera = default_preferred_camera(sources)
    selected = [s.source_id for s in sources if s.enabled and not s.is_real_camera]
    if camera is not None:
        selected.insert(0, camera.source_id)
    return selected


@dataclass
class CheckpointRow:
    checkpoint_id: str
    name: str
    original_timestamp_ns: int
    effective_timestamp_ns: int


@dataclass
class AnnotationRow:
    annotation_id: str
    timestamp_ns: int
    category: str
    text: str
    source_id: str = ""


@dataclass
class SyncAnchorRow:
    sync_anchor_id: str
    timestamp_ns: int
    mechanism: str
    modalities: list[str] = field(default_factory=list)


@dataclass
class AlertRow:
    alert_id: str
    level: str
    source_id: str
    message: str
    acknowledged: bool = False


@dataclass
class GapRow:
    source_id: str
    stream_id: str
    cause: str
    start_session_time_ns: int
    end_session_time_ns: int | None = None
    closed: bool = False
    estimated_lost_count: int = 0

    @property
    def key(self) -> tuple[str, int]:
        return (self.source_id, self.start_session_time_ns)


_GAP_CAUSE_NAMES = {
    health_pb2.GAP_CAUSE_UNSPECIFIED: "gap",
    health_pb2.GAP_CAUSE_DISCONNECT: "disconnect",
    health_pb2.GAP_CAUSE_SEQUENCE_LOSS: "sequence_loss",
    health_pb2.GAP_CAUSE_OVERLOAD_DROP: "overload",
    health_pb2.GAP_CAUSE_WRITER_ERROR: "writer_error",
    health_pb2.GAP_CAUSE_UNKNOWN: "unknown",
}


def _gap_cause_name(cause: int) -> str:
    return _GAP_CAUSE_NAMES.get(cause, "gap")


@dataclass
class CaptureState:
    session_id: str = ""
    package_path: str = ""
    session_state: int = control_pb2.SESSION_STATE_IDLE
    elapsed_session_ns: int = 0
    rehearsal_active: bool = False
    connected: bool = False
    instance_id: str = ""
    sources: list[SourceRow] = field(default_factory=list)
    selected_ids: set[str] = field(default_factory=set)
    health: dict[str, health_pb2.HealthSnapshot] = field(default_factory=dict)
    previews: dict[str, preview_pb2.PreviewFrame] = field(default_factory=dict)
    checkpoints: list[CheckpointRow] = field(default_factory=list)
    annotations: list[AnnotationRow] = field(default_factory=list)
    sync_anchors: list[SyncAnchorRow] = field(default_factory=list)
    alerts: list[AlertRow] = field(default_factory=list)
    gaps: list[GapRow] = field(default_factory=list)
    disk: health_pb2.DiskStatus | None = None
    focus_id: str = ""
    status_line: str = "Not connected"
    review_mode: bool = False
    preview_grid_columns: int = 0  # 0 = auto

    @property
    def recording(self) -> bool:
        return self.session_state == control_pb2.SESSION_STATE_RECORDING

    @property
    def elapsed_s(self) -> float:
        return self.elapsed_session_ns / 1e9

    def session_state_name(self) -> str:
        return SESSION_STATE_NAMES.get(self.session_state, "unknown")

    def by_id(self, source_id: str) -> SourceRow | None:
        for src in self.sources:
            if src.source_id == source_id:
                return src
        return None

    def selected_sources(self) -> list[SourceRow]:
        return [s for s in self.sources if s.source_id in self.selected_ids]

    def health_status(self, source_id: str) -> str:
        snap = self.health.get(source_id)
        src = self.by_id(source_id)
        if src is not None and not src.selected:
            return "disabled"
        if snap is None:
            return "connecting"
        if self.recording and snap.lifecycle_state == source_pb2.SOURCE_LIFECYCLE_RECORDING:
            if snap.health == health_pb2.HEALTH_LEVEL_ERROR or not snap.connected:
                return "error"
            if snap.health == health_pb2.HEALTH_LEVEL_WARNING:
                return "warning"
            return "recording"
        return HEALTH_NAMES.get(snap.health, "ready")

    def apply_sources(
        self,
        reply: control_pb2.ListSourcesReply | control_pb2.RescanSourcesReply,
        *,
        preserve_selection: bool = False,
    ) -> None:
        previous = set(self.selected_ids) if preserve_selection else set()
        rows: list[SourceRow] = []
        for inst in reply.sources:
            modality = inst.metadata.get("modality", "")
            if not modality and inst.streams:
                modality = inst.streams[0].modality
            rate = inst.streams[0].nominal_rate_hz if inst.streams else 0.0
            serial = inst.physical_devices[0].serial if inst.physical_devices else ""
            firmware = inst.physical_devices[0].firmware if inst.physical_devices else ""
            rows.append(
                SourceRow(
                    source_id=inst.source_id,
                    alias=inst.alias or inst.source_id,
                    source_type=inst.source_type,
                    modality=modality,
                    selected=False,
                    enabled=inst.enabled,
                    metadata=dict(inst.metadata),
                    nominal_rate_hz=rate,
                    serial=serial,
                    firmware=firmware,
                    plugin_id=inst.plugin_id or "",
                )
            )
        self.sources = rows
        defaults = default_selected_source_ids(rows)
        if preserve_selection and previous:
            keep = {s.source_id for s in rows} & previous
            self.selected_ids = keep if keep else set(defaults)
        else:
            self.selected_ids = set(defaults)
        for s in self.sources:
            s.selected = s.source_id in self.selected_ids
        if rows:
            preferred = next(
                (s for s in rows if s.source_id in self.selected_ids and s.is_real_camera),
                None,
            ) or next((s for s in rows if s.source_id in self.selected_ids), rows[0])
            self.focus_id = preferred.source_id

    def gaps_for(self, source_id: str) -> list[GapRow]:
        return [g for g in self.gaps if g.source_id == source_id]

    def has_open_gap(self, source_id: str) -> bool:
        snap = self.health.get(source_id)
        if snap is not None and snap.HasField("open_gap"):
            return True
        return any(g.source_id == source_id and not g.closed for g in self.gaps)

    def highest_unacked_alert(self) -> AlertRow | None:
        rank = {"CRITICAL": 3, "WARNING": 2, "INFO": 1}
        open_alerts = [a for a in self.alerts if not a.acknowledged]
        if not open_alerts:
            return None
        return max(open_alerts, key=lambda a: rank.get(a.level, 0))

    def apply_session_view(self, view: control_pb2.GetSessionViewReply) -> None:
        if view.error.code:
            return
        self.session_id = view.session_id or self.session_id
        self.package_path = view.package_path or self.package_path
        self.session_state = view.state
        self.elapsed_session_ns = view.elapsed_session_ns
        self.rehearsal_active = view.rehearsal_active
        self.checkpoints = [
            CheckpointRow(
                checkpoint_id=cp.checkpoint_id,
                name=cp.name or "(unnamed)",
                original_timestamp_ns=cp.original_timestamp_ns,
                effective_timestamp_ns=cp.effective_timestamp_ns,
            )
            for cp in view.checkpoints
        ]
        self.annotations = [
            AnnotationRow(
                annotation_id=a.annotation_id,
                timestamp_ns=a.timestamp_ns,
                category=a.category or "",
                text=a.text or "",
                source_id=a.source_id or "",
            )
            for a in view.annotations
        ]
        self.sync_anchors = [
            SyncAnchorRow(
                sync_anchor_id=s.sync_anchor_id,
                timestamp_ns=s.timestamp_ns,
                mechanism=s.mechanism or "",
                modalities=list(s.modalities_targeted),
            )
            for s in view.sync_anchors
        ]
        level_names = {
            health_pb2.ALERT_LEVEL_INFO: "INFO",
            health_pb2.ALERT_LEVEL_WARNING: "WARNING",
            health_pb2.ALERT_LEVEL_CRITICAL: "CRITICAL",
        }
        self.alerts = [
            AlertRow(
                alert_id=a.alert_id,
                level=level_names.get(a.level, "INFO"),
                source_id=a.source_id,
                message=a.message,
                acknowledged=a.acknowledged,
            )
            for a in view.alerts
        ]
        # Prefer lane gaps from session view; keep live GapEvent rows that
        # have not yet appeared in the snapshot.
        lane_gaps: list[GapRow] = []
        for lane in view.lanes:
            for g in lane.gaps:
                end = g.end_session_time_ns if g.HasField("end_session_time_ns") else None
                lane_gaps.append(
                    GapRow(
                        source_id=g.source_id or lane.source_id,
                        stream_id=g.stream_id or lane.stream_id,
                        cause=_gap_cause_name(g.cause),
                        start_session_time_ns=g.start_session_time_ns,
                        end_session_time_ns=end,
                        closed=bool(g.closed or end is not None),
                        estimated_lost_count=g.estimated_lost_count,
                    )
                )
        if lane_gaps:
            live_only = [
                g
                for g in self.gaps
                if g.key not in {(x.source_id, x.start_session_time_ns) for x in lane_gaps}
            ]
            self.gaps = lane_gaps + live_only
        if view.HasField("disk") or view.disk.free_bytes or view.disk.reserve_bytes:
            self.disk = view.disk

    def apply_preview(self, frame: preview_pb2.PreviewFrame) -> None:
        self.previews[frame.source_id] = frame

    def apply_health(self, snap: health_pb2.HealthSnapshot) -> None:
        self.health[snap.source_id] = snap

    def apply_disk(self, disk: health_pb2.DiskStatus) -> None:
        self.disk = disk

    def apply_alert(self, alert: health_pb2.Alert) -> None:
        level_names = {
            health_pb2.ALERT_LEVEL_INFO: "INFO",
            health_pb2.ALERT_LEVEL_WARNING: "WARNING",
            health_pb2.ALERT_LEVEL_CRITICAL: "CRITICAL",
        }
        row = AlertRow(
            alert_id=alert.alert_id,
            level=level_names.get(alert.level, "INFO"),
            source_id=alert.source_id,
            message=alert.message,
            acknowledged=alert.acknowledged,
        )
        for i, existing in enumerate(self.alerts):
            if existing.alert_id == row.alert_id:
                self.alerts[i] = row
                return
        self.alerts.append(row)

    def apply_gap_event(self, gap: health_pb2.GapEvent) -> None:
        end = gap.end_session_time_ns if gap.HasField("end_session_time_ns") else None
        row = GapRow(
            source_id=gap.source_id,
            stream_id=gap.stream_id,
            cause=_gap_cause_name(gap.cause),
            start_session_time_ns=gap.start_session_time_ns,
            end_session_time_ns=end,
            closed=bool(gap.closed or end is not None),
            estimated_lost_count=gap.estimated_lost_count,
        )
        for i, existing in enumerate(self.gaps):
            if existing.key == row.key:
                self.gaps[i] = row
                return
        self.gaps.append(row)

    def upsert_checkpoint(self, cp: Any) -> None:
        row = CheckpointRow(
            checkpoint_id=cp.checkpoint_id,
            name=cp.name or "(unnamed)",
            original_timestamp_ns=cp.original_timestamp_ns,
            effective_timestamp_ns=cp.effective_timestamp_ns,
        )
        for i, existing in enumerate(self.checkpoints):
            if existing.checkpoint_id == row.checkpoint_id:
                self.checkpoints[i] = row
                return
        self.checkpoints.append(row)
