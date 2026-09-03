# SPDX-License-Identifier: GPL-3.0-only
"""Package QC for analysis jobs (Phase A)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from capture_analysis.discover import discover_streams
from capture_analysis.types import StreamRef
from capture_session.package_reader import ReviewSummary, load_review_summary


@dataclass
class StreamQc:
    source_id: str
    stream_id: str
    modality: str
    data_schema_id: str
    nominal_rate_hz: float
    units: str
    mcap_segments: int
    mkv_segments: int
    timing_segments: int
    rate_ok: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "streamId": self.stream_id,
            "modality": self.modality,
            "dataSchemaId": self.data_schema_id,
            "nominalRateHz": self.nominal_rate_hz,
            "units": self.units,
            "mcapSegments": self.mcap_segments,
            "mkvSegments": self.mkv_segments,
            "timingSegments": self.timing_segments,
            "rateOk": self.rate_ok,
            "warnings": list(self.warnings),
        }


@dataclass
class QcReport:
    package_path: str
    session_id: str
    package_state: str
    duration_ns: int
    manifest_sha256: str
    source_count: int
    stream_count: int
    open_gap_count: int
    closed_gap_count: int
    checkpoint_count: int
    annotation_count: int
    sync_anchor_count: int
    recovery_reports: list[str]
    streams: list[StreamQc]
    integrity_file_count: int
    warnings: list[str] = field(default_factory=list)
    traffic_lights: dict[str, str] = field(default_factory=dict)  # source_id -> ok|warn|fail

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaId": "capture.analysis_qc/1",
            "packagePath": self.package_path,
            "sessionId": self.session_id,
            "packageState": self.package_state,
            "durationNs": self.duration_ns,
            "manifestSha256": self.manifest_sha256,
            "sourceCount": self.source_count,
            "streamCount": self.stream_count,
            "openGapCount": self.open_gap_count,
            "closedGapCount": self.closed_gap_count,
            "checkpointCount": self.checkpoint_count,
            "annotationCount": self.annotation_count,
            "syncAnchorCount": self.sync_anchor_count,
            "recoveryReports": list(self.recovery_reports),
            "integrityFileCount": self.integrity_file_count,
            "streams": [s.to_dict() for s in self.streams],
            "warnings": list(self.warnings),
            "trafficLights": dict(self.traffic_lights),
        }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stream_qc(ref: StreamRef) -> StreamQc:
    warnings: list[str] = []
    rate_ok = ref.nominal_rate_hz > 0
    if not rate_ok:
        # Video MKV-only descriptors sometimes omit rate; warn, don't fail QC.
        if ref.modality == "video" or ref.mkv_paths:
            warnings.append("nominal_rate_hz missing or zero (feature jobs will fail)")
        else:
            warnings.append("nominal_rate_hz missing or zero")

    if ref.modality in ("radar", "radar_doppler"):
        warnings.append(
            "radar timing is host-arrival; uncertainty may be tens of milliseconds "
            "(not a hardware-sync claim)"
        )

    if not ref.mcap_paths and not ref.mkv_paths:
        warnings.append("no segment files under streams/*/segments/")

    if ref.mkv_paths and not ref.timing_mcap_paths and not any(
        "timing" in p.name for p in ref.mcap_paths
    ):
        # timing may live beside mkv as *.timing.mcap already split out
        if not ref.timing_mcap_paths:
            warnings.append("video segments present without timing sidecar MCAP")

    light_bits = []
    if not rate_ok and ref.modality not in ("video",):
        light_bits.append("warn")
    if not ref.mcap_paths and not ref.mkv_paths:
        light_bits.append("fail")

    return StreamQc(
        source_id=ref.source_id,
        stream_id=ref.stream_id,
        modality=ref.modality,
        data_schema_id=ref.data_schema_id,
        nominal_rate_hz=ref.nominal_rate_hz,
        units=ref.units,
        mcap_segments=len(ref.mcap_paths),
        mkv_segments=len(ref.mkv_paths),
        timing_segments=len(ref.timing_mcap_paths),
        rate_ok=rate_ok,
        warnings=warnings,
    )


def collect_qc(package_root: str | Path) -> QcReport:
    root = Path(package_root)
    summary: ReviewSummary = load_review_summary(root)
    manifest_path = root / "manifest.json"
    manifest_sha = _sha256_file(manifest_path) if manifest_path.is_file() else ""

    streams = [_stream_qc(r) for r in discover_streams(root)]
    warnings: list[str] = []
    if summary.state not in ("finalized", "finalized_recovered", ""):
        warnings.append(f"package state is {summary.state!r} (prefer finalized)")
    if summary.recovery_reports:
        warnings.append(
            f"recovery reports present: {', '.join(summary.recovery_reports)}"
        )
    if summary.open_gap_count:
        warnings.append(f"{summary.open_gap_count} open gap(s) still listed")
    if summary.duration_ns <= 1:
        warnings.append(
            "package duration_ns is unknown/zero — analysis uses an open time window "
            "(integrity entries lack endSessionTimeNs)"
        )

    traffic: dict[str, str] = {}
    for s in streams:
        level = "ok"
        if any("no segment" in w for w in s.warnings):
            level = "fail"
        elif s.warnings:
            level = "warn"
        prev = traffic.get(s.source_id, "ok")
        rank = {"ok": 0, "warn": 1, "fail": 2}
        if rank[level] > rank[prev]:
            traffic[s.source_id] = level
        else:
            traffic.setdefault(s.source_id, prev)

    for s in streams:
        warnings.extend(f"{s.source_id}/{s.stream_id}: {w}" for w in s.warnings)

    return QcReport(
        package_path=str(root.resolve()),
        session_id=summary.session_id,
        package_state=summary.state,
        duration_ns=summary.duration_ns,
        manifest_sha256=manifest_sha,
        source_count=len(summary.source_ids),
        stream_count=len(streams),
        open_gap_count=summary.open_gap_count,
        closed_gap_count=summary.closed_gap_count,
        checkpoint_count=len(summary.checkpoints),
        annotation_count=len(summary.annotations),
        sync_anchor_count=len(summary.sync_anchors),
        recovery_reports=list(summary.recovery_reports),
        streams=streams,
        integrity_file_count=len(summary.integrity_files),
        warnings=warnings,
        traffic_lights=traffic,
    )
