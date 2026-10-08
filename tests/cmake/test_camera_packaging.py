# SPDX-License-Identifier: GPL-3.0-only
"""Collect the camera's native packaging fixture in the existing Python CI job."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def inherited_loader_error_mode():
    """Let the expected Windows missing-DLL control exit without a dialog."""
    if sys.platform != "win32":
        yield
        return

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetErrorMode.argtypes = []
    kernel32.GetErrorMode.restype = ctypes.c_uint
    kernel32.SetErrorMode.argtypes = [ctypes.c_uint]
    kernel32.SetErrorMode.restype = ctypes.c_uint
    previous = kernel32.GetErrorMode()
    # Children inherit this process mode. Preserve all pre-existing flags.
    # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
    kernel32.SetErrorMode(previous | 0x0001 | 0x0002)
    try:
        yield
    finally:
        kernel32.SetErrorMode(previous)


@pytest.mark.skipif(
    sys.platform not in ("linux", "win32"),
    reason="The native camera packaging fixture supports Linux and Windows.",
)
def test_camera_runtime_native_loader():
    cmake = shutil.which("cmake")
    if cmake is None:
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail("Hosted camera packaging qualification requires CMake 3.28+.")
        pytest.skip("Native camera packaging qualification requires CMake 3.28+.")

    # The existing Windows Python job has VS 2022 installed but no developer shell.
    # Its Visual Studio generator discovers the compiler and SDK itself.
    env = os.environ.copy()
    if sys.platform == "win32":
        env["CMAKE_GENERATOR"] = "Visual Studio 17 2022"
        env["CMAKE_GENERATOR_PLATFORM"] = "x64"

    # The existing CI artifact step includes build/evidence. Keep the native build,
    # report and output together, outside the source snapshot and operator state.
    evidence = ROOT / "build/evidence" / f"camera-packaging-{uuid.uuid4().hex}"
    evidence.mkdir(parents=True, exist_ok=False)
    work = evidence / "native fixture with spaces"
    log_path = evidence / "fixture.log"
    command = [
        sys.executable,
        str(ROOT / "tests/cmake/camera_packaging/check_packaging.py"),
        "--source",
        str(ROOT),
        "--work",
        str(work),
        "--cmake",
        cmake,
    ]
    with inherited_loader_error_mode(), log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=240,
            check=False,
        )

    output = log_path.read_text(encoding="utf-8", errors="replace")
    assert result.returncode == 0, f"Native camera packaging fixture failed:\n{output}"
    report = json.loads((work / "report.json").read_text(encoding="utf-8"))
    assert report["platform"] == sys.platform
    assert report["passed"] is True, output
    assert report["checks"] and all(item["pass"] is True for item in report["checks"]), output
