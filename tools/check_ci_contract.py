#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check the repository's CI dependency contract before expensive builds.

Checks the current CaptureSuite workflow format, not arbitrary YAML or GitHub
Actions security. A matching SHA establishes consistency, not upstream trust.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^\s*vcpkgGitCommitId:\s*[\"']?([\w.-]+)[\"']?\s*(?:#.*)?$", re.M)
MEMBERS = (
    "libs/python/capture_protocol",
    "libs/python/capture_session",
    "libs/python/capture_analysis[analysis]",
    "libs/python/capture_worker",
    "desktop[analysis]",
)
ENVIRONMENT = (
    "capture_protocol",
    "capture_session",
    "capture_analysis",
    "capture_worker",
    "capture_desktop",
    "numpy",
    "scipy",
    "pandas",
    "pyarrow",
    "matplotlib",
    "mcap",
    "yaml",
    "PySide6",
    "pyqtgraph",
    "grpc_tools",
    "pytest",
    "ruff",
)


def check_macos_bootstrap_contract(root: Path) -> list[str]:
    """Check the bounded Apple-silicon bootstrap without requiring a Mac host."""
    errors: list[str] = []
    try:
        presets = json.loads((root / "CMakePresets.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        return [f"Cannot read CMakePresets.json for macOS bootstrap: {type(exc).__name__}"]

    configure = {
        item.get("name"): item
        for item in presets.get("configurePresets", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    builds = {
        item.get("name"): item
        for item in presets.get("buildPresets", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    base = configure.get("macos-arm64-base")
    if not isinstance(base, dict):
        errors.append("Missing macos-arm64-base configure preset")
    else:
        if base.get("generator") != "Ninja":
            errors.append("macos-arm64-base must use Ninja")
        if base.get("toolchainFile") != "$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake":
            errors.append("macos-arm64-base must use the VCPKG_ROOT toolchain")
        cache = base.get("cacheVariables", {})
        expected = {
            "VCPKG_TARGET_TRIPLET": "arm64-osx",
            "CMAKE_OSX_ARCHITECTURES": "arm64",
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "CAPTURE_ENABLE_CAMERA_WORKER": "OFF",
            "CAPTURE_ENABLE_RADAR_WORKER": "OFF",
        }
        if not isinstance(cache, dict):
            errors.append("macos-arm64-base cacheVariables must be an object")
        else:
            for key, value in expected.items():
                if cache.get(key) != value:
                    errors.append(f"macos-arm64-base {key} must be {value}")

    for mode, build_type in (("debug", "Debug"), ("release", "Release")):
        name = f"macos-arm64-{mode}"
        preset = configure.get(name)
        if not isinstance(preset, dict):
            errors.append(f"Missing {name} configure preset")
            continue
        inherits = preset.get("inherits")
        if inherits != "macos-arm64-base" and not (
            isinstance(inherits, list) and "macos-arm64-base" in inherits
        ):
            errors.append(f"{name} must inherit macos-arm64-base")
        expected_dir = f"${{sourceDir}}/build/{name}"
        if preset.get("binaryDir") != expected_dir:
            errors.append(f"{name} binaryDir must be {expected_dir}")
        cache = preset.get("cacheVariables", {})
        if not isinstance(cache, dict) or cache.get("CMAKE_BUILD_TYPE") != build_type:
            errors.append(f"{name} CMAKE_BUILD_TYPE must be {build_type}")
        build = builds.get(name)
        if not isinstance(build, dict) or build.get("configurePreset") != name:
            errors.append(f"Missing matching {name} build preset")

    try:
        script = (root / "scripts" / "bootstrap-macos.sh").read_text(encoding="utf-8")
    except OSError:
        errors.append("Missing scripts/bootstrap-macos.sh")
    else:
        required_markers = (
            "uname -s",
            "uname -m",
            '"builtin-baseline"',
            "VCPKG_ROOT",
            "bootstrap-vcpkg.sh",
            'cmake --preset "$preset"',
            'cmake --build --preset "$preset"',
            "--provision-vcpkg",
            "refusing to reset an existing checkout",
        )
        for marker in required_markers:
            if marker not in script:
                errors.append(f"bootstrap-macos.sh missing guard/action: {marker}")
        if "brew install" in script or "port install" in script:
            errors.append("bootstrap-macos.sh must not mutate system package managers")

    return errors


def check(root: Path) -> list[str]:
    errors = []
    try:
        baseline = json.loads((root / "vcpkg.json").read_text(encoding="utf-8"))["builtin-baseline"]
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            errors.append("builtin-baseline must be a full 40-character lowercase commit SHA")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot read builtin-baseline: {type(exc).__name__}")
        baseline = None
    for name in ("ci.yml", "release.yml"):
        try:
            text = (root / ".github" / "workflows" / name).read_text(encoding="utf-8")
        except OSError:
            errors.append(f"Cannot read workflow {name}")
            continue
        pins = PIN.findall(text)
        if len(pins) != 1 or pins[0] != baseline:
            errors.append(f"{name}: one vcpkg commit pin must match builtin-baseline")
        if name == "ci.yml":
            if "python -m pip install -r requirements-ci.txt" not in text:
                errors.append("ci.yml must install the complete requirements-ci.txt environment")
            if "--check-environment" not in text:
                errors.append(
                    "ci.yml must check imports instead of silently skipping optional tests"
                )
            if "--no-tests=error" not in text:
                errors.append("ci.yml CTest must reject an empty test discovery")
            if "session_doctor -j 4" not in text:
                errors.append("ci.yml must build session_doctor before recovery integration")
            if "python -m pip install -r requirements-native-ci.txt" not in text:
                errors.append("ci.yml must install the native integration environment")
            if "CAPTURE_TEST_BUILD_DIR: build/windows-release" not in text:
                errors.append("ci.yml must bind native tests to the exact hosted build")
            if "python tools/run_native_ci_tests.py" not in text:
                errors.append("ci.yml must execute the zero-skip native integration runner")
            if "build/evidence/native-*/" not in text:
                errors.append("ci.yml must preserve native integration receipts")
    try:
        lines = (root / "requirements-ci.txt").read_text(encoding="utf-8").splitlines()
        entries = {line.strip() for line in lines if line.strip() and not line.startswith("#")}
        for member in MEMBERS:
            if f"-e ./{member}" not in entries:
                errors.append(f"Missing CI workspace member: {member}")
            path = member.split("[", 1)[0]
            if not (root / path / "pyproject.toml").is_file():
                errors.append(f"Missing workspace metadata: {path}")
    except OSError:
        errors.append("Cannot read requirements-ci.txt")
    try:
        native_lines = (
            (root / "requirements-native-ci.txt").read_text(encoding="utf-8").splitlines()
        )
        native_entries = {
            line.strip() for line in native_lines if line.strip() and not line.startswith("#")
        }
        for entry in (
            "-e ./libs/python/capture_protocol",
            "-e ./libs/python/capture_session",
        ):
            if entry not in native_entries:
                errors.append(f"Missing native CI dependency: {entry}")
        if not any(entry.startswith("pytest") for entry in native_entries):
            errors.append("Native CI environment must include pytest")
    except OSError:
        errors.append("Cannot read requirements-native-ci.txt")
    errors.extend(check_macos_bootstrap_contract(root))
    return errors


def check_registry(root: Path, registry: Path) -> list[str]:
    """Check direct port/features in the pinned checkout; vcpkg resolves transitives."""
    errors = []
    try:
        manifest = json.loads((root / "vcpkg.json").read_text(encoding="utf-8"))
        baseline = json.loads((registry / "versions/baseline.json").read_text(encoding="utf-8"))[
            "default"
        ]
        for dependency in manifest["dependencies"]:
            name = dependency if isinstance(dependency, str) else dependency["name"]
            if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name):
                errors.append("Invalid direct port name")
                continue
            if name not in baseline:
                errors.append(f"Pinned registry does not contain required port: {name}")
                continue
            features = [] if isinstance(dependency, str) else dependency.get("features", [])
            if features:
                port_path = registry / "ports" / name / "vcpkg.json"
                port = json.loads(port_path.read_text(encoding="utf-8"))
                supported = set(port.get("features", {})) | {"core", "default"}
                for feature in features:
                    if feature not in supported:
                        errors.append(f"Pinned port {name} lacks feature: {feature}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot validate registry contents: {type(exc).__name__}")
    return errors


def check_environment() -> list[str]:
    errors = []
    for module in ENVIRONMENT:
        try:
            importlib.import_module(module)
        except Exception as exc:
            errors.append(f"Required CI import {module} failed: {type(exc).__name__}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-environment", action="store_true")
    parser.add_argument("--vcpkg-root", type=Path)
    args = parser.parse_args()
    errors = check(ROOT)
    if args.vcpkg_root is not None:
        errors.extend(check_registry(ROOT, args.vcpkg_root))
    if args.check_environment:
        errors.extend(check_environment())
    print(json.dumps({"accepted": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
