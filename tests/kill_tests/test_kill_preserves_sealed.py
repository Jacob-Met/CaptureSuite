# SPDX-License-Identifier: GPL-3.0-only
"""Force-kill daemon mid-capture; sealed segments must survive recovery."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest
from capture_protocol.control_client import ControlClient
from capture_session import assert_package_durable, load_integrity, load_manifest
from native_test_support import binary_path, native_environment, stop_owned_process

REPO = Path(__file__).resolve().parents[2]
DAEMON = binary_path(REPO, "daemon/capture_daemon.exe")
DOCTOR = binary_path(REPO, "tools/session_doctor/session_doctor.exe")


@pytest.mark.skipif(not DAEMON.is_file(), reason="capture_daemon not built")
@pytest.mark.skipif(not DOCTOR.is_file(), reason="session_doctor not built")
def test_kill_preserves_sealed_segment(tmp_path: Path):
    env = native_environment(tmp_path / "owned-native-state")
    session_parent = Path(env["CAPTURE_SESSION_PARENT"])
    env["CAPTURE_TEST_ROTATE_BYTES"] = "8192"
    log_dir = Path(env["CAPTURE_TEST_LOG_DIR"])
    instance = Path(env["LOCALAPPDATA"]) / "CaptureSuite" / "instance.json"
    assert not instance.exists()

    with (log_dir / "out.txt").open("w") as out, (log_dir / "err.txt").open("w") as err:
        proc = subprocess.Popen(
            [str(DAEMON)],
            stdout=out,
            stderr=err,
            cwd=str(REPO),
            env=env,
        )

    pipe = None
    our_instance_id = None
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.fail(
                "daemon exited early:\n"
                + (log_dir / "out.txt").read_text(encoding="utf-8", errors="replace")
                + (log_dir / "err.txt").read_text(encoding="utf-8", errors="replace")
            )
        if instance.is_file():
            try:
                data = json.loads(instance.read_text(encoding="utf-8"))
                candidate = data.get("control_pipe")
                iid = data.get("instance_id")
                if candidate and iid and ctypes_wait(candidate):
                    pipe = candidate
                    our_instance_id = iid
                    break
            except Exception:
                pass
        time.sleep(0.05)
    else:
        stop_owned_process(proc)
        pytest.fail("daemon pipe not ready")

    package_path = None
    sealed_before = {}
    try:
        with ControlClient(pipe) as client:
            assert client.instance_id == our_instance_id
            created = client.create_session("kill-test-session")
            assert not created.error.code, created.error.message
            package_path = created.package_path
            assert package_path
            assert Path(package_path).is_relative_to(session_parent), (
                f"connected to wrong daemon; package={package_path} expected under {session_parent}"
            )
            # High-rate sim streams only — rotate under CAPTURE_TEST_ROTATE_BYTES.
            sel = client.select_sources(["sim.emg.main", "sim.imu.upper", "sim.radar.1"])
            assert not sel.error.code, sel.error.message
            started = client.start_selected()
            assert not started.error.code, started.error.message

            # Wait until at least one sealed segment appears in integrity.json
            wait_deadline = time.time() + 30
            last_stats = None
            while time.time() < wait_deadline:
                try:
                    last_stats = client.get_recording_stats()
                except Exception:
                    last_stats = None
                integrity_path = Path(package_path) / "integrity.json"
                if integrity_path.is_file():
                    try:
                        integrity = json.loads(integrity_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        time.sleep(0.1)
                        continue
                    sealed = [f for f in integrity.get("files", []) if f.get("status") == "sealed"]
                    if sealed:
                        for f in sealed:
                            abs_path = Path(package_path) / f["path"]
                            if not abs_path.is_file():
                                continue
                            sealed_before[f["path"]] = {
                                "size": abs_path.stat().st_size,
                                "hash": f.get("hashBlake3Hex", ""),
                                "sha256": hashlib.sha256(abs_path.read_bytes()).hexdigest(),
                            }
                        if sealed_before:
                            break
                time.sleep(0.1)
            else:
                pytest.fail(
                    "no sealed segment before kill; "
                    f"stats={last_stats.total_samples if last_stats else None} "
                    f"pkg={package_path} "
                    f"integrity_exists={(Path(package_path) / 'integrity.json').is_file()}"
                )

        # Kill hard mid-session (UI/daemon crash).
        proc.kill()
        proc.wait(timeout=10)

        # Sealed files must be byte-identical before recovery.
        for rel, meta in sealed_before.items():
            path = Path(package_path) / rel
            assert path.is_file()
            assert path.stat().st_size == meta["size"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"]

        doctor = subprocess.run(
            [str(DOCTOR), package_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert doctor.returncode == 0, doctor.stderr

        for rel, meta in sealed_before.items():
            path = Path(package_path) / rel
            assert path.stat().st_size == meta["size"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"]

        manifest = load_manifest(package_path)
        assert manifest["state"] == "finalized_recovered"
        info = assert_package_durable(package_path)
        assert info["segments"]
        integrity = load_integrity(package_path)
        assert integrity.get("files")
    finally:
        stop_owned_process(proc)


def ctypes_wait(pipe_name: str) -> bool:
    import ctypes

    return bool(ctypes.windll.kernel32.WaitNamedPipeW(pipe_name, 200))
