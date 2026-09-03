# SPDX-License-Identifier: GPL-3.0-only
"""Record sim IMU + EMG briefly and verify on-disk protobuf schema fidelity.

No hardware required. Run against a live daemon (tools/run-daemon-gstreamer.ps1).
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402
from capture_protocol.generated.capture.v1.data import (  # noqa: E402
    emg_batch_pb2,
    imu_frame_pb2,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=1.5)
    args = ap.parse_args()

    try:
        from mcap.reader import make_reader
    except ImportError:
        print(
            "mcap package missing — install with:\n"
            r'  & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"'
            r" -m pip install mcap",
            file=sys.stderr,
        )
        return 2

    client = ControlClient()
    client.connect()
    try:
        sources = list(client.list_sources().sources)
        want = ["sim.emg.main", "sim.imu.upper"]
        have = {s.source_id for s in sources}
        missing = [s for s in want if s not in have]
        if missing:
            print(f"FAIL missing sources: {missing}")
            return 1

        sess = client.create_session(f"probe-imu-emg-{int(time.time())}")
        if sess.error.code:
            print("create_session:", sess.error.code, sess.error.message)
            return 1
        package = Path(sess.package_path)
        print("package:", package)

        sel = client.select_sources(want)
        if sel.error.code:
            print("select:", sel.error.code, sel.error.message)
            return 1
        start = client.start_selected()
        if start.error.code:
            print("start:", start.error.code, start.error.message)
            return 1
        if start.state != control_pb2.SESSION_STATE_RECORDING:
            print("expected RECORDING, got", start.state)
            return 1

        time.sleep(args.seconds)

        tok = client.request_stop()
        if tok.error.code:
            print("request_stop:", tok.error.code, tok.error.message)
            return 1
        stop = client.stop_session(tok.confirmation_token)
        if stop.error.code:
            print("stop:", stop.error.code, stop.error.message)
            return 1
        if stop.state != control_pb2.SESSION_STATE_FINALIZED:
            print("expected FINALIZED, got", stop.state)
            return 1

        imu_mcaps = sorted((package / "sources" / "sim.imu.upper").rglob("*.mcap"))
        emg_mcaps = sorted((package / "sources" / "sim.emg.main").rglob("*.mcap"))
        if not imu_mcaps or not emg_mcaps:
            print(f"FAIL mcap missing imu={len(imu_mcaps)} emg={len(emg_mcaps)}")
            return 1

        imu_ok = 0
        last_sensor = ""
        with imu_mcaps[0].open("rb") as fh:
            for schema, _ch, message in make_reader(fh).iter_messages():
                name = schema.name if schema else ""
                if "imu.frame" not in name:
                    continue
                frame = imu_frame_pb2.ImuFrame()
                frame.ParseFromString(message.data)
                if not frame.sensors:
                    print("FAIL ImuFrame has no sensors")
                    return 1
                if frame.timing.sequence_number <= 0:
                    print("FAIL ImuFrame missing sequence")
                    return 1
                if abs(frame.sensors[0].accel_z) < 5.0:
                    print("FAIL ImuFrame accel_z not near gravity", frame.sensors[0].accel_z)
                    return 1
                last_sensor = frame.sensors[0].sensor_id
                imu_ok += 1
                if imu_ok >= 3:
                    break
        if imu_ok < 3:
            print(f"FAIL decoded only {imu_ok} ImuFrame messages")
            return 1
        print(f"PASS imu: {imu_ok}+ ImuFrame msgs, first_sensor={last_sensor}")

        emg_ok = 0
        last_channels = 0
        last_samples = 0
        with emg_mcaps[0].open("rb") as fh:
            for schema, _ch, message in make_reader(fh).iter_messages():
                name = schema.name if schema else ""
                if "emg.batch" not in name:
                    continue
                batch = emg_batch_pb2.EmgBatch()
                batch.ParseFromString(message.data)
                if len(batch.channel_ids) < 8:
                    print("FAIL EmgBatch channel_ids", list(batch.channel_ids))
                    return 1
                if batch.sample_count <= 0:
                    print("FAIL EmgBatch empty sample_count")
                    return 1
                nbytes = len(batch.samples_f32_le)
                expect = len(batch.channel_ids) * batch.sample_count * 4
                if nbytes != expect:
                    print(f"FAIL EmgBatch bytes {nbytes} != {expect}")
                    return 1
                first = struct.unpack_from("<f", batch.samples_f32_le, 0)[0]
                if abs(first) > 1.5:
                    print("FAIL EmgBatch sample out of range", first)
                    return 1
                last_channels = len(batch.channel_ids)
                last_samples = batch.sample_count
                emg_ok += 1
                if emg_ok >= 3:
                    break
        if emg_ok < 3:
            print(f"FAIL decoded only {emg_ok} EmgBatch messages")
            return 1
        print(
            f"PASS emg: {emg_ok}+ EmgBatch msgs, "
            f"channels={last_channels} samples/msg={last_samples}"
        )
        print("PASS sim imu/emg record fidelity")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
