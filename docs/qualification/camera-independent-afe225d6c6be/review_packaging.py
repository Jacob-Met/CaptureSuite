#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Independent camera package receiving controls over a copied native fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

DEPS = ("abseil_dll", "blake3", "libprotobuf", "lz4", "zstd")
WORKER = "capture_worker_camera.exe"
MARKER = "CAMERA_PACKAGING_PROBE_REACHED_MAIN"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cmake", required=True)
    parser.add_argument("--ninja", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = {"groups": [], "commands": [], "source_before": {}}
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "LD_PRELOAD", "DYLD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES"):
        env.pop(key, None)
    cwd = root / "independent unrelated cwd"
    cwd.mkdir()
    candidate = root / "candidate source with spaces"
    fixture = root / "candidate native work with spaces" / "fixture"
    built = root / "candidate native work with spaces" / "build"
    plugin = built / "daemon/Release/plugins/camera_gstreamer"
    legacy = built / "daemon/Release/workers/camera"
    original = built / "workers/camera/Release"
    for relative in ("workers/camera/CMakeLists.txt", "plugins/camera_gstreamer/plugin.json"):
        report["source_before"][relative] = sha(candidate / relative)

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        report["commands"].append(
            {
                "argv": command,
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        return result

    def launch(directory: Path, success: bool) -> subprocess.CompletedProcess[str]:
        result = run([str(directory / WORKER)])
        if success:
            assert result.returncode == 0 and result.stdout.strip() == MARKER
        else:
            assert result.returncode == 127 and MARKER not in result.stdout
        return result

    dynamic = run(["readelf", "-d", str(plugin / WORKER)])
    assert dynamic.returncode == 0
    needed = re.findall(r"\(NEEDED\).*\[(.*?)\]", dynamic.stdout)
    paths = re.findall(r"\((?:RUNPATH|RPATH)\).*\[(.*?)\]", dynamic.stdout)
    assert set(f"{name}.dll" for name in DEPS).issubset(needed)
    assert paths == ["$ORIGIN"], paths
    report["groups"].append(
        {
            "name": "actual ELF closure and origin-only search",
            "pass": True,
            "needed": needed,
            "search": paths,
        }
    )

    omissions = []
    for name in DEPS:
        path = plugin / f"{name}.dll"
        held = path.with_suffix(".dll.withheld")
        expected = sha(path)
        assert expected == sha(original / path.name) == sha(legacy / path.name)
        path.rename(held)
        try:
            result = launch(plugin, False)
            assert path.name in result.stderr
            launch(legacy, True)
        finally:
            held.rename(path)
        assert sha(path) == expected
        launch(plugin, True)
        omissions.append(
            {
                "dependency": path.name,
                "missing_exit": 127,
                "legacy_with_original_present_exit": 0,
                "restored_exit": 0,
            }
        )
    report["groups"].append(
        {
            "name": "each dependency is necessary and restoration recovers",
            "pass": True,
            "cases": omissions,
        }
    )

    relocated = root / "relocated camera (independent)"
    shutil.copytree(plugin, relocated)
    held_original = original.with_name(original.name + ".withheld")
    held_legacy = legacy.with_name(legacy.name + ".withheld")
    original.rename(held_original)
    legacy.rename(held_legacy)
    try:
        launch(plugin, True)
        launch(relocated, True)
    finally:
        held_legacy.rename(legacy)
        held_original.rename(original)
    report["groups"].append(
        {"name": "both plugin locations run without original or legacy trees", "pass": True}
    )

    multi = root / "multi config build with spaces"
    configure = run(
        [
            args.cmake,
            "-S",
            str(fixture),
            "-B",
            str(multi),
            "-G",
            "Ninja Multi-Config",
            "-DCMAKE_MAKE_PROGRAM=" + args.ninja,
        ]
    )
    assert configure.returncode == 0
    configs = {}
    for config in ("Debug", "Release"):
        build = run([args.cmake, "--build", str(multi), "--config", config, "--parallel", "2"])
        assert build.returncode == 0
        produced = multi / "workers/camera" / config
        packaged = multi / "daemon" / config
        configs[config] = {}
        for name in (WORKER, *(f"{dep}.dll" for dep in DEPS)):
            expected = sha(produced / name)
            for relative in ("workers/camera", "plugins/camera_gstreamer"):
                assert sha(packaged / relative / name) == expected
            configs[config][name] = expected
        for relative in ("workers/camera", "plugins/camera_gstreamer"):
            launch(packaged / relative, True)
        assert sha(packaged / "plugins/camera_gstreamer/plugin.json") == sha(
            candidate / "plugins/camera_gstreamer/plugin.json"
        )
    assert all(configs["Debug"][name] != configs["Release"][name] for name in configs["Debug"])
    report["groups"].append(
        {
            "name": "multi-config Debug and Release stage their own exact bytes",
            "pass": True,
            "config_hashes": configs,
        }
    )

    baseline_report = json.loads(
        (root / "baseline native work with spaces/report.json").read_text()
    )
    candidate_report = json.loads(
        (root / "candidate native work with spaces/report.json").read_text()
    )
    assert candidate_report["passed"] and len(candidate_report["checks"]) == 17
    failed = [item for item in baseline_report["checks"] if not item["pass"]]
    assert not baseline_report["passed"] and len(failed) == 7
    assert [item["returncode"] for item in failed if "returncode" in item] == [127]
    report["groups"].append(
        {
            "name": "exact production rollback restores missing-package failure",
            "pass": True,
            "baseline_passed": 10,
            "baseline_failed": 7,
            "candidate_passed": 17,
            "candidate_failed": 0,
        }
    )

    for relative, expected in report["source_before"].items():
        assert sha(candidate / relative) == expected
    report["groups"].append(
        {"name": "production source and manifest remain byte-identical", "pass": True}
    )
    report["passed"] = all(group["pass"] for group in report["groups"])
    report["limits"] = [
        "Native Linux CMake/ELF fixture, including Ninja Multi-Config and paths with spaces.",
        "No Windows DLL loader, MSVC/vcpkg, GStreamer, Media Foundation, daemon or hardware run.",
        "POST_BUILD packages a newly built target; "
        "this is not an automatic package repair contract.",
    ]
    report_path = root / "evidence/independent-review.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {"passed": report["passed"], "groups": report["groups"], "report": str(report_path)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
