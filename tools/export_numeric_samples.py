# SPDX-License-Identifier: GPL-3.0-only
"""Lossless numeric sample handoff from recorded MCAP, without resampling.

CSV is long-form: one row per frame and channel. Device timestamps and MCAP
anchors are separate. A within-batch session estimate is provided only when
native timestamps exist; it is never a calibrated cross-device clock fit.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
from contextlib import ExitStack
from pathlib import Path

SCHEMA_NAMES = {"capture.v1.data.NumericBatch", "generic.numeric_batch/1"}
COLUMNS = (
    "mcap_file",
    "mcap_channel_id",
    "topic",
    "message_index",
    "frame_index",
    "channel_index",
    "channel_name",
    "value",
    "units",
    "dtype",
    "mcap_log_time_ns",
    "mcap_publish_time_ns",
    "device_time_ns",
    "session_estimate_ns",
    "time_basis",
)


def _decode(payload: bytes, encoding: str) -> dict:
    if encoding == "json":
        record = json.loads(payload)
        if not isinstance(record, dict):
            raise ValueError("numeric JSON payload must be an object")
        return record
    if encoding != "protobuf":
        raise ValueError(f"unsupported numeric message encoding: {encoding!r}")
    proto_root = Path(__file__).resolve().parents[1] / "libs/python/capture_protocol"
    if proto_root.is_dir() and str(proto_root) not in sys.path:
        sys.path.insert(0, str(proto_root))
    from capture_protocol.generated.capture.v1.data.numeric_batch_pb2 import NumericBatch

    msg = NumericBatch()
    msg.ParseFromString(payload)
    return {
        name: list(getattr(msg, name)) for name in ("channel_names", "samples", "device_time_ns")
    } | {
        "channel_count": msg.channel_count,
        "units": msg.units,
        "dtype": msg.dtype,
    }


def _validate(record: dict) -> tuple[int, list[str], list, list[int]]:
    count = record.get("channel_count", 0)
    samples = record.get("samples", [])
    names = record.get("channel_names", [])
    times = record.get("device_time_ns", [])
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("numeric channel_count must be positive")
    if not all(isinstance(value, list) for value in (samples, names, times)):
        raise ValueError("numeric samples, names and times must be arrays")
    if len(samples) % count:
        raise ValueError("numeric samples must contain whole frames")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in samples):
        raise ValueError("numeric samples must be numbers")
    if names and (len(names) != count or not all(isinstance(n, str) for n in names)):
        raise ValueError("numeric channel names must match channel_count")
    if times and (
        len(times) != len(samples) // count
        or not all(
            isinstance(t, int) and not isinstance(t, bool) and -(1 << 63) <= t < (1 << 63)
            for t in times
        )
    ):
        raise ValueError("numeric timestamps must contain one int64 per frame")
    if not all(isinstance(record.get(k, ""), str) for k in ("units", "dtype")):
        raise ValueError("numeric units and dtype must be strings")
    return count, names or [""] * count, samples, times


def export_numeric_samples(root: Path, out: Path, manifest: dict) -> None:
    """Stream recorded frames to CSV; malformed input fails visibly."""
    from mcap.reader import make_reader

    sources = root / "sources"
    if not sources.is_dir():
        return
    for source in sorted(p for p in sources.iterdir() if p.is_dir()):
        dest = out / "numeric" / source.name
        entries: dict[tuple[str, str], dict] = {}
        with ExitStack() as stack:
            for path in sorted(source.rglob("*.mcap")):
                relative = path.relative_to(root).as_posix()
                with path.open("rb") as handle:
                    for message_index, (schema, channel, message) in enumerate(
                        make_reader(handle).iter_messages(log_time_order=False)
                    ):
                        if not schema or schema.name not in SCHEMA_NAMES:
                            continue
                        try:
                            record = _decode(message.data, channel.message_encoding)
                            count, names, samples, times = _validate(record)
                        except Exception as exc:
                            raise ValueError(f"{relative}, message {message_index}: {exc}") from exc
                        if not samples:
                            continue
                        # Stream folder + topic distinguish multiplexed streams, while
                        # rotated segments of the same stream share one output.
                        key = (path.parent.relative_to(source).as_posix(), channel.topic)
                        if key not in entries:
                            dest.mkdir(parents=True, exist_ok=True)
                            label = hashlib.sha256(repr(key).encode()).hexdigest()[:16]
                            csv_path = dest / f"samples-{label}.csv"
                            writer = csv.writer(
                                stack.enter_context(
                                    csv_path.open("w", encoding="utf-8", newline="")
                                )
                            )
                            writer.writerow(COLUMNS)
                            entries[key] = {
                                "source_id": source.name,
                                "topic": channel.topic,
                                "stream_directory": key[0],
                                "samples_csv": csv_path.relative_to(out).as_posix(),
                                "mcap_files": [],
                                "frame_count": 0,
                                "row_count": 0,
                                "message_count": 0,
                                "frames_without_device_time": 0,
                                "nonfinite_value_count": 0,
                                "backward_device_steps": 0,
                                "_writer": writer,
                            }
                        entry = entries[key]
                        if relative not in entry["mcap_files"]:
                            entry["mcap_files"].append(relative)
                        basis = "batch_anchor_plus_native_delta" if times else "unavailable"
                        for frame in range(len(samples) // count):
                            native = times[frame] if times else ""
                            estimated = int(message.log_time) + native - times[0] if times else ""
                            for ch in range(count):
                                value = samples[frame * count + ch]
                                entry["_writer"].writerow(
                                    (
                                        relative,
                                        channel.id,
                                        channel.topic,
                                        message_index,
                                        frame,
                                        ch,
                                        names[ch],
                                        value,
                                        record.get("units", ""),
                                        record.get("dtype", ""),
                                        message.log_time,
                                        message.publish_time,
                                        native,
                                        estimated,
                                        basis,
                                    )
                                )
                                entry["nonfinite_value_count"] += not math.isfinite(value)
                        frames = len(samples) // count
                        entry["frame_count"] += frames
                        entry["row_count"] += len(samples)
                        entry["message_count"] += 1
                        entry["frames_without_device_time"] += 0 if times else frames
                        entry["backward_device_steps"] += sum(
                            b < a for a, b in zip(times, times[1:], strict=False)
                        )
        for entry in entries.values():
            entry.pop("_writer")
            entry["time_semantics"] = (
                "MCAP log_time anchors the first frame; session_estimate_ns adds native "
                "within-batch deltas. Uncalibrated; no drift fit or cross-device sync claim. "
                "Missing native timestamps leave device and estimate fields empty."
            )
            entry["gap_semantics"] = (
                "Recorded samples are preserved, including any within declared gaps. "
                "No gap filling, filtering, sorting or resampling is performed."
            )
            entry["provenance"] = []
            for path in sorted(source.rglob("stream.json")) + [source / "health/gaps.jsonl"]:
                if not path.is_file():
                    continue
                target = dest / "provenance" / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                entry["provenance"].append(target.relative_to(out).as_posix())
            manifest.setdefault("numeric", []).append(entry)
