# SPDX-License-Identifier: GPL-3.0-only
import subprocess
from pathlib import Path
from types import SimpleNamespace

import native_test_support as native
import pytest


def test_explicit_missing_build_fails_instead_of_skip(tmp_path, monkeypatch):
    monkeypatch.setenv("CAPTURE_TEST_BUILD_DIR", "build/windows-release")
    with pytest.raises(FileNotFoundError, match="Required native-test binary"):
        native.binary_path(tmp_path, "daemon/capture_daemon.exe")


@pytest.mark.parametrize("layout", ["windows-release/daemon", "windows-debug/daemon/Debug"])
def test_supported_build_is_discovered(tmp_path, monkeypatch, layout):
    monkeypatch.delenv("CAPTURE_TEST_BUILD_DIR", raising=False)
    target = tmp_path / "build" / layout / "capture_daemon.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"fixture-not-executable")
    assert native.binary_path(tmp_path, "daemon/capture_daemon.exe") == target


def test_explicit_build_does_not_fall_back_to_other_binary(tmp_path, monkeypatch):
    target = tmp_path / "build/windows-debug/daemon/capture_daemon.exe"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"fixture-not-executable")
    monkeypatch.setenv("CAPTURE_TEST_BUILD_DIR", "missing")
    with pytest.raises(FileNotFoundError):
        native.binary_path(tmp_path, "daemon/capture_daemon.exe")


def test_native_state_does_not_touch_existing_instance(tmp_path, monkeypatch):
    existing = tmp_path / "owner-state/CaptureSuite/instance.json"
    existing.parent.mkdir(parents=True)
    existing.write_text("preserve-owner-instance")
    monkeypatch.setenv("LOCALAPPDATA", str(existing.parent.parent))
    env = native.native_environment(tmp_path / "test")
    assert Path(env["LOCALAPPDATA"]).is_relative_to(tmp_path / "test")
    assert existing.read_text() == "preserve-owner-instance"
    assert env["CAPTURE_USE_RADAR_WORKER"] == env["CAPTURE_USE_CAMERA_WORKER"] == "0"
    assert env["CAPTURE_IFX_PREVIEW"] == "0"
    assert env["CAPTURE_TEST_SIM_ONLY"] == "1"
    assert Path(env["CAPTURE_TEST_LOG_DIR"]).is_relative_to(tmp_path / "test")


def test_native_state_cannot_silently_reuse_directory(tmp_path):
    native.native_environment(tmp_path / "test")
    with pytest.raises(FileExistsError):
        native.native_environment(tmp_path / "test")


def test_cleanup_addresses_only_given_process():
    calls = []
    owned = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: calls.append("terminate"),
        wait=lambda **kwargs: calls.append("wait"),
        kill=lambda: calls.append("kill"),
    )
    native.stop_owned_process(owned)
    assert calls == ["terminate", "wait"]


def test_cleanup_timeout_kills_then_reaps_same_process():
    calls = []

    def wait(**kwargs):
        calls.append("wait")
        if calls.count("wait") == 1:
            raise subprocess.TimeoutExpired("synthetic-child", 1)

    owned = SimpleNamespace(
        poll=lambda: None,
        terminate=lambda: calls.append("terminate"),
        wait=wait,
        kill=lambda: calls.append("kill"),
    )
    native.stop_owned_process(owned)
    assert calls == ["terminate", "wait", "kill", "wait"]


def test_finished_process_not_signalled():
    native.stop_owned_process(SimpleNamespace(poll=lambda: 0))
