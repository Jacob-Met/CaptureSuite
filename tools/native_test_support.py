# SPDX-License-Identifier: GPL-3.0-only
"""Native-test binary resolution and process ownership; never scan/kill by name."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def binary_path(repo: Path, relative: str) -> Path:
    """Use an explicit build or an existing local preset, never an installed app.

    An explicit missing binary is an error, not a skipped native CI test. Without
    an explicit build, normal Python-only development may skip unavailable native
    executables. This function performs no process launch or hardware access.
    """
    override = os.environ.get("CAPTURE_TEST_BUILD_DIR")
    if override:
        build = Path(override)
        if not build.is_absolute():
            build = repo / build
        target = build / relative
        if not target.is_file():
            raise FileNotFoundError(f"Required native-test binary missing: {target}")
        return target
    rel = Path(relative)
    candidates = []
    for preset, configuration in (("windows-debug", "Debug"), ("windows-release", "Release")):
        build = repo / "build" / preset
        candidates.extend((build / rel, build / rel.parent / configuration / rel.name))
    return next((p for p in candidates if p.is_file()), candidates[0])


def stop_owned_process(proc: subprocess.Popen, *, timeout: float = 8.0) -> None:
    """Stop only the supplied child handle and reap it, including timeout fallback."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout)


def native_environment(parent: Path) -> dict[str, str]:
    """Isolate native-test state and disable optional external hardware bridges.

    No camera/radar SDK worker or live preview bridge is enabled by this fixture.
    Built-in camera enumeration is unchanged: full native tests are run on the
    hosted Windows runner, not as physical-device qualification on an owner's PC.
    """
    env = os.environ.copy()
    for key, name in (
        ("LOCALAPPDATA", "local"),
        ("APPDATA", "roaming"),
        ("CAPTURE_SESSION_PARENT", "sessions"),
        ("CAPTURE_TEST_LOG_DIR", "logs"),
    ):
        directory = parent / name
        directory.mkdir(parents=True, exist_ok=False)
        env[key] = str(directory)
    env["CAPTURE_USE_CAMERA_WORKER"] = "0"
    env["CAPTURE_USE_RADAR_WORKER"] = "0"
    env["CAPTURE_IFX_PREVIEW"] = "0"
    env["CAPTURE_TEST_SIM_ONLY"] = "1"
    return env
