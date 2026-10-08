#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Build and launch a native dependency fixture through the real camera copy rules."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEPENDENCIES = ("abseil_dll", "blake3", "libprotobuf", "lz4", "zstd")
MARKER = "CAMERA_PACKAGING_PROBE_REACHED_MAIN"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> dict:
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=120, check=False
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def check(args: argparse.Namespace) -> dict:
    source = args.source.resolve(strict=True)
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    fixture = work / "fixture"
    camera = fixture / "workers/camera"
    (camera / "src").mkdir(parents=True)
    (fixture / "plugins/camera_gstreamer").mkdir(parents=True)
    (fixture / "cmake").mkdir()
    production = source / "workers/camera/CMakeLists.txt"
    manifest = source / "plugins/camera_gstreamer/plugin.json"
    report = {
        "source": str(source),
        "platform": sys.platform,
        "cmake_sha256": digest(production),
        "manifest_sha256": digest(manifest),
        "checks": [],
        "commands": [],
        "limits": "Native fixture packaging only; no real SDK, camera, daemon or hardware.",
    }
    shutil.copyfile(production, camera / "CMakeLists.txt")
    shutil.copyfile(manifest, fixture / "plugins/camera_gstreamer/plugin.json")
    shutil.copyfile(HERE / "CMakeLists.txt", fixture / "CMakeLists.txt")
    shutil.copyfile(HERE / "probe.cpp", camera / "src/main.cpp")
    for name in (
        "camera_enumerate", "worker_session", "gst_pipeline", "capture_mode",
        "capture_pipeline", "uvc_controls",
    ):
        (camera / f"src/{name}.cpp").write_text("// Fixture translation unit.\n")
    (fixture / "daemon.cpp").write_text("int main() { return 0; }\n")
    (fixture / "dependency.cpp").write_text(
        'extern "C" int PROBE_FUNCTION() { return PROBE_VALUE; }\n'
    )
    (fixture / "cmake/FindGStreamer.cmake").write_text(
        "add_library(GStreamer::GStreamer INTERFACE IMPORTED)\n"
        "set(GStreamer_FOUND TRUE)\n"
        'set(GStreamer_ROOT "${CMAKE_BINARY_DIR}/absent-sdk")\n'
    )
    build = work / "build"
    commands = [
        [args.cmake, "-S", str(fixture), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
        [args.cmake, "--build", str(build), "--config", "Release", "--parallel", "2"],
    ]
    for command in commands:
        result = run(command, work)
        report["commands"].append(result)
        if result["returncode"] != 0:
            report["setup_error"] = "Native fixture configure/build failed."
            return report

    original = build / "workers/camera/Release"
    daemon = build / "daemon/Release"
    worker = json.loads(manifest.read_text(encoding="utf-8"))["executable"]
    env = os.environ.copy()
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES"):
        env.pop(name, None)
    if os.name == "nt":
        system = Path(os.environ["SystemRoot"])
        env["PATH"] = os.pathsep.join((str(system / "System32"), str(system)))
    launch_cwd = work / "unrelated-cwd"
    launch_cwd.mkdir()
    for relative in ("workers/camera", "plugins/camera_gstreamer"):
        stage = daemon / relative
        for name in (worker, *(f"{dep}.dll" for dep in DEPENDENCIES)):
            target = stage / name
            report["checks"].append({
                "check": f"{relative}/{name}: exact staged bytes",
                "pass": target.is_file() and digest(target) == digest(original / name),
            })
        result = run([str(stage / worker)], launch_cwd, env)
        report["checks"].append({
            "check": f"{relative}: native dependency launch",
            "pass": result["returncode"] == 0 and result["stdout"].strip() == MARKER,
            **result,
        })
    packaged_manifest = daemon / "plugins/camera_gstreamer/plugin.json"
    report["checks"].append({
        "check": "plugin manifest: exact staged bytes",
        "pass": packaged_manifest.is_file() and digest(packaged_manifest) == digest(manifest),
    })
    control = work / "missing-protobuf"
    shutil.copytree(daemon / "plugins/camera_gstreamer", control)
    missing = control / "libprotobuf.dll"
    if missing.exists():
        missing.unlink()
        result = run([str(control / worker)], launch_cwd, env)
        report["checks"].append({
            "check": "removing only plugin-local libprotobuf.dll prevents main",
            "pass": result["returncode"] != 0 and MARKER not in result["stdout"],
            **result,
        })
    else:
        report["checks"].append({
            "check": "removing only plugin-local libprotobuf.dll prevents main",
            "pass": False,
            "reason": "Baseline package already lacks libprotobuf.dll.",
        })
    report["checks"].append({
        "check": "production source remained unchanged during qualification",
        "pass": digest(production) == report["cmake_sha256"]
        and digest(manifest) == report["manifest_sha256"],
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=HERE.parents[2])
    parser.add_argument("--work", type=Path, required=True, help="New evidence/build directory")
    parser.add_argument("--cmake", default="cmake")
    args = parser.parse_args()
    if sys.platform not in ("linux", "win32"):
        parser.error("This launch fixture supports native Windows and Linux toolchains.")
    report = check(args)
    report["passed"] = not report.get("setup_error") and all(
        item["pass"] for item in report["checks"]
    )
    (args.work / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"], "checks": report["checks"],
        "setup_error": report.get("setup_error"), "report": str(args.work / "report.json"),
    }, indent=2))
    return 2 if report.get("setup_error") else 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
