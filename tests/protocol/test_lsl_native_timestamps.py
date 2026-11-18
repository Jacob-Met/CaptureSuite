# SPDX-License-Identifier: GPL-3.0-only
"""Compare retained device clocks to the exact timestamps supplied by a real LSL outlet."""

import os
import threading
import time
import uuid

import pytest


@pytest.mark.skipif(os.environ.get("CAPTURE_RUN_LSL_TESTS") != "1", reason="real localhost LSL")
def test_retained_native_timestamps_match_the_outlet(tmp_path):
    pylsl = pytest.importorskip("pylsl")
    from capture_protocol.framing import Frame
    from capture_protocol.generated.capture.v1 import worker_pb2
    from capture_protocol.generated.capture.v1.common_pb2 import MessageType
    from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
    from capture_worker.transport import MemoryTransport
    from lsl_bridge import LslBridgeWorker
    from mcap.reader import make_reader

    uid = "native-clock-" + uuid.uuid4().hex
    source_id = "lsl." + uid
    outlet = pylsl.StreamOutlet(pylsl.StreamInfo(uid, "Force", 1, 100, "double64", uid))
    worker = LslBridgeWorker(transport=MemoryTransport())
    worker.apply_config("", {"name_filter": uid, "timeout_s": 0.2, "chunk_size": 10})
    package = tmp_path / "native-clock.mmsession"
    package.mkdir()
    clocks = {}
    stopped = threading.Event()

    def emit():
        index = 0
        while not stopped.is_set():
            # The serial identifies each original sample even if startup misses a prefix.
            stamp = pylsl.local_clock() - 3.25
            clocks[index] = int(stamp * 1_000_000_000)
            outlet.push_sample([float(index)], stamp)
            index += 1
            stopped.wait(0.01)

    producer = threading.Thread(target=emit, daemon=True)
    producer.start()
    try:
        assert source_id in {s.source_id for s in worker._refresh_sources()}
        start = worker_pb2.StartRequest(
            source_id=source_id,
            session_t0_qpc_ns=time.perf_counter_ns(),
            session_package_path=str(package),
        )
        reply = worker.handle_frame(
            Frame(MessageType.MESSAGE_TYPE_START, 1, start.SerializeToString())
        )
        assert not worker_pb2.StartReply.FromString(reply.payload).error.code
        deadline = time.monotonic() + 10
        while worker._sample_seq.get(source_id, 0) < 100 and time.monotonic() < deadline:
            stopped.wait(0.02)
        stop = worker_pb2.StopRequest(source_id=source_id)
        reply = worker.handle_frame(
            Frame(MessageType.MESSAGE_TYPE_STOP, 2, stop.SerializeToString())
        )
        assert not worker_pb2.StopReply.FromString(reply.payload).error.code
    finally:
        stopped.set()
        producer.join(timeout=2)
        worker.stop(source_id)
        worker._seal_writer(source_id)

    segments = list((package / "sources" / source_id).rglob("*.mcap"))
    assert len(segments) == 1
    pairs = []
    with segments[0].open("rb") as stream:
        for _, _, message in make_reader(stream).iter_messages():
            batch = numeric_batch_pb2.NumericBatch.FromString(message.data)
            assert batch.channel_count == 1
            pairs.extend(zip(batch.samples, batch.device_time_ns, strict=True))
    assert len(pairs) >= 100
    indices = [int(value) for value, _ in pairs]
    assert indices == list(range(indices[0], indices[0] + len(pairs)))
    errors = [retained - clocks[int(value)] for value, retained in pairs]
    print(
        f"LSL_NATIVE {len(pairs)} pairs, {sum(e != 0 for e in errors)} mismatches, "
        f"maximum absolute error {max(map(abs, errors))} ns"
    )
    assert all(error == 0 for error in errors)
