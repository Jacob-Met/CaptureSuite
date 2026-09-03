# SPDX-License-Identifier: GPL-3.0-only
"""Modality-specific expanded inspector rows for Focus view."""

from __future__ import annotations

from .state import CaptureState, SourceRow, fmt_rate


def _is_provisional(src: SourceRow) -> bool:
    if src.source_id.startswith("sim."):
        return True
    if src.plugin_id.startswith("sim."):
        return True
    return src.metadata.get("provisional", "").lower() in ("1", "true", "yes")


def _badge_provisional(src: SourceRow) -> str:
    if _is_provisional(src):
        return " · provisional (sim/replay)"
    if src.metadata.get("hardware_validated", "").lower() in ("1", "true", "yes"):
        return " · hardware validated"
    return ""


def _emg_lines(src: SourceRow, state: CaptureState) -> list[str]:
    md = src.metadata
    channels = md.get("channel_ids") or md.get("channels") or []
    if isinstance(channels, str):
        channels = [c.strip() for c in channels.split(",") if c.strip()]
    ch_count = len(channels) if channels else int(md.get("channel_count") or 8)
    units = md.get("units") or "a.u."
    calibrated = md.get("calibrated", "false").lower() in ("1", "true", "yes")
    lines = [
        f"EMG · {ch_count} ch · {fmt_rate(src.nominal_rate_hz or float(md.get('rate_hz') or 0))}",
        f"Units: {units}{'' if calibrated else ' (uncalibrated)'}",
    ]
    anatomy = md.get("anatomical_preset") or md.get("muscle_map")
    if anatomy:
        lines.append(f"Anatomy preset: {anatomy}")
    muscles = md.get("muscle_labels") or md.get("muscles")
    if isinstance(muscles, str) and muscles.strip():
        labels = [m.strip() for m in muscles.split(",") if m.strip()]
        preview = ", ".join(labels[:8])
        if len(labels) > 8:
            preview += f", +{len(labels) - 8} more"
        lines.append(f"Muscles: {preview}")
    elif channels:
        preview = ", ".join(str(c) for c in channels[:8])
        if len(channels) > 8:
            preview += f", +{len(channels) - 8} more"
        lines.append(f"Channels: {preview}")
    else:
        # Default sim channel grid labels for expanded card depth.
        default = [f"ch{i}" for i in range(ch_count)]
        lines.append(f"Channels: {', '.join(default[:8])}" + ("…" if ch_count > 8 else ""))
    frame = state.previews.get(src.source_id)
    if frame is not None and frame.HasField("trace"):
        lines.append(
            f"Live trace: {frame.trace.channel_count} ch × "
            f"{frame.trace.points_per_channel} samples"
        )
        if frame.trace.units:
            lines.append(f"Preview units: {frame.trace.units}")
    snap = state.health.get(src.source_id)
    if snap and snap.connected:
        lines.append(
            f"Arrival: {fmt_rate(snap.measured_rate_hz)} measured · "
            f"{snap.dropped_count} dropped · gaps {snap.gap_count}"
        )
        if snap.dropped_last_10s:
            lines.append(f"Dropout last 10s: {snap.dropped_last_10s}")
    lines[0] += _badge_provisional(src)
    return lines


def _imu_lines(src: SourceRow, state: CaptureState) -> list[str]:
    md = src.metadata
    sensor_count = int(md.get("sensor_count") or md.get("sensors") or 7)
    preview_sensor = md.get("preview_sensor") or md.get("default_sensor") or "pelvis"
    lines = [
        f"IMU · {sensor_count} sensors · {fmt_rate(src.nominal_rate_hz)}",
        f"Preview sensor: {preview_sensor}",
    ]
    segments = md.get("segment_map") or md.get("segments")
    if isinstance(segments, str) and segments.strip():
        lines.append(f"Segments: {segments}")
    else:
        lines.append("Segments: pelvis → thorax → upper arms (sim default)")
    frame = state.previews.get(src.source_id)
    if frame is not None and frame.HasField("orientation"):
        sel = frame.selected_channel if frame.selected_channel else preview_sensor
        o = frame.orientation
        lines.append(
            f"Orientation: qw={o.qw:.3f} qx={o.qx:.3f} qy={o.qy:.3f} qz={o.qz:.3f} ({sel})"
        )
        if o.accel_magnitude:
            lines.append(
                f"Accel |a|={o.accel_magnitude:.2f} {o.accel_units or 'a.u.'}"
            )
    if md.get("mag_disturbance") in ("1", "true", "yes"):
        lines.append("Magnetic disturbance flagged")
    snap = state.health.get(src.source_id)
    if snap and snap.connected:
        lines.append(
            f"Packet health: {snap.dropped_last_10s} drops / 10s · gaps {snap.gap_count}"
        )
    lines[0] += _badge_provisional(src)
    return lines


def _radar_lines(src: SourceRow, state: CaptureState) -> list[str]:
    md = src.metadata
    cfg_hash = md.get("configuration_hash") or md.get("config_hash") or "—"
    kind = src.kind_key
    label = "Doppler radar" if kind == "radar_doppler" else "FMCW radar"
    lines = [
        f"{label} · {fmt_rate(src.nominal_rate_hz)} · config {str(cfg_hash)[:12]}",
    ]
    slot = md.get("logical_slot") or md.get("slot")
    if slot:
        lines.append(f"Spatial slot: {slot}")
    radars = [
        s
        for s in state.selected_sources()
        if s.modality in ("radar", "radar_doppler") or s.is_hardware_radar
    ]
    if len(radars) >= 2:
        lines.append(f"Array: software coordinated · {len(radars)} members")
    lines.append("Timestamps: device-native · host arrival may lag")
    frame = state.previews.get(src.source_id)
    if frame is not None and frame.HasField("matrix"):
        m = frame.matrix
        lines.append(
            f"Preview: {m.rows}×{m.cols} heatmap "
            f"({m.row_axis or 'range'}×{m.col_axis or 'doppler'})"
        )
    elif frame is not None and frame.HasField("trace"):
        lines.append(
            f"Motion trace: {frame.trace.points_per_channel} samples "
            f"({frame.trace.units or 'a.u.'})"
        )
    snap = state.health.get(src.source_id)
    if snap and snap.connected:
        lines.append(
            f"Frames: {fmt_rate(snap.measured_rate_hz)} · "
            f"overload drops {snap.dropped_last_10s}/10s"
        )
        if snap.current_segment:
            lines.append(f"Segment: {snap.current_segment}")
    lines[0] += _badge_provisional(src)
    return lines


def _camera_lines(src: SourceRow, state: CaptureState) -> list[str]:
    md = src.metadata
    mode = md.get("record_mode") or ("timing_only" if src.timing_only else "full")
    enc = md.get("encoding") or ("deferred" if src.timing_only else "mkv")
    res = md.get("resolution") or md.get("size") or ""
    slot = md.get("logical_slot") or md.get("view") or ""
    lines = [
        f"Camera · {fmt_rate(src.nominal_rate_hz)} · record {mode}",
        f"Encode path: {enc} · serial {src.serial or '—'}",
    ]
    if res:
        lines.append(f"Resolution: {res}")
    if slot:
        lines.append(f"Logical slot: {slot}")
    if src.firmware:
        lines.append(f"Firmware / encoder: {src.firmware}")
    if src.is_virtual_camera:
        lines.append("Virtual camera — not a default capture device")
    snap = state.health.get(src.source_id)
    if snap and snap.connected:
        lines.append(f"Preview: {fmt_rate(snap.measured_rate_hz)} effective")
        if snap.dropped_count:
            lines.append(f"Dropped frames: {snap.dropped_count}")
        if snap.current_segment:
            lines.append(f"Segment: {snap.current_segment}")
    if _is_provisional(src):
        lines[0] += _badge_provisional(src)
    return lines


def _generic_lines(src: SourceRow, state: CaptureState) -> list[str]:
    snap = state.health.get(src.source_id)
    lines = [f"{src.modality or src.source_type} · {fmt_rate(src.nominal_rate_hz)}"]
    if snap and snap.connected:
        lines.append(f"Rate {fmt_rate(snap.measured_rate_hz)} · gaps {snap.gap_count}")
    lines[0] += _badge_provisional(src)
    return lines


def expanded_detail_lines(src: SourceRow, state: CaptureState) -> list[str]:
    kind = src.kind_key
    if kind == "emg":
        return _emg_lines(src, state)
    if kind == "imu":
        return _imu_lines(src, state)
    if kind in ("radar", "radar_doppler"):
        return _radar_lines(src, state)
    if kind in ("camera", "video"):
        return _camera_lines(src, state)
    return _generic_lines(src, state)


def expanded_honesty_footer(src: SourceRow) -> str:
    if src.timing_only:
        return "Recording timing metadata; encode deferred to seal."
    if _is_provisional(src):
        return "Sim/replay path — features tagged provisional until hardware validation."
    return "Native device timestamps · no resample during capture."
