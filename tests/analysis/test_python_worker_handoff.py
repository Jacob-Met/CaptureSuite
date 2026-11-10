# SPDX-License-Identifier: GPL-3.0-only
"""Receive actual Python worker MCAP through normal session/analysis APIs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from capture_analysis import JobParams, hash_sources_tree, run
from capture_analysis.discover import discover_streams
from capture_analysis.loaders.numeric_batch import load_numeric_batch
from capture_analysis.types import TimeWindow
from capture_protocol.framing import Frame
from capture_protocol.generated.capture.v1 import worker_pb2
from capture_protocol.generated.capture.v1.common_pb2 import MessageType
from capture_protocol.generated.capture.v1.data import numeric_batch_pb2
from capture_worker.transport import MemoryTransport
from capture_worker.worker import Worker
from capture_worker.writer import McapSegmentWriter
from mcap.reader import make_reader


class ManualNumericWorker(Worker):
    def discover(self):
        return [
            {
                "source_id": "lab.force",
                "streams": [
                    {
                        "stream_id": "lab.force.batch",
                        "modality": "numeric",
                        "data_schema_id": "generic.numeric_batch/1",
                        "nominal_rate_hz": 10,
                        "units": "N",
                    }
                ],
            }
        ]

    def config_schema(self, source_id):
        return {"type": "object"}


def _rpc(worker, kind, request, reply_class):
    frame = worker.handle_frame(Frame(kind, 1, request.SerializeToString()))
    assert frame is not None
    reply = reply_class.FromString(frame.payload)
    assert not reply.error.code, reply.error.message
    return reply


def _package(path: Path) -> Path:
    path.mkdir()
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "session_schema_version": "1.0.0",
                "sessionId": "worker-handoff",
                "state": "finalized",
                "sourceIds": ["lab.force"],
            }
        )
    )
    stream = path / "sources/lab.force/streams/lab.force.batch"
    stream.mkdir(parents=True)
    (stream / "stream.json").write_text(
        json.dumps(
            {
                "sourceId": "lab.force",
                "streamId": "lab.force.batch",
                "modality": "numeric",
                "dataSchemaId": "generic.numeric_batch/1",
                "nominalRateHz": 10,
                "units": "N",
            }
        )
    )
    return path


def test_worker_recording_reopens_and_exports_without_moving_raw(tmp_path, monkeypatch):
    package = _package(tmp_path / "measured.mmsession")
    transport = MemoryTransport()
    worker = ManualNumericWorker(transport=transport)
    _rpc(
        worker,
        MessageType.MESSAGE_TYPE_START,
        worker_pb2.StartRequest(
            source_id="lab.force",
            session_t0_qpc_ns=8_000_000_000,
            session_package_path=str(package),
        ),
        worker_pb2.StartReply,
    )
    # An unrelated wall-clock change must not place data outside session time.
    monkeypatch.setattr("capture_worker.worker.time.time_ns", lambda: 1_900_000_000_000_000_000)
    monkeypatch.setattr("capture_worker.worker.time.perf_counter_ns", lambda: 8_100_000_000)
    native_times = [100_000_000_000 + i * 100_000_000 for i in range(10)]
    worker.emit_samples(
        "lab.force",
        [float(i) for i in range(10)],
        channel_count=1,
        channel_names=["force"],
        device_time_ns=native_times,
        units="N",
    )
    _rpc(
        worker,
        MessageType.MESSAGE_TYPE_STOP,
        worker_pb2.StopRequest(source_id="lab.force"),
        worker_pb2.StopReply,
    )
    sealed = [
        worker_pb2.SegmentSealed.FromString(payload)
        for kind, _, payload in transport.outbound
        if kind == MessageType.MESSAGE_TYPE_SEGMENT_SEALED
    ]
    assert len(sealed) == 1
    assert sealed[0].actual_count == 10
    assert sealed[0].end_session_time_ns == 1_000_000_000
    refs = discover_streams(package)
    assert len(refs) == 1 and len(refs[0].mcap_paths) == 1
    raw_path = refs[0].mcap_paths[0]
    with raw_path.open("rb") as stream:
        schema, _, message = next(make_reader(stream).iter_messages())
    assert message.log_time == 100_000_000
    assert (
        list(numeric_batch_pb2.NumericBatch.FromString(message.data).device_time_ns) == native_times
    )
    loaded = load_numeric_batch(refs[0], TimeWindow(0, 2_000_000_000), max_ram_bytes=8 * 1024**2)
    assert loaded.X.tolist() == [list(range(10))]
    assert loaded.t_sample_ns.tolist() == [100_000_000 + i * 100_000_000 for i in range(10)]
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="features", overwrite_job_id="worker-features"))
    tables = list((result.job_dir / "features").rglob("*.parquet"))
    assert len(tables) == 1
    import pandas as pd

    table = pd.read_parquet(tables[0])
    assert table["force_mean"].tolist() == [4.5]
    assert table["t_start_ns"].tolist() == [100_000_000]
    assert hash_sources_tree(package) == before


def _writer(package):
    return McapSegmentWriter(
        package_root=package,
        source_id="lab.force",
        stream_id="lab.force.batch",
        schema_name="capture.v1.data.NumericBatch",
        data_schema_id="generic.numeric_batch/1",
    )


def test_resuming_source_retains_previous_sealed_bytes(tmp_path):
    package = _package(tmp_path / "resume.mmsession")
    original = _writer(package)
    original.open()
    original.append(b"first retained sample", log_time_ns=1)
    first = original.close()
    assert first is not None
    digest = hashlib.sha256(first.absolute_path.read_bytes()).hexdigest()
    resumed = _writer(package)
    resumed.open()
    resumed.append(b"second retained sample", log_time_ns=2)
    second = resumed.close()
    assert second is not None and second.path != first.path
    assert first.absolute_path.name == "000000.mcap"
    assert second.absolute_path.name == "000001.mcap"
    assert hashlib.sha256(first.absolute_path.read_bytes()).hexdigest() == digest
    assert len(discover_streams(package)[0].mcap_paths) == 2


def test_explicit_existing_segment_is_refused_without_replacing_it(tmp_path):
    writer = _writer(tmp_path)
    writer.open(initial_segment_index=3)
    writer.append(b"preserve", log_time_ns=1)
    first = writer.close()
    assert first is not None
    before = first.absolute_path.read_bytes()
    with pytest.raises(FileExistsError):
        _writer(tmp_path).open(initial_segment_index=3)
    assert first.absolute_path.read_bytes() == before
