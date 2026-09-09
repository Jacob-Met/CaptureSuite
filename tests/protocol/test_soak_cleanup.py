# SPDX-License-Identifier: GPL-3.0-only
"""Exercise capture cleanup with a fake client only; no daemon or hardware."""

import json
from types import SimpleNamespace as NS

import pytest
import soak_camera_radar as soak


def response(code=0, **kwargs):
    return NS(error=NS(code=code, message="synthetic"), **kwargs)


@pytest.fixture
def bench(tmp_path, monkeypatch):
    package = tmp_path / "synthetic.mmsession"
    package.mkdir()
    (package / "arrays.json").write_text("{}")
    (package / "manifest.json").write_text("{}")
    (package / "integrity.json").write_text(json.dumps({"files": [{"hash": "a"}, {"hash": "b"}]}))
    stream = package / "sources/radar.1/stream.json"
    stream.parent.mkdir(parents=True)
    stream.write_text("{}")

    class FakeClient:
        failure = None
        request_code = 0
        stop_code = 0
        final_state = soak.control_pb2.SESSION_STATE_FINALIZED
        requested = 0
        stopped = 0

        def connect(self):
            pass

        def list_sources(self):
            return NS(
                sources=[
                    NS(source_id="camera.1", source_type="camera", alias="Camera", streams=[]),
                    NS(
                        source_id="radar.1",
                        source_type="radar",
                        alias="Radar",
                        streams=[NS(modality="radar_doppler")],
                    ),
                ]
            )

        def stop_rehearsal(self):
            pass

        def create_session(self, name):
            return response(package_path=str(package))

        def select_sources(self, ids):
            assert ids == ["camera.1", "radar.1"]

        def start_selected(self):
            return response(state=soak.control_pb2.SESSION_STATE_RECORDING)

        def get_recording_stats(self):
            if self.failure is not None:
                raise self.failure
            return NS(streams=[NS(source_id=s, sample_count=5) for s in ["camera.1", "radar.1"]])

        def request_stop(self):
            self.requested += 1
            return response(self.request_code, confirmation_token="synthetic-token")

        def stop_session(self, token):
            assert token == "synthetic-token"
            self.stopped += 1
            return response(self.stop_code, state=self.final_state)

    client = FakeClient()
    clock = iter([0.0, 0.0, 0.0, 2.0])
    monkeypatch.setattr(soak, "ControlClient", lambda **kwargs: client)
    monkeypatch.setattr(soak, "time", NS(time=lambda: next(clock, 2.0), sleep=lambda _: None))
    monkeypatch.setattr(soak.sys, "argv", ["soak_camera_radar.py", "1"])
    return client, package


@pytest.mark.parametrize("request_code", [0, 7])
def test_capture_error_is_not_swallowed_by_stop_refusal(bench, request_code):
    client, _ = bench
    original = RuntimeError("synthetic capture failure")
    client.failure = original
    client.request_code = request_code
    with pytest.raises(RuntimeError) as raised:
        soak.main()
    assert raised.value is original
    assert client.requested == 1
    assert client.stopped == (1 if request_code == 0 else 0)


def test_missing_arrays_after_start_still_requests_stop(bench):
    client, package = bench
    (package / "arrays.json").unlink()
    assert soak.main() == 1
    assert client.requested == client.stopped == 1


def test_synthetic_success_still_finalizes(bench):
    client, _ = bench
    assert soak.main() == 0
    assert client.requested == client.stopped == 1


@pytest.mark.parametrize("field,value", [("request_code", 7), ("stop_code", 7), ("final_state", 0)])
def test_stop_error_never_reports_success(bench, field, value):
    client, _ = bench
    setattr(client, field, value)
    assert soak.main() == 1
    assert client.requested == 1


def test_interrupt_remains_visible_after_stop_refusal(bench):
    client, _ = bench
    client.failure = KeyboardInterrupt()
    client.request_code = 7
    with pytest.raises(KeyboardInterrupt):
        soak.main()
    assert client.requested == 1
