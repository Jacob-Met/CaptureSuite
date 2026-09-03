# SPDX-License-Identifier: GPL-3.0-only
# SPDX-License-Identifier: Apache-2.0
"""Example sine-wave acquisition plugin (generic.numeric_batch/1)."""

from __future__ import annotations

import math
import threading
import time
from typing import Any

from capture_protocol.generated.capture.v1 import source_pb2, worker_pb2
from capture_worker.preview import build_trace_preview
from capture_worker.transport import Transport
from capture_worker.worker import Worker


class SineWorker(Worker):
    plugin_version = "0.1.0"

    def __init__(
        self,
        *,
        plugin_id: str = "example.sine",
        worker_id: str = "example-sine",
        transport: Transport | None = None,
    ) -> None:
        super().__init__(plugin_id=plugin_id, worker_id=worker_id, transport=transport)
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._rate_hz = 100.0
        self._channels = 2

    def discover(self) -> list[source_pb2.SourceInstance]:
        src = source_pb2.SourceInstance()
        src.source_id = "example.sine.main"
        src.source_type = "example.sine"
        src.alias = "Sine Demo"
        src.enabled = True
        src.plugin_id = self.plugin_id
        src.plugin_version = self.plugin_version
        src.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
        dev = src.physical_devices.add()
        dev.vendor = "CaptureSuite Example"
        dev.model = "SineGenerator"
        dev.serial = "SINE-001"
        dev.stable_device_key = "example.sine.SINE-001"
        src.physical_device_ids.append(dev.stable_device_key)
        stream = src.streams.add()
        stream.stream_id = "example.sine.main.batch"
        stream.source_id = src.source_id
        stream.modality = "numeric"
        stream.data_schema_id = "generic.numeric_batch/1"
        stream.nominal_rate_hz = self._rate_hz
        stream.units = "a.u."
        stream.stream_class = source_pb2.STREAM_CLASS_SAMPLED
        return [src]

    def config_schema(self, source_id: str) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "schema_revision": "example.sine/1",
            "properties": {
                "rate_hz": {"type": "number", "default": 100, "minimum": 1},
                "channels": {
                    "type": "integer",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 16,
                },
            },
        }

    def apply_config(self, source_id: str, document: dict[str, Any]) -> dict[str, Any]:
        self._rate_hz = float(document.get("rate_hz", self._rate_hz))
        self._channels = int(document.get("channels", self._channels))
        return super().apply_config(
            source_id, {"rate_hz": self._rate_hz, "channels": self._channels}
        )

    def start(self, source_id: str, start_req: worker_pb2.StartRequest) -> None:
        self._stop.clear()
        t = threading.Thread(target=self._run_source, args=(source_id,), daemon=True)
        self._threads[source_id] = t
        t.start()

    def stop(self, source_id: str) -> None:
        self._stop.set()
        th = self._threads.pop(source_id, None)
        if th is not None:
            th.join(timeout=2.0)

    def _run_source(self, source_id: str) -> None:
        t0 = time.perf_counter()
        period = 1.0 / max(1.0, self._rate_hz)
        names = [f"ch{i}" for i in range(self._channels)]
        seq = 0
        while not self._stop.is_set():
            t = time.perf_counter() - t0
            samples = [
                math.sin(2 * math.pi * (1.0 + c) * t) for c in range(self._channels)
            ]
            seq += 1
            self.emit_samples(
                source_id,
                samples,
                channel_count=self._channels,
                channel_names=names,
                device_time_ns=[time.time_ns()],
            )
            frame = build_trace_preview(
                source_id=source_id,
                stream_id="example.sine.main.batch",
                channel_names=names,
                samples=samples,
                points_per_channel=1,
                session_time_ns=time.perf_counter_ns(),
                sequence=seq,
            )
            self.emit_preview(frame)
            time.sleep(period)
