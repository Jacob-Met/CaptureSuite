# SPDX-License-Identifier: GPL-3.0-only
"""End-to-end Milestone 2: Python client drives C++ daemon over named pipe."""

from __future__ import annotations

import ctypes
import json
import subprocess
import time
from pathlib import Path

import pytest
from capture_protocol.control_client import ControlClient
from capture_protocol.generated.capture.v1 import control_pb2
from native_test_support import binary_path, native_environment, stop_owned_process


def _pipe_ready(pipe_name: str, timeout_ms: int = 200) -> bool:
    """True when a client can connect to the named pipe (does not consume it)."""
    return bool(ctypes.windll.kernel32.WaitNamedPipeW(pipe_name, timeout_ms))


REPO = Path(__file__).resolve().parents[2]


def _daemon_path() -> Path | None:
    target = binary_path(REPO, "daemon/capture_daemon.exe")
    return target if target.is_file() else None


@pytest.fixture(scope="module")
def daemon_proc(tmp_path_factory):
    daemon = _daemon_path()
    if daemon is None:
        pytest.skip("capture_daemon.exe not built (run cmake --build)")
    owned = tmp_path_factory.mktemp("native-daemon")
    env = native_environment(owned)
    instance = Path(env["LOCALAPPDATA"]) / "CaptureSuite" / "instance.json"
    assert not instance.exists()
    stdout_path = owned / "daemon_stdout.txt"
    stderr_path = owned / "daemon_stderr.txt"
    with (
        stdout_path.open("w", encoding="utf-8") as out,
        stderr_path.open("w", encoding="utf-8") as err,
    ):
        proc = subprocess.Popen([str(daemon)], stdout=out, stderr=err, cwd=REPO, env=env)
        try:
            pipe_name = None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    pytest.fail(
                        "daemon exited early:\n"
                        f"stdout={stdout_path.read_text(encoding='utf-8', errors='replace')}\n"
                        f"stderr={stderr_path.read_text(encoding='utf-8', errors='replace')}"
                    )
                if instance.is_file():
                    try:
                        data = json.loads(instance.read_text(encoding="utf-8"))
                        candidate = data.get("control_pipe")
                        if candidate and data.get("instance_id") and _pipe_ready(candidate):
                            pipe_name = candidate
                            break
                    except (json.JSONDecodeError, OSError, KeyError):
                        pass
                time.sleep(0.05)
            if pipe_name is None:
                pytest.fail("daemon did not publish a usable pipe in its isolated test directory")
            yield pipe_name
        finally:
            stop_owned_process(proc)


def test_multi_modality_record_with_disconnect(daemon_proc):
    pipe_name = daemon_proc
    with ControlClient(pipe_name) as client:
        sources = client.list_sources()
        assert not sources.error.code
        ids = {s.source_id for s in sources.sources}
        assert "sim.emg.main" in ids
        assert "sim.replay.demo" in ids
        assert any(
            s.source_type in ("camera", "sim.camera")
            or any(st.modality == "video" for st in s.streams)
            for s in sources.sources
        )

        created = client.create_session("py-e2e-m2")
        assert not created.error.code
        assert created.state == control_pb2.SESSION_STATE_PREPARING

        camera_id = next(
            (
                s.source_id
                for s in sources.sources
                if "video" in {st.modality for st in s.streams}
                or s.source_type in ("camera", "sim.camera")
            ),
            "sim.camera.sagittal",
        )
        selected = [
            camera_id,
            "sim.emg.main",
            "sim.imu.upper",
            "sim.radar.1",
            "sim.replay.demo",
        ]
        sel = client.select_sources(selected)
        assert not sel.error.code
        assert set(sel.selected_source_ids) == set(selected)

        started = client.start_selected()
        assert not started.error.code
        assert started.state == control_pb2.SESSION_STATE_RECORDING

        time.sleep(0.25)
        cp = client.create_checkpoint("Section A", "e2e")
        assert cp.checkpoint.checkpoint_id
        client.annotate("e2e note", "e2e")
        client.add_sync_anchor("clapper", "e2e")

        fault = client.inject_fault("sim.emg.main", "disconnect")
        assert not fault.error.code
        time.sleep(0.15)

        mid = client.get_recording_stats()
        assert mid.total_samples > 0
        others = [s for s in mid.streams if s.source_id != "sim.emg.main"]
        assert any(s.sample_count > 0 for s in others)

        client.inject_fault("sim.emg.main", "reconnect")
        time.sleep(0.1)

        token = client.request_stop().confirmation_token
        stopped = client.stop_session(token)
        assert not stopped.error.code
        assert stopped.state == control_pb2.SESSION_STATE_FINALIZED

        final = client.get_recording_stats()
        assert final.total_samples > 50
        assert final.checkpoint_count >= 1
        assert final.annotation_count >= 1
        assert final.sync_anchor_count >= 1
        emg_final = next(s for s in final.streams if s.source_id == "sim.emg.main")
        assert emg_final.gap_count >= 1


def test_bad_stop_token_rejected(daemon_proc):
    with ControlClient(daemon_proc) as client:
        client.create_session("py-e2e-badstop")
        client.select_sources(["sim.imu.upper"])
        started = client.start_selected()
        assert not started.error.code
        bad = client.stop_session("not-a-real-token")
        assert bad.error.code
        token = client.request_stop().confirmation_token
        ok = client.stop_session(token)
        assert not ok.error.code


def test_config_schema_and_apply(daemon_proc):
    import json

    with ControlClient(daemon_proc) as client:
        schema = client.get_config_schema("sim.emg.main")
        assert not schema.error.code
        doc = json.loads(schema.schema_json)
        assert doc["schema_revision"] == "sim.emg/1"
        assert schema.schema_revision == "sim.emg/1"
        assert "gain" in doc["properties"]

        applied = client.apply_config("sim.emg.main", {"gain": 2.0, "channel_count": 8})
        assert not applied.error.code
        assert applied.source.source_id == "sim.emg.main"
        assert json.loads(applied.effective_json)["channel_count"] == 8

        rejected = client.apply_config("sim.emg.main", {"gain": 2.0, "channel_count": 32})
        assert rejected.error.code == "VALIDATION_FAILED"

        radar = client.apply_config(
            "sim.radar.1", {"frame_rate_hz": 30, "chirp_bandwidth_mhz": 2050}
        )
        assert not radar.error.code
        assert "chirp_bandwidth_mhz" in list(radar.coerced_fields)
        assert json.loads(radar.effective_json)["chirp_bandwidth_mhz"] == 2100

        client.create_session("py-e2e-cfg")
        client.select_sources(["sim.emg.main"])
        client.start_selected()
        locked = client.apply_config("sim.emg.main", {"gain": 1.0})
        assert locked.error.code == "INVALID_STATE"
        token = client.request_stop().confirmation_token
        assert not client.stop_session(token).error.code


def test_camera_apply_config_proxied_when_worker_present(daemon_proc):
    """ApplyConfig for a GStreamer camera must round-trip into the worker."""
    import json

    with ControlClient(daemon_proc) as client:
        sources = client.list_sources()
        cam = next(
            (s for s in sources.sources if s.plugin_id == "camera.gstreamer" and s.enabled),
            None,
        )
        if cam is None:
            pytest.skip("camera.gstreamer worker not enabled in this daemon")

        schema = client.get_config_schema(cam.source_id)
        assert not schema.error.code
        assert schema.schema_revision == "camera.gstreamer/3"
        doc = json.loads(schema.schema_json)
        assert "encoder_preference" in doc["properties"]

        # capture_mode is only advertised when the device reports usable modes,
        # so a headless CI box without a camera still passes.
        capture_mode = doc["properties"].get("capture_mode")
        if capture_mode is not None:
            assert capture_mode["enum"], "capture_mode advertised with no modes"
            assert capture_mode["default"] in capture_mode["enum"]

        client.create_session("py-e2e-cam-cfg")
        applied = client.apply_config(
            cam.source_id,
            {
                "encoder_preference": "x264enc",
                "preview_enabled": True,
                "preview_max_rate_hz": 8,
            },
        )
        assert not applied.error.code, applied.error.message
        effective = json.loads(applied.effective_json)
        assert effective["encoder_preference"] == "x264enc"
        assert effective["preview_max_rate_hz"] == 8
        assert applied.schema_revision == "camera.gstreamer/3"


def test_start_all_ready_and_acknowledge_alert(daemon_proc):
    with ControlClient(daemon_proc) as client:
        client.create_session("py-e2e-startall")
        started = client.start_all_ready()
        assert not started.error.code
        assert started.state == control_pb2.SESSION_STATE_RECORDING
        assert len(started.started_source_ids) >= 2

        client.inject_fault("sim.emg.main", "disconnect")
        time.sleep(0.2)
        view = client.get_session_view()
        pending = [a for a in view.alerts if not a.acknowledged]
        assert pending, "expected a disconnect alert"
        ack = client.acknowledge_alert(pending[0].alert_id)
        assert not ack.error.code
        assert ack.alert.acknowledged
        view2 = client.get_session_view()
        matched = next(a for a in view2.alerts if a.alert_id == pending[0].alert_id)
        assert matched.acknowledged

        token = client.request_stop().confirmation_token
        assert not client.stop_session(token).error.code


def test_concurrent_clients_served(daemon_proc):
    """Several clients stay connected at once.

    Daemon-held alert acknowledgement and GetSessionView for late joiners both
    assume a second screen can attach mid-session, so a client must never have
    to disconnect before the next one is served.
    """
    with ControlClient(daemon_proc) as first, ControlClient(daemon_proc) as second:
        assert first.list_sources().sources
        assert second.list_sources().sources

        # A late joiner connects while the first two are still attached.
        with ControlClient(daemon_proc) as third:
            assert third.get_session_view().error.code == ""

        # Events keep flowing to a subscriber while another client issues RPCs.
        assert not first.subscribe_status(include_preview=False).error.code
        deadline = time.time() + 5
        received = 0
        while time.time() < deadline and received == 0:
            assert second.list_sources().sources
            if first.poll_event(0.25) is not None:
                received += 1
        assert received > 0, "subscriber received no events while a peer was active"
