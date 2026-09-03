# SPDX-License-Identifier: GPL-3.0-only
"""Load imu.frame/1 into per-sensor arrays (RAM-guarded)."""

from __future__ import annotations

import numpy as np

from capture_analysis.loaders.base import estimate_imu_bytes, guard_ram
from capture_analysis.loaders.mcap_iter import decode_protobuf, iter_mcap_messages
from capture_analysis.types import LoadedImu, StreamRef, TimeWindow


def load_imu(
    stream: StreamRef,
    window: TimeWindow,
    *,
    max_ram_bytes: int,
) -> LoadedImu:
    stream.require_rate()
    guard_ram(
        estimate_imu_bytes(stream, window),
        max_ram_bytes=max_ram_bytes,
        stream=stream,
    )

    from capture_protocol.generated.capture.v1.data import imu_frame_pb2

    sensor_ids: list[str] | None = None
    rows: list[tuple[int, list]] = []

    for _name, payload, _log in iter_mcap_messages(
        stream.mcap_paths, schema_needle="imu.frame"
    ):
        msg = decode_protobuf(imu_frame_pb2.ImuFrame, payload)
        t = int(msg.timing.session_time_ns)
        if t < window.start_session_ns or t > window.end_session_ns:
            continue
        sensors = list(msg.sensors)
        ids = [s.sensor_id for s in sensors]
        if sensor_ids is None:
            sensor_ids = ids
        elif ids != sensor_ids:
            # Allow superset growth once; pad missing later.
            for sid in ids:
                if sid not in sensor_ids:
                    sensor_ids.append(sid)
        rows.append((t, sensors))

    if not rows or sensor_ids is None:
        empty = np.zeros((0, 0, 3), dtype=np.float32)
        return LoadedImu(
            sensor_ids=[],
            t_frame_ns=np.zeros(0, dtype=np.int64),
            accel=empty,
            gyro=empty,
            quat=np.zeros((0, 0, 4), dtype=np.float32),
            units=stream.units or "a.u.",
        )

    rows.sort(key=lambda r: r[0])
    f = len(rows)
    s = len(sensor_ids)
    index = {sid: i for i, sid in enumerate(sensor_ids)}
    t_ns = np.zeros(f, dtype=np.int64)
    accel = np.full((f, s, 3), np.nan, dtype=np.float32)
    gyro = np.full((f, s, 3), np.nan, dtype=np.float32)
    quat = np.full((f, s, 4), np.nan, dtype=np.float32)

    for i, (t, sensors) in enumerate(rows):
        t_ns[i] = t
        for sample in sensors:
            j = index.get(sample.sensor_id)
            if j is None:
                continue
            accel[i, j] = (sample.accel_x, sample.accel_y, sample.accel_z)
            gyro[i, j] = (sample.gyro_x, sample.gyro_y, sample.gyro_z)
            quat[i, j] = (sample.qw, sample.qx, sample.qy, sample.qz)

    return LoadedImu(
        sensor_ids=sensor_ids,
        t_frame_ns=t_ns,
        accel=accel,
        gyro=gyro,
        quat=quat,
        units=stream.units or "a.u.",
    )
