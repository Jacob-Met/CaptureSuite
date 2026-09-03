# SPDX-License-Identifier: GPL-3.0-only
"""Walk a sealed package and emit StreamRef rows from source/stream JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from capture_analysis.types import StreamRef


def _pick(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_streams(package_root: str | Path) -> list[StreamRef]:
    root = Path(package_root)
    sources_dir = root / "sources"
    if not sources_dir.is_dir():
        return []

    refs: list[StreamRef] = []
    for src_dir in sorted(p for p in sources_dir.iterdir() if p.is_dir()):
        source_id = src_dir.name
        config: dict[str, Any] = {}
        source_json = src_dir / "source.json"
        if source_json.is_file():
            try:
                config = _load_json(source_json)
            except json.JSONDecodeError:
                config = {}

        streams_dir = src_dir / "streams"
        if not streams_dir.is_dir():
            continue
        for stream_dir in sorted(p for p in streams_dir.iterdir() if p.is_dir()):
            stream_json = stream_dir / "stream.json"
            if not stream_json.is_file():
                continue
            try:
                meta = _load_json(stream_json)
            except json.JSONDecodeError:
                continue

            stream_id = str(
                _pick(meta, "streamId", "stream_id", default=stream_dir.name)
            )
            modality = str(_pick(meta, "modality", default="") or "")
            schema_id = str(
                _pick(meta, "dataSchemaId", "data_schema_id", default="") or ""
            )
            rate = float(_pick(meta, "nominalRateHz", "nominal_rate_hz", default=0.0) or 0.0)
            units = str(_pick(meta, "units", default="") or "")
            dims_raw = _pick(meta, "dimensions", default=[]) or []
            dimensions = tuple(int(x) for x in dims_raw) if isinstance(dims_raw, list) else ()

            segments = stream_dir / "segments"
            mcap_paths = (
                tuple(sorted(segments.glob("*.mcap"))) if segments.is_dir() else ()
            )
            mkv_paths = (
                tuple(sorted(segments.glob("*.mkv"))) if segments.is_dir() else ()
            )
            timing_mcap = (
                tuple(sorted(segments.glob("*.timing.mcap"))) if segments.is_dir() else ()
            )
            # Timing sidecars are also *.mcap; keep primary data MCAPs separate.
            data_mcap = tuple(
                p for p in mcap_paths if not p.name.endswith(".timing.mcap")
            )

            if not modality:
                if schema_id.startswith("emg."):
                    modality = "emg"
                elif schema_id.startswith("imu."):
                    modality = "imu"
                elif schema_id.startswith("radar.doppler"):
                    modality = "radar_doppler"
                elif schema_id.startswith("radar."):
                    modality = "radar"
                elif schema_id.startswith("video.") or mkv_paths:
                    modality = "video"

            refs.append(
                StreamRef(
                    source_id=str(_pick(meta, "sourceId", "source_id", default=source_id)),
                    stream_id=stream_id,
                    modality=modality,
                    data_schema_id=schema_id,
                    nominal_rate_hz=rate,
                    units=units,
                    dimensions=dimensions,
                    mcap_paths=data_mcap,
                    mkv_paths=mkv_paths,
                    timing_mcap_paths=timing_mcap,
                    config_snapshot=config if isinstance(config, dict) else {},
                    stream_json_path=stream_json,
                )
            )
    return refs
