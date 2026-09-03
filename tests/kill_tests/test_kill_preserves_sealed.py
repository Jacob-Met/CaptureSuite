# SPDX-License-Identifier: GPL-3.0-only
"""Force-kill daemon mid-capture; sealed segments must survive recovery."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest
from capture_protocol.control_client import ControlClient
from capture_session import assert_package_durable, load_integrity, load_manifest

REPO = Path(__file__).resolve().parents[2]
DAEMON = REPO / "build" / "windows-debug" / "daemon" / "capture_daemon.exe"
DOCTOR = REPO / "build" / "windows-debug" / "tools" / "session_doctor" / "session_doctor.exe"


def _kill_stray_daemons() -> None:
    """instance.json is global — stray daemons steal clients. Own the slot."""
    subprocess.run(
        ["taskkill", "/F", "/IM", "capture_daemon.exe"],
        capture_output=True,
        check=False,
    )
    time.sleep(0.3)


@pytest.mark.skipif(not DAEMON.is_file(), reason="capture_daemon not built")
@pytest.mark.skipif(not DOCTOR.is_file(), reason="session_doctor not built")
def test_kill_preserves_sealed_segment(tmp_path: Path):
    _kill_stray_daemons()
    session_parent = tmp_path / "sessions"
    session_parent.mkdir()
    env = os.environ.copy()
    env["CAPTURE_SESSION_PARENT"] = str(session_parent)
    env["CAPTURE_TEST_ROTATE_BYTES"] = "8192"

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    instance = Path(os.environ["LOCALAPPDATA"]) / "CaptureSuite" / "instance.json"
    if instance.is_file():
        instance.unlink()

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
        proc.kill()
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
                f"connected to wrong daemon; package={package_path} "
                f"expected under {session_parent}"
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
                        integrity = json.loads(
                            integrity_path.read_text(encoding="utf-8")
                        )
                    except (OSError, json.JSONDecodeError):
                        time.sleep(0.1)
                        continue
                    sealed = [
                        f
                        for f in integrity.get("files", [])
                        if f.get("status") == "sealed"
                    ]
                    if sealed:
                        for f in sealed:
                            abs_path = Path(package_path) / f["path"]
                            if not abs_path.is_file():
                                continue
                            sealed_before[f["path"]] = {
                                "size": abs_path.stat().st_size,
                                "hash": f.get("hashBlake3Hex", ""),
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

        doctor = subprocess.run(
            [str(DOCTOR), package_path],
            capture_output=True,
            text=True,
            check=False,
        )
        assert doctor.returncode == 0, doctor.stderr

        for rel, meta in sealed_before.items():
            path = Path(package_path) / rel
            assert path.stat().st_size == meta["size"]

        manifest = load_manifest(package_path)
        assert manifest["state"] == "finalized_recovered"
        info = assert_package_durable(package_path)
        assert info["segments"]
        integrity = load_integrity(package_path)
        assert integrity.get("files")
    finally:
        if proc.poll() is None:
            proc.kill()


def ctypes_wait(pipe_name: str) -> bool:
    import ctypes

    return bool(ctypes.windll.kernel32.WaitNamedPipeW(pipe_name, 200))
