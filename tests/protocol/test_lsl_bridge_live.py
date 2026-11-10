# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in real localhost LSL -> worker RPC -> retained MCAP integration.

Run with CAPTURE_RUN_LSL_TESTS=1 and pylsl installed. No transport or outlet
is mocked. Worker control uses the maintained MemoryTransport, not Win32 pipes.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CAPTURE_RUN_LSL_TESTS") != "1",
    reason="opt-in localhost LSL sockets (CAPTURE_RUN_LSL_TESTS=1)",
)


def test_real_outlets_record_and_stop_independently(tmp_path: Path) -> None:
    pylsl = pytest.importorskip("pylsl")
    from capture_protocol.framing import Frame
    from capture_protocol.generated.capture.v1 import source_pb2, worker_pb2
    from capture_protocol.generated.capture.v1.common_pb2 import MessageType
    from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
    from capture_worker.transport import MemoryTransport
    from lsl_bridge import LslBridgeWorker
    from mcap.reader import make_reader

    prefix = "CaptureSuite-live-" + uuid.uuid4().hex
    ids = [prefix + "-a", prefix + "-b"]
    outlets = [
        pylsl.StreamOutlet(pylsl.StreamInfo(uid, "Force", 1, 100, "double64", uid))
        for uid in ids
    ]
    producer_stop = threading.Event()

    def publish() -> None:
        while not producer_stop.is_set():
            for index, outlet in enumerate(outlets):
                outlet.push_sample([float((index + 1) * 17)], pylsl.local_clock())
            producer_stop.wait(0.01)

    producer = threading.Thread(target=publish, daemon=True)
    producer.start()
    worker = LslBridgeWorker(transport=MemoryTransport())
    worker.apply_config("", {"name_filter": prefix, "timeout_s": 0.2, "chunk_size": 8})
    source_ids = ["lsl." + uid for uid in ids]
    package = tmp_path / "live-lsl.mmsession"
    package.mkdir()

    def wait_for(predicate, label: str) -> None:
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.01)
        pytest.fail(label)

    def rpc(kind, request, reply_class):
        frame = worker.handle_frame(Frame(kind, 1, request.SerializeToString()))
        assert frame is not None
        reply = reply_class()
        reply.ParseFromString(frame.payload)
        assert not reply.error.code, reply.error.message
        return reply

    try:
        sources = worker._refresh_sources()
        assert {src.source_id for src in sources} == set(source_ids)
        assert all(
            src.streams[0].timestamp_source == source_pb2.TIMESTAMP_SOURCE_DEVICE
            for src in sources
        )
        for source_id in source_ids:
            rpc(
                MessageType.MESSAGE_TYPE_START,
                worker_pb2.StartRequest(
                    source_id=source_id,
                    session_t0_qpc_ns=time.perf_counter_ns(),
                    session_package_path=str(package),
                ),
                worker_pb2.StartReply,
            )
        wait_for(
            lambda: all(worker._sample_seq.get(sid, 0) >= 4 for sid in source_ids),
            "both real outlets must reach their MCAP writers",
        )
        rpc(
            MessageType.MESSAGE_TYPE_STOP,
            worker_pb2.StopRequest(source_id=source_ids[0]),
            worker_pb2.StopReply,
        )
        stopped_count = worker._sample_seq[source_ids[0]]
        survivor_count = worker._sample_seq[source_ids[1]]
        wait_for(
            lambda: worker._sample_seq[source_ids[1]] >= survivor_count + 4,
            "stopping the first outlet must not stop the second",
        )
        assert worker._sample_seq[source_ids[0]] == stopped_count
        rpc(
            MessageType.MESSAGE_TYPE_STOP,
            worker_pb2.StopRequest(source_id=source_ids[1]),
            worker_pb2.StopReply,
        )
        for index, source_id in enumerate(source_ids):
            files = list((package / "streams" / source_id).rglob("*.mcap"))
            assert len(files) == 1
            values = []
            with files[0].open("rb") as stream:
                for _, _, message in make_reader(stream).iter_messages():
                    batch = numeric_batch_pb2.NumericBatch.FromString(message.data)
                    assert batch.channel_count == 1
                    assert len(batch.device_time_ns) == len(batch.samples)
                    values.extend(batch.samples)
            assert len(values) >= 4
            assert set(values) == {float((index + 1) * 17)}
        assert not worker._threads
    finally:
        for source_id in source_ids:
            worker.stop(source_id)
            worker._seal_writer(source_id)
        producer_stop.set()
        producer.join(timeout=2.0)
