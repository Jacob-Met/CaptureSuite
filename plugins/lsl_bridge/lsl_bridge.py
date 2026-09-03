# SPDX-License-Identifier: GPL-3.0-only
# SPDX-License-Identifier: Apache-2.0
"""Lab Streaming Layer (LSL) bridge worker for CaptureSuite."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from capture_protocol.generated.capture.v1 import source_pb2, worker_pb2
from capture_worker.preview import build_trace_preview
from capture_worker.transport import Transport
from capture_worker.worker import Worker

log = logging.getLogger("lsl_bridge")


def _try_import_pylsl():
    try:
        import pylsl  # type: ignore

        return pylsl
    except ImportError:
        return None


class LslBridgeWorker(Worker):
    plugin_version = "0.1.0"

    def __init__(
        self,
        *,
        plugin_id: str = "lsl.bridge",
        worker_id: str = "lsl-bridge",
        transport: Transport | None = None,
    ) -> None:
        super().__init__(plugin_id=plugin_id, worker_id=worker_id, transport=transport)
        self._name_filter = ""
        self._type_filter = ""
        self._chunk = 32
        self._timeout = 1.0
        self._threads: dict[str, threading.Thread] = {}
        self._stop = threading.Event()

    def discover(self) -> list[source_pb2.SourceInstance]:
        pylsl = _try_import_pylsl()
        sources: list[source_pb2.SourceInstance] = []
        if pylsl is None:
            src = source_pb2.SourceInstance()
            src.source_id = "lsl.unavailable"
            src.source_type = "lsl.bridge"
            src.alias = "LSL (pylsl not installed)"
            src.enabled = False
            src.plugin_id = self.plugin_id
            src.plugin_version = self.plugin_version
            src.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_UNAVAILABLE
            src.metadata["disabled_reason"] = "pylsl not installed"
            return [src]

        streams = pylsl.resolve_streams(wait_time=0.2)
        for info in streams:
            name = info.name()
            stype = info.type()
            if self._name_filter and self._name_filter not in name:
                continue
            if self._type_filter and self._type_filter.lower() not in stype.lower():
                continue
            uid = info.source_id() or info.uid()
            source_id = f"lsl.{uid}"
            src = source_pb2.SourceInstance()
            src.source_id = source_id
            src.source_type = "lsl.bridge"
            src.alias = name or source_id
            src.enabled = True
            src.plugin_id = self.plugin_id
            src.plugin_version = self.plugin_version
            src.lifecycle_state = source_pb2.SOURCE_LIFECYCLE_DISCOVERED
            src.metadata["lsl_type"] = stype
            src.metadata["lsl_hostname"] = info.hostname()
            dev = src.physical_devices.add()
            dev.vendor = "LSL"
            dev.model = stype or "stream"
            dev.serial = uid
            dev.stable_device_key = f"lsl.{uid}"
            src.physical_device_ids.append(dev.stable_device_key)
            stream = src.streams.add()
            stream.stream_id = f"{source_id}.batch"
            stream.source_id = source_id
            stream.modality = (stype or "numeric").lower()
            stream.data_schema_id = "generic.numeric_batch/1"
            stream.nominal_rate_hz = float(info.nominal_srate() or 0.0)
            stream.units = "a.u."
            stream.stream_class = source_pb2.STREAM_CLASS_SAMPLED
            stream.timestamp_source = "device"
            sources.append(src)
        return sources

    def config_schema(self, source_id: str) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "schema_revision": "lsl.bridge/1",
            "properties": {
                "name_filter": {"type": "string", "default": ""},
                "type_filter": {"type": "string", "default": ""},
                "chunk_size": {"type": "integer", "default": 32, "minimum": 1},
                "timeout_s": {"type": "number", "default": 1.0, "minimum": 0.05},
            },
        }

    def apply_config(self, source_id: str, document: dict[str, Any]) -> dict[str, Any]:
        self._name_filter = str(document.get("name_filter", self._name_filter))
        self._type_filter = str(document.get("type_filter", self._type_filter))
        self._chunk = int(document.get("chunk_size", self._chunk))
        self._timeout = float(document.get("timeout_s", self._timeout))
        return super().apply_config(
            source_id,
            {
                "name_filter": self._name_filter,
                "type_filter": self._type_filter,
                "chunk_size": self._chunk,
                "timeout_s": self._timeout,
            },
        )

    def start(self, source_id: str, start_req: worker_pb2.StartRequest) -> None:
        self._stop.clear()
        t = threading.Thread(target=self._pump, args=(source_id,), daemon=True)
        self._threads[source_id] = t
        t.start()

    def stop(self, source_id: str) -> None:
        self._stop.set()
        th = self._threads.pop(source_id, None)
        if th is not None:
            th.join(timeout=3.0)

    def _pump(self, source_id: str) -> None:
        pylsl = _try_import_pylsl()
        if pylsl is None:
            return
        uid = source_id.removeprefix("lsl.")
        streams = pylsl.resolve_byprop("source_id", uid, timeout=self._timeout)
        if not streams:
            streams = pylsl.resolve_streams(wait_time=self._timeout)
            streams = [s for s in streams if (s.source_id() or s.uid()) == uid]
        if not streams:
            log.warning("no LSL stream for %s", source_id)
            return
        inlet = pylsl.StreamInlet(streams[0], max_chunklen=self._chunk)
        ch = inlet.info().channel_count()
        names = [f"ch{i}" for i in range(ch)]
        seq = 0
        while not self._stop.is_set():
            samples, timestamps = inlet.pull_chunk(
                timeout=self._timeout, max_samples=self._chunk
            )
            if not samples:
                continue
            correction = 0.0
            try:
                correction = float(inlet.time_correction())
            except Exception:  # noqa: BLE001
                correction = 0.0
            device_times = [
                int((float(ts) + correction) * 1e9) for ts in (timestamps or [])
            ]
            flat: list[float] = []
            for row in samples:
                flat.extend(float(x) for x in row)
            self.emit_samples(
                source_id,
                flat,
                channel_count=ch,
                channel_names=names,
                device_time_ns=device_times or None,
            )
            last = [float(x) for x in samples[-1]]
            seq += 1
            frame = build_trace_preview(
                source_id=source_id,
                stream_id=f"{source_id}.batch",
                channel_names=names,
                samples=last,
                points_per_channel=1,
                session_time_ns=time.perf_counter_ns(),
                sequence=seq,
            )
            self.emit_preview(frame)
            time.sleep(0.001)
