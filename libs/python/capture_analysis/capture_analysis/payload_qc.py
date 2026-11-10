# SPDX-License-Identifier: GPL-3.0-only
"""Optional sample-grounded quality evidence from sealed MCAP recordings.

MCAP structural validity is not sensor accuracy. A status naming a decoded
schema means its listed value and shape checks actually ran on every message.
All observations are derived from raw bytes without modifying source files.
"""

from __future__ import annotations

import math
from typing import Any

from capture_analysis.types import StreamRef

_PREVIEW_FRAMES = 256
_PREVIEW_CHANNELS = 6

_SCHEMAS = {
    "generic.numeric_batch/1": {"capture.v1.data.NumericBatch", "generic.numeric_batch/1"},
    "emg.batch/1": {"capture.v1.data.EmgBatch", "emg.batch/1"},
    "imu.frame/1": {"capture.v1.data.ImuFrame", "imu.frame/1"},
}


def _decode_emg(payload: bytes) -> tuple[int, int, list[str], list[tuple[float, float]]]:
    import numpy as np
    from capture_protocol.generated.capture.v1.data import emg_batch_pb2

    from capture_analysis.loaders.mcap_iter import decode_protobuf

    msg = decode_protobuf(emg_batch_pb2.EmgBatch, payload)
    n = int(msg.sample_count)
    ids = list(msg.channel_ids)
    if n < 1 or not ids or len(set(ids)) != len(ids) or not all(ids):
        raise ValueError("EMG batch requires samples and unique, nonempty channel IDs")
    expected = 4 * n * len(ids)
    if len(msg.samples_f32_le) != expected:
        raise ValueError(f"EMG sample byte count {len(msg.samples_f32_le)} != {expected}")
    values = np.frombuffer(msg.samples_f32_le, dtype="<f4").reshape(len(ids), n)
    if not bool(np.isfinite(values).all()):
        raise ValueError("EMG samples contain NaN or infinity")
    limits = [(float(row.min()), float(row.max())) for row in values]
    return n, int(msg.first_sample_index), ids, limits


def _decode_imu(payload: bytes) -> tuple[list[str], list[str]]:
    from capture_protocol.generated.capture.v1.data import imu_frame_pb2

    from capture_analysis.loaders.mcap_iter import decode_protobuf

    msg = decode_protobuf(imu_frame_pb2.ImuFrame, payload)
    ids = [sensor.sensor_id for sensor in msg.sensors]
    if not ids or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError("IMU frame requires unique, nonempty sensor IDs")
    zero_sensor_ids: list[str] = []
    for sensor in msg.sensors:
        values = (
            sensor.accel_x,
            sensor.accel_y,
            sensor.accel_z,
            sensor.gyro_x,
            sensor.gyro_y,
            sensor.gyro_z,
            sensor.qw,
            sensor.qx,
            sensor.qy,
            sensor.qz,
        )
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"IMU sensor {sensor.sensor_id!r} contains NaN or infinity")
        if sensor.qw == sensor.qx == sensor.qy == sensor.qz == 0:
            zero_sensor_ids.append(sensor.sensor_id)
    return ids, zero_sensor_ids


def inspect_stream_payloads(
    ref: StreamRef, *, preview_window: tuple[int | None, int | None] | None = None
) -> dict[str, Any]:
    """Read actual MCAP bytes and report checks completed or exact failures.

    Each segment is streamed. Supported schemas are all-or-nothing: a segment
    with no declared-schema messages cannot borrow the success of another.
    """
    result: dict[str, Any] = {
        "status": "not_applicable" if not ref.mcap_paths else "failed",
        "segmentsChecked": 0,
        "messagesChecked": 0,
        "sampleFramesChecked": None,
        "detail": "No data MCAP segments to inspect",
    }
    if not ref.mcap_paths:
        return result

    schema_id = ref.data_schema_id
    expected = _SCHEMAS.get(schema_id)
    frames = 0
    preview_batches: list[dict[str, Any]] = []
    preview_frames = 0
    matching_frames = 0
    untimed_frames = 0
    layout: list[str] | None = None
    last_device_time: int | None = None
    frames_without_native_time = 0
    extrema: dict[str, tuple[float, float]] = {}
    observed_sensors: set[str] = set()
    sensor_frame_counts: dict[str, int] = {}
    zero_quaternions = 0
    zero_by_sensor: dict[str, int] = {}
    next_emg_index: int | None = None
    emg_continuity: dict[str, Any] = {
        "batchesChecked": 0,
        "transitionsChecked": 0,
        "forwardJumpCount": 0,
        "overlapOrResetCount": 0,
        "examples": [],
    }
    try:
        from mcap.reader import make_reader

        if schema_id == "generic.numeric_batch/1":
            # Same NumericBatch wire decoder as maintained feature extraction.
            from capture_analysis.loaders.numeric_batch import _decode

        for path in ref.mcap_paths:
            per_segment = 0
            matching = 0
            with path.open("rb") as fh:
                reader = make_reader(fh, validate_crcs=True)
                for schema, _channel, message in reader.iter_messages():
                    per_segment += 1
                    result["messagesChecked"] += 1
                    if expected is None:
                        continue
                    if schema is None or schema.name not in expected:
                        raise ValueError(f"{path.name}: message schema does not match {schema_id}")
                    matching += 1
                    if schema_id == "generic.numeric_batch/1":
                        channels, names, samples, device_times = _decode(message.data)
                        if not samples:
                            if device_times:
                                raise ValueError("numeric timestamps without sample frames")
                            continue
                        if channels < 1 or len(samples) % channels:
                            raise ValueError("numeric samples must contain whole channel frames")
                        n = len(samples) // channels
                        names = names or [f"ch{i}" for i in range(channels)]
                        if len(names) != channels or len(set(names)) != channels or not all(names):
                            raise ValueError("numeric channel names must match unique channels")
                        if layout is None:
                            layout = names
                        elif layout != names:
                            raise ValueError("numeric channel layout changes between batches")
                        if device_times and len(device_times) != n:
                            raise ValueError("numeric timestamps must match the frame count")
                        if any(b < a for a, b in zip(device_times, device_times[1:], strict=False)):
                            raise ValueError("numeric timestamps move backward within a batch")
                        if device_times:
                            if last_device_time is not None and device_times[0] < last_device_time:
                                raise ValueError(
                                    "numeric timestamps move backward between batches or segments "
                                    f"(previous {last_device_time}, next {device_times[0]})"
                                )
                            last_device_time = device_times[-1]
                        else:
                            # A nominal-rate clock is not proof of native timing continuity.
                            frames_without_native_time += n
                        if not all(math.isfinite(value) for value in samples):
                            raise ValueError("numeric samples contain NaN or infinity")
                        # All samples remain QC-checked; only the displayed excerpt is scoped.
                        keep: list[int] = []
                        if preview_window is None:
                            matching_frames += n
                            keep = list(range(min(n, _PREVIEW_FRAMES - preview_frames)))
                        elif not device_times:
                            untimed_frames += n
                        else:
                            start, end = preview_window
                            for i, native in enumerate(device_times):
                                session = int(message.log_time) + native - device_times[0]
                                if (start is None or session >= start) and (
                                    end is None or session <= end
                                ):
                                    matching_frames += 1
                                    if len(keep) < _PREVIEW_FRAMES - preview_frames:
                                        keep.append(i)
                        if keep:
                            preview_batches.append(
                                {
                                    "firstFrame": frames + keep[0],
                                    "displayFirstFrame": preview_frames,
                                    "segment": path.name,
                                    "messageIndex": per_segment - 1,
                                    "sessionTimeNs": str(message.log_time),
                                    "nativeTimeNs": [str(device_times[i]) for i in keep]
                                    if device_times
                                    else [],
                                    "mappedSessionTimeNs": [
                                        str(
                                            int(message.log_time)
                                            + device_times[i]
                                            - device_times[0]
                                        )
                                        for i in keep
                                    ]
                                    if device_times
                                    else [],
                                    "values": [
                                        samples[
                                            i * channels : i * channels
                                            + min(channels, _PREVIEW_CHANNELS)
                                        ]
                                        for i in keep
                                    ],
                                }
                            )
                            preview_frames += len(keep)
                        frames += n
                    elif schema_id == "emg.batch/1":
                        n, first_index, ids, limits = _decode_emg(message.data)
                        emg_continuity["batchesChecked"] += 1
                        if next_emg_index is not None:
                            emg_continuity["transitionsChecked"] += 1
                            if first_index != next_emg_index:
                                forward = first_index > next_emg_index
                                key = "forwardJumpCount" if forward else "overlapOrResetCount"
                                emg_continuity[key] += 1
                                if len(emg_continuity["examples"]) < 10:
                                    emg_continuity["examples"].append({
                                        "segment": path.name,
                                        "messageInSegment": per_segment,
                                        "kind": "forward_jump" if forward else "overlap_or_reset",
                                        # Strings retain int64 precision in JSON consumers.
                                        "expectedFirstSampleIndex": str(next_emg_index),
                                        "actualFirstSampleIndex": str(first_index),
                                    })
                        # Re-anchor after every batch, including an index reset.
                        # No origin is assumed for the first recorded batch.
                        next_emg_index = first_index + n
                        if layout is None:
                            layout = ids
                        elif layout != ids:
                            raise ValueError("EMG channel IDs change between batches")
                        for sid, (low, high) in zip(ids, limits, strict=True):
                            old = extrema.get(sid)
                            extrema[sid] = (
                                min(old[0], low) if old else low,
                                max(old[1], high) if old else high,
                            )
                        frames += n
                    elif schema_id == "imu.frame/1":
                        ids, zero = _decode_imu(message.data)
                        observed_sensors.update(ids)
                        for sensor_id in ids:
                            sensor_frame_counts[sensor_id] = (
                                sensor_frame_counts.get(sensor_id, 0) + 1
                            )
                        zero_quaternions += len(zero)
                        for sensor_id in zero:
                            zero_by_sensor[sensor_id] = zero_by_sensor.get(sensor_id, 0) + 1
                        frames += 1
            result["segmentsChecked"] += 1
            if not per_segment:
                raise ValueError(f"{path.name}: MCAP contains no data messages")
            if expected is not None and not matching:
                raise ValueError(f"{path.name}: no {schema_id} messages found")

        if expected is None:
            result.update(
                status="mcap_messages_checked",
                detail="MCAP messages parsed; this schema's sample values were not decoded",
            )
        elif frames == 0:
            raise ValueError(f"no {schema_id} sample frames found in MCAP segments")
        else:
            status = {
                "generic.numeric_batch/1": "numeric_samples_checked",
                "emg.batch/1": "emg_samples_checked",
                "imu.frame/1": "imu_frames_checked",
            }[schema_id]
            result.update(
                status=status,
                sampleFramesChecked=frames,
                detail="Decoded all declared-schema messages; checked shape and finite values",
            )
            if schema_id == "generic.numeric_batch/1":
                result["numericPreview"] = {
                    "schemaId": "capture.numeric_qc_preview/1",
                    "selection": "session_interval" if preview_window else "first_recorded_frames",
                    "intervalStartNs": str(preview_window[0])
                    if preview_window and preview_window[0] is not None
                    else None,
                    "intervalEndNs": str(preview_window[1])
                    if preview_window and preview_window[1] is not None
                    else None,
                    "matchingFrames": matching_frames,
                    "untimedFramesExcluded": untimed_frames,
                    "framesShown": preview_frames,
                    "framesChecked": frames,
                    "frameLimit": _PREVIEW_FRAMES,
                    "channelLimit": _PREVIEW_CHANNELS,
                    "channelIds": (layout or [])[:_PREVIEW_CHANNELS],
                    "totalChannels": len(layout or []),
                    "units": ref.units,
                    "batches": preview_batches,
                }
                result["framesWithoutNativeTimestamps"] = frames_without_native_time
                result["detail"] = (
                    "Decoded NumericBatch values and ordered native timestamps across "
                    "batches and segments where present; "
                    f"{frames_without_native_time} frame(s) have no native timestamps"
                )
            if layout:
                result["channelIds"] = layout
            if schema_id == "emg.batch/1":
                result["sampleIndexContinuity"] = emg_continuity
                # Exact flatline observations, not an electrode-condition diagnosis.
                result["constantChannels"] = sorted(
                    name for name, (low, high) in extrema.items() if low == high and frames >= 2
                )
            if schema_id == "imu.frame/1":
                result["sensorIds"] = sorted(observed_sensors)
                result["sensorFramePresence"] = {
                    sensor_id: {
                        "framesPresent": sensor_frame_counts[sensor_id],
                        "totalFrames": frames,
                    }
                    for sensor_id in sorted(observed_sensors)
                }
                result["partiallyPresentSensorIds"] = sorted(
                    sensor_id for sensor_id, count in sensor_frame_counts.items() if count < frames
                )
                result["zeroQuaternionSensorSamples"] = zero_quaternions
                result["zeroQuaternionSamplesBySensor"] = dict(sorted(zero_by_sensor.items()))
    except Exception as exc:  # noqa: BLE001 - malformed MCAP/codec errors are report data
        result.update(
            status="failed",
            sampleFramesChecked=None,
            detail=f"{type(exc).__name__}: {str(exc)[:220]}",
        )
    return result
