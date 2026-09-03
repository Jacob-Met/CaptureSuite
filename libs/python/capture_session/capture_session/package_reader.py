# SPDX-License-Identifier: GPL-3.0-only
"""Read-only review summary for a sealed/recovered .mmsession package."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

class SessionPackageError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class GapSummary:
    source_id: str
    stream_id: str
    cause: str
    start_session_time_ns: int
    end_session_time_ns: int | None
    closed: bool
    estimated_lost_count: int = 0


@dataclass
class ReviewSummary:
    package_path: str
    session_id: str
    state: str
    t0_wall_utc: str = ""
    finalized_utc: str = ""
    source_ids: list[str] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    annotations: list[dict[str, Any]] = field(default_factory=list)
    sync_anchors: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[GapSummary] = field(default_factory=list)
    integrity_files: list[dict[str, Any]] = field(default_factory=list)
    arrays: dict[str, Any] | None = None
    recovery_reports: list[str] = field(default_factory=list)
    duration_ns: int = 0

    @property
    def open_gap_count(self) -> int:
        return sum(1 for g in self.gaps if not g.closed)

    @property
    def closed_gap_count(self) -> int:
        return sum(1 for g in self.gaps if g.closed)


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        for key in ("checkpoints", "annotations", "syncAnchors", "items"):
            if isinstance(raw.get(key), list):
                return [x for x in raw[key] if isinstance(x, dict)]
    return []


def _load_gaps_jsonl(path: Path, source_id: str) -> list[GapSummary]:
    if not path.is_file():
        return []
    out: list[GapSummary] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        start = int(row.get("startSessionTimeNs") or row.get("start_session_time_ns") or 0)
        end_raw = row.get("endSessionTimeNs", row.get("end_session_time_ns"))
        end = int(end_raw) if end_raw is not None else None
        closed = bool(row.get("closed", end is not None))
        out.append(
            GapSummary(
                source_id=str(row.get("sourceId") or row.get("source_id") or source_id),
                stream_id=str(row.get("streamId") or row.get("stream_id") or ""),
                cause=str(row.get("cause") or "unknown"),
                start_session_time_ns=start,
                end_session_time_ns=end,
                closed=closed,
                estimated_lost_count=int(
                    row.get("estimatedLostCount") or row.get("estimated_lost_count") or 0
                ),
            )
        )
    return out


def load_review_summary(package_root: str | Path) -> ReviewSummary:
    root = Path(package_root)
    if not root.is_dir():
        raise SessionPackageError(f"package not found: {root}")
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise SessionPackageError(f"missing manifest: {manifest_path}")
    manifest = _load_json(manifest_path)
    identity = manifest.get("identity") or {}
    session_id = str(
        manifest.get("sessionId") or identity.get("sessionId") or root.stem
    )
    state = str(manifest.get("state") or "")
    integrity_files: list[dict[str, Any]] = []
    integrity_path = root / "integrity.json"
    if integrity_path.is_file():
        try:
            integrity = _load_json(integrity_path)
            files = integrity.get("files") or []
            if isinstance(files, list):
                integrity_files = [f for f in files if isinstance(f, dict)]
        except json.JSONDecodeError:
            pass

    events = root / "events"
    checkpoints = _load_json_list(events / "checkpoints.json")
    annotations = _load_json_list(events / "annotations.json")
    sync_anchors = _load_json_list(events / "sync_anchors.json")

    gaps: list[GapSummary] = []
    sources_dir = root / "sources"
    source_ids: list[str] = []
    if sources_dir.is_dir():
        for src in sorted(p for p in sources_dir.iterdir() if p.is_dir()):
            source_ids.append(src.name)
            gap_path = src / "health" / "gaps.jsonl"
            gaps.extend(_load_gaps_jsonl(gap_path, src.name))

    arrays = None
    arrays_path = root / "arrays.json"
    if arrays_path.is_file():
        try:
            arrays = json.loads(arrays_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            arrays = None

    recovery_reports = sorted(
        str(p.relative_to(root)).replace("\\", "/")
        for p in (root / "recovery").glob("report_*.json")
    ) if (root / "recovery").is_dir() else []

    duration_ns = 0
    for f in integrity_files:
        try:
            end = int(f.get("endSessionTimeNs") or 0)
        except (TypeError, ValueError):
            end = 0
        duration_ns = max(duration_ns, end)
    for g in gaps:
        if g.end_session_time_ns is not None:
            duration_ns = max(duration_ns, g.end_session_time_ns)
        duration_ns = max(duration_ns, g.start_session_time_ns)

    return ReviewSummary(
        package_path=str(root),
        session_id=session_id,
        state=state,
        t0_wall_utc=str(manifest.get("t0WallUtc") or manifest.get("t0_wall_utc") or ""),
        finalized_utc=str(
            manifest.get("finalizedUtc") or manifest.get("finalized_utc") or ""
        ),
        source_ids=source_ids or list(manifest.get("sourceIds") or []),
        checkpoints=checkpoints,
        annotations=annotations,
        sync_anchors=sync_anchors,
        gaps=gaps,
        integrity_files=integrity_files,
        arrays=arrays if isinstance(arrays, dict) else None,
        recovery_reports=recovery_reports,
        duration_ns=duration_ns,
    )
