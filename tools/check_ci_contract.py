#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Check the developer build, test and Python environment contract.

The maintained entries are local uv and CMake commands. Deleted GitHub Actions
workflow files have no authority over the supported developer environment.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = (
    "libs/python/capture_protocol",
    "libs/python/capture_session",
    "libs/python/capture_analysis[analysis]",
    "libs/python/capture_worker",
    "desktop[analysis]",
)
WORKSPACE_SOURCES = (
    "capture-protocol",
    "capture-session",
    "capture-analysis",
    "capture-worker",
    "capture-desktop",
)
REQUIRED_EXTRAS = {
    "dev": {"pytest", "pytest-cov", "pytest-xdist", "pytest-qt", "ruff"},
    "analysis": {"numpy", "scipy", "pandas", "pyarrow", "matplotlib"},
}
DEV_COMMANDS = (
    "cmake --preset windows-release",
    "cmake --build build/windows-release --target capture_daemon session_doctor",
    "uv sync --all-packages --extra dev --extra analysis",
    "uv run --all-packages --extra dev --extra analysis "
    "python tools/check_ci_contract.py --check-environment",
    "uv run --all-packages --extra dev --extra analysis python -m pytest tests -q",
    "ctest --test-dir build/windows-release --output-on-failure --no-tests=error",
    '$env:CAPTURE_TEST_BUILD_DIR = "build/windows-release"',
    "uv run --all-packages --extra dev --extra analysis python tools/run_native_ci_tests.py",
)
NATIVE_RUNNER_MARKERS = (
    "CAPTURE_TEST_BUILD_DIR",
    "capture_daemon.exe",
    "session_doctor.exe",
    "NATIVE_TESTS",
    "Native integration tests were skipped",
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


def dependency_names(entries: list[str]) -> set[str]:
    names = set()
    for entry in entries:
        if isinstance(entry, str) and (match := re.match(r"[A-Za-z0-9_-]+", entry)):
            names.add(match.group().lower().replace("_", "-"))
    return names


def check(root: Path) -> list[str]:
    errors = []
    try:
        baseline = json.loads((root / "vcpkg.json").read_text(encoding="utf-8"))["builtin-baseline"]
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            errors.append("builtin-baseline must be a full 40-character lowercase commit SHA")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot read builtin-baseline: {type(exc).__name__}")

    # CaptureSuite uses uv's workspace, not the removed GitHub Actions workflows.
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        uv = project["tool"]["uv"]
        members = uv["workspace"]["members"]
        for member in MEMBERS:
            if member.split("[", 1)[0] not in members:
                errors.append(f"Missing uv workspace member: {member}")
        for source in WORKSPACE_SOURCES:
            if uv.get("sources", {}).get(source) != {"workspace": True}:
                errors.append(f"Missing local uv workspace source: {source}")
        extras = project["project"]["optional-dependencies"]
        for group, required in REQUIRED_EXTRAS.items():
            missing = required - dependency_names(extras.get(group, []))
            for name in sorted(missing):
                errors.append(f"Missing uv {group} dependency: {name}")
        pytest_options = project["tool"]["pytest"]["ini_options"]
        if "tests" not in pytest_options.get("testpaths", []):
            errors.append("Pytest must discover the real tests directory")
        options = shlex.split(pytest_options.get("addopts", ""))
        if "--maxprocesses=4" not in options or "--dist" not in options:
            errors.append("Pytest must retain the configured four-worker module gate")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot read uv developer workspace: {type(exc).__name__}")

    try:
        commands = {
            line.strip()
            for line in (root / "CONTRIBUTING.md").read_text(encoding="utf-8").splitlines()
        }
        for command in DEV_COMMANDS:
            if command not in commands:
                errors.append(f"Missing supported developer command: {command}")
    except OSError:
        errors.append("Cannot read supported developer commands")

    try:
        presets = json.loads((root / "CMakePresets.json").read_text(encoding="utf-8"))
        configure = {p["name"]: p for p in presets["configurePresets"]}
        builds = {p["name"]: p for p in presets["buildPresets"]}
        if configure.get("windows-release", {}).get("binaryDir") != (
            "${sourceDir}/build/windows-release"
        ):
            errors.append("Windows release preset must retain its native build directory")
        if builds.get("windows-release", {}).get("configurePreset") != "windows-release":
            errors.append("Windows release build must use the configured preset")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot read active CMake presets: {type(exc).__name__}")

    try:
        runner = (root / "tools/run_native_ci_tests.py").read_text(encoding="utf-8")
        for marker in NATIVE_RUNNER_MARKERS:
            if marker not in runner:
                errors.append(f"Native integration runner lost required behavior: {marker}")
    except OSError:
        errors.append("Cannot read native integration runner")

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
        for entry in ("-e ./libs/python/capture_protocol", "-e ./libs/python/capture_session"):
            if entry not in native_entries:
                errors.append(f"Missing native CI dependency: {entry}")
        if not any(entry.startswith("pytest") for entry in native_entries):
            errors.append("Native CI environment must include pytest")
    except OSError:
        errors.append("Cannot read requirements-native-ci.txt")
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
