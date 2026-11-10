# SPDX-License-Identifier: GPL-3.0-only
"""Real LSL -> Python SDK -> native SessionPackage -> ordinary analysis.

The small C++ fixture drives the maintained SessionPackage API; it never writes
sample files or hand-builds reader metadata. The native Windows daemon/pipe
transport and hardware synchronization remain outside this portable test.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("CAPTURE_RUN_LSL_TESTS") != "1"
    or not os.environ.get("CAPTURE_NATIVE_PACKAGE_FIXTURE"),
    reason="requires real LSL and the compiled native SessionPackage fixture",
)


def test_live_worker_reopens_native_package_and_resumes_without_loss(tmp_path):
    pylsl = pytest.importorskip("pylsl")
    import numpy as np
    import pandas as pd
    from capture_analysis import JobParams, hash_sources_tree, run
    from capture_analysis.discover import discover_streams
    from capture_analysis.loaders.numeric_batch import load_numeric_batch
    from capture_analysis.windows import full_window
    from capture_protocol.framing import Frame
    from capture_protocol.generated.capture.v1 import worker_pb2
    from capture_protocol.generated.capture.v1.common_pb2 import MessageType
    from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
    from capture_session.package_reader import load_review_summary
    from capture_worker.transport import MemoryTransport
    from lsl_bridge import LslBridgeWorker
    from mcap.reader import make_reader

    prefix = "CaptureSuite-native-" + uuid.uuid4().hex
    ids = [prefix + "-a", prefix + "-b"]
    source_ids = ["lsl." + uid for uid in ids]
    rates, channels = [23, 37], [2, 1]
    outlets = [
        pylsl.StreamOutlet(pylsl.StreamInfo(uid, "Force", ch, rate, "double64", uid))
        for uid, ch, rate in zip(ids, channels, rates, strict=True)
    ]
    producer_stop = threading.Event()

    def publish(index):
        sequence = 0
        while not producer_stop.is_set():
            now = pylsl.local_clock()
            frames = [
                [index * 10000.0 + sequence + j + c / 10 for c in range(channels[index])]
                for j in range(4)
            ]
            timestamps = [now - (3 - j) / rates[index] for j in range(4)]
            outlets[index].push_chunk(frames, timestamps)
            sequence += 4
            producer_stop.wait(4 / rates[index])

    producers = [threading.Thread(target=publish, args=(i,), daemon=True) for i in range(2)]
    for producer in producers:
        producer.start()
    transport = MemoryTransport()
    worker = LslBridgeWorker(transport=transport)
    worker.apply_config("", {"name_filter": prefix, "chunk_size": 8, "timeout_s": 0.2})
    process = subprocess.Popen(
        [os.environ["CAPTURE_NATIVE_PACKAGE_FIXTURE"]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )

    def native(request):
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        response = json.loads(process.stdout.readline())
        assert response["ok"], response
        return response

    def rpc(kind, request, reply_class):
        frame = worker.handle_frame(Frame(kind, 1, request.SerializeToString()))
        assert frame is not None
        reply = reply_class.FromString(frame.payload)
        assert not reply.error.code, reply.error.message

    def wait_for(predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        pytest.fail("live outlets did not deliver expected batches")

    def start(source_id):
        rpc(
            MessageType.MESSAGE_TYPE_START,
            worker_pb2.StartRequest(
                source_id=source_id, session_t0_qpc_ns=t0, session_package_path=str(package)
            ),
            worker_pb2.StartReply,
        )

    def stop(source_id):
        rpc(
            MessageType.MESSAGE_TYPE_STOP,
            worker_pb2.StopRequest(source_id=source_id),
            worker_pb2.StopReply,
        )

    try:
        sources = worker._refresh_sources()
        assert {source.source_id for source in sources} == set(source_ids)
        t0 = time.perf_counter_ns()
        package = Path(
            native(
                {
                    "operation": "create",
                    "parent": str(tmp_path),
                    "session_id": prefix,
                    "t0_ns": t0,
                    "wall_utc": datetime.now(UTC).isoformat(),
                    "streams": [
                        {
                            "source_id": source.source_id,
                            "stream_id": stream.stream_id,
                            "modality": stream.modality,
                            "nominal_rate_hz": stream.nominal_rate_hz,
                            "alias": source.alias,
                            "source_type": source.source_type,
                        }
                        for source in sources
                        for stream in source.streams
                    ],
                }
            )["root"]
        )
        for source_id in source_ids:
            start(source_id)
        wait_for(lambda: all(worker._sample_seq.get(sid, 0) >= 4 for sid in source_ids))
        stop(source_ids[0])
        first = next((package / "sources" / source_ids[0]).rglob("*.mcap"))
        first_digest = hashlib.sha256(first.read_bytes()).hexdigest()
        survivor_count = worker._sample_seq[source_ids[1]]
        stopped_count = worker._sample_seq[source_ids[0]]
        wait_for(lambda: worker._sample_seq[source_ids[1]] >= survivor_count + 4)
        assert worker._sample_seq[source_ids[0]] == stopped_count
        start(source_ids[0])
        wait_for(lambda: worker._sample_seq[source_ids[0]] >= stopped_count + 4)
        for source_id in source_ids:
            stop(source_id)
        assert hashlib.sha256(first.read_bytes()).hexdigest() == first_digest
        for kind, _, payload in transport.outbound:
            if kind != MessageType.MESSAGE_TYPE_SEGMENT_SEALED:
                continue
            event = worker_pb2.SegmentSealed.FromString(payload)
            native(
                {
                    "operation": "sealed",
                    **{
                        field: getattr(event, field)
                        for field in (
                            "path",
                            "source_id",
                            "stream_id",
                            "size_bytes",
                            "hash_blake3_hex",
                            "start_session_time_ns",
                            "end_session_time_ns",
                            "actual_count",
                            "segment_index",
                        )
                    },
                }
            )
        native({"operation": "finalize"})
        assert process.wait(timeout=5) == 0
        manifest = json.loads((package / "manifest.json").read_text())
        assert manifest["state"] == "finalized"
        refs = discover_streams(package)
        assert len(refs) == 2
        raw_before = hash_sources_tree(package)
        counts = {}
        loaded_by_stream = {}
        window = full_window(load_review_summary(package))
        for ref in refs:
            raw_frames, raw_times = [], []
            for path in ref.mcap_paths:
                with path.open("rb") as stream:
                    for _, _, message in make_reader(stream).iter_messages():
                        batch = numeric_batch_pb2.NumericBatch.FromString(message.data)
                        n = len(batch.samples) // batch.channel_count
                        raw_frames.extend(np.array(batch.samples).reshape(n, batch.channel_count))
                        raw_times.extend(
                            message.log_time + value - batch.device_time_ns[0]
                            for value in batch.device_time_ns
                        )
            loaded = load_numeric_batch(ref, window, max_ram_bytes=16 * 1024**2)
            order = np.argsort(raw_times, kind="stable")
            assert np.array_equal(loaded.X.T, np.array(raw_frames)[order])
            assert np.array_equal(loaded.t_sample_ns, np.array(raw_times)[order])
            assert loaded.t_sample_ns.max() < 10**10
            counts[ref.stream_id] = len(raw_frames)
            loaded_by_stream[ref.stream_id] = loaded
        result = run(package, JobParams(command="features", overwrite_job_id="live-handoff"))
        tables = list((result.job_dir / "features").rglob("*.parquet"))
        assert len(tables) == 2
        schema = json.loads((result.job_dir / "features/_schema.json").read_text())
        for path in tables:
            table = pd.read_parquet(path)
            entry = schema["tables"][path.relative_to(result.job_dir).as_posix()]
            loaded = loaded_by_stream[entry["streamId"]]
            n = round(loaded.fs_hz)
            assert table["ch0_mean"].iloc[0] == pytest.approx(loaded.X[0, :n].mean())
            assert table["t_start_ns"].iloc[0] == loaded.t_sample_ns[0]
            assert table["t_end_ns"].iloc[0] == loaded.t_sample_ns[n - 1] + round(
                1e9 / loaded.fs_hz
            )
            csv = pd.read_csv(path.with_suffix(".csv"))
            assert csv["ch0_mean"].iloc[0] == pytest.approx(table["ch0_mean"].iloc[0])
        assert hash_sources_tree(package) == raw_before
        (tmp_path / "live-handoff-evidence.json").write_text(
            json.dumps(
                {
                    "package": str(package),
                    "counts": counts,
                    "first_segment_sha256": first_digest,
                    "job": str(result.job_dir),
                    "boundary": "real LSL + Worker RPC + native SessionPackage + ordinary features",
                },
                indent=2,
            )
        )
    finally:
        for source_id in source_ids:
            worker.stop(source_id)
            worker._seal_writer(source_id)
        producer_stop.set()
        for producer in producers:
            producer.join(timeout=2)
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
