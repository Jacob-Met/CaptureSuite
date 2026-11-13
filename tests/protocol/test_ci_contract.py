# SPDX-License-Identifier: GPL-3.0-only
import json
import shutil
from pathlib import Path

import check_ci_contract as contract
import pytest

SHA = "b322364f06308bdd24823f9d8f03fe0cc86fd46f"


@pytest.fixture
def configured(tmp_path: Path) -> Path:
    (tmp_path / "vcpkg.json").write_text(json.dumps({"builtin-baseline": SHA}))
    for source in (
        "pyproject.toml",
        "CMakePresets.json",
        "CONTRIBUTING.md",
        "tools/run_native_ci_tests.py",
    ):
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(contract.ROOT / source, target)
    (tmp_path / "requirements-ci.txt").write_text("\n".join(f"-e ./{m}" for m in contract.MEMBERS))
    (tmp_path / "requirements-native-ci.txt").write_text(
        "-e ./libs/python/capture_protocol\n-e ./libs/python/capture_session\npytest>=8\n"
    )
    for member in contract.MEMBERS:
        folder = tmp_path / member.split("[", 1)[0]
        folder.mkdir(parents=True)
        (folder / "pyproject.toml").write_text("[project]\n")
    return tmp_path


def test_real_repository_contract():
    assert contract.check(contract.ROOT) == []


def test_valid_complete_contract(configured):
    assert contract.check(configured) == []


@pytest.mark.parametrize("bad", ["2024.12.16", "b322364", "z" * 40, 42, None])
def test_invalid_registry_pin_is_rejected(configured, bad):
    (configured / "vcpkg.json").write_text(json.dumps({"builtin-baseline": bad}))
    assert contract.check(configured)


@pytest.mark.parametrize("section", ["configurePresets", "buildPresets"])
def test_missing_windows_preset_is_rejected(configured, section):
    p = configured / "CMakePresets.json"
    presets = json.loads(p.read_text())
    presets[section] = [item for item in presets[section] if item["name"] != "windows-release"]
    p.write_text(json.dumps(presets))
    assert any("Windows release" in error for error in contract.check(configured))


def test_missing_manifest_is_a_diagnostic(configured):
    (configured / "vcpkg.json").unlink()
    assert any("builtin-baseline" in e for e in contract.check(configured))


def test_optional_dependencies_cannot_be_omitted(configured):
    p = configured / "requirements-ci.txt"
    p.write_text(p.read_text().replace("-e ./desktop[analysis]", "-e ./desktop"))
    assert any("desktop[analysis]" in e for e in contract.check(configured))


@pytest.mark.parametrize(
    "command",
    [
        "cmake --preset windows-release",
        "cmake --build build/windows-release --target capture_daemon session_doctor",
        "uv sync --all-packages --extra dev --extra analysis",
        "uv run --all-packages --extra dev --extra analysis "
        "python tools/check_ci_contract.py --check-environment",
        "uv run --all-packages --extra dev --extra analysis python -m pytest tests -q",
        "ctest --test-dir build/windows-release --output-on-failure --no-tests=error",
        '$env:CAPTURE_TEST_BUILD_DIR = "build/windows-release"',
        "uv run --all-packages --extra dev --extra analysis python tools/run_native_ci_tests.py",
    ],
)
def test_missing_supported_developer_step_is_rejected(configured, command):
    p = configured / "CONTRIBUTING.md"
    text = p.read_text()
    assert command in text
    p.write_text(text.replace(command, "# removed", 1))
    assert any(command in error for error in contract.check(configured))


@pytest.mark.parametrize("marker", contract.NATIVE_RUNNER_MARKERS)
def test_native_runner_cannot_lose_critical_behavior(configured, marker):
    p = configured / "tools/run_native_ci_tests.py"
    text = p.read_text()
    assert marker in text
    p.write_text(text.replace(marker, "disabled-placeholder"))
    assert any(marker in error for error in contract.check(configured))


def test_uv_workspace_sources_are_required(configured):
    p = configured / "pyproject.toml"
    text = p.read_text()
    assert "capture-analysis = { workspace = true }" in text
    p.write_text(text.replace("capture-analysis = { workspace = true }", ""))
    assert any("capture-analysis" in error for error in contract.check(configured))


def test_uv_dev_dependencies_are_required(configured):
    p = configured / "pyproject.toml"
    text = p.read_text()
    assert "pytest-xdist>=3.8,<4" in text
    p.write_text(text.replace("pytest-xdist>=3.8,<4", "unrelated>=3.8,<4"))
    assert any("pytest-xdist" in error for error in contract.check(configured))


def test_uv_pytest_parallel_gate_is_required(configured):
    p = configured / "pyproject.toml"
    text = p.read_text()
    assert "--maxprocesses=4" in text
    p.write_text(text.replace("--maxprocesses=4", "--maxprocesses=1"))
    assert any("four-worker" in error for error in contract.check(configured))


def test_native_dependency_file_cannot_drop_capture_session(configured):
    p = configured / "requirements-native-ci.txt"
    p.write_text(p.read_text().replace("-e ./libs/python/capture_session\n", ""))
    assert any("capture_session" in error for error in contract.check(configured))


def test_broken_import_is_reported_without_aborting_other_checks(monkeypatch):
    seen = []

    def load(name):
        seen.append(name)
        if name == "numpy":
            raise ImportError("synthetic unavailable dependency")

    monkeypatch.setattr(contract.importlib, "import_module", load)
    errors = contract.check_environment()
    assert len(errors) == 1 and "numpy" in errors[0]
    assert seen == list(contract.ENVIRONMENT)


@pytest.fixture
def registry_case(tmp_path):
    root = tmp_path / "project"
    registry = tmp_path / "registry"
    root.mkdir()
    (registry / "versions").mkdir(parents=True)
    (registry / "ports/mcap").mkdir(parents=True)
    (root / "vcpkg.json").write_text(
        json.dumps({"dependencies": ["protobuf", {"name": "mcap", "features": ["lz4", "zstd"]}]})
    )
    (registry / "versions/baseline.json").write_text(
        json.dumps({"default": {"protobuf": {"baseline": "5.29.5"}, "mcap": {"baseline": "2.0.2"}}})
    )
    (registry / "ports/mcap/vcpkg.json").write_text(
        json.dumps({"features": {"lz4": {}, "zstd": {}}})
    )
    return root, registry


def test_required_registry_ports_and_features(registry_case):
    assert contract.check_registry(*registry_case) == []


def test_historical_missing_mcap_is_caught_before_cmake(registry_case):
    root, registry = registry_case
    p = registry / "versions/baseline.json"
    d = json.loads(p.read_text())
    del d["default"]["mcap"]
    p.write_text(json.dumps(d))
    assert contract.check_registry(root, registry) == [
        "Pinned registry does not contain required port: mcap"
    ]


def test_missing_port_feature_is_explicit(registry_case):
    root, registry = registry_case
    (registry / "ports/mcap/vcpkg.json").write_text('{"features": {"lz4": {}}}')
    assert contract.check_registry(root, registry) == ["Pinned port mcap lacks feature: zstd"]


def test_unreadable_registry_is_not_success(registry_case):
    root, registry = registry_case
    (registry / "versions/baseline.json").write_text("invalid")
    assert contract.check_registry(root, registry)


def test_port_paths_cannot_escape_registry(registry_case):
    root, registry = registry_case
    (root / "vcpkg.json").write_text('{"dependencies": ["../../private"]}')
    assert contract.check_registry(root, registry) == ["Invalid direct port name"]


def test_local_native_commands_each_fail_separately():
    lines = (contract.ROOT / "CONTRIBUTING.md").read_text().splitlines()
    ctest = "ctest --test-dir build/windows-release --output-on-failure --no-tests=error"
    build = "cmake --build build/windows-release --target capture_daemon session_doctor"
    native = (
        "uv run --all-packages --extra dev --extra analysis python tools/run_native_ci_tests.py"
    )
    assert lines.index(build) < lines.index(ctest) < lines.index(native)
    assert lines[lines.index(native) - 1] == (
        '$env:CAPTURE_TEST_BUILD_DIR = "build/windows-release"'
    )
    assert all(";" not in line and "&&" not in line for line in (build, ctest, native))


def test_only_generated_proto_headers_are_external():
    root = contract.ROOT
    text = (root / "libs/cpp/capture_proto/CMakeLists.txt").read_text()
    assert (
        "target_include_directories(capture_proto SYSTEM PUBLIC ${CAPTURE_PROTO_GEN_DIR})" in text
    )
    warnings = (root / "cmake/CompilerWarnings.cmake").read_text()
    assert "/W4" in warnings and "/WX" in warnings and "CAPTURE_WERROR" in warnings
    warning_gate = (root / "tools/check_cpp_warning_boundary.py").read_text()
    assert '"C4267" in output' in warning_gate
    assert '"owned_conversion"' in warning_gate
    assert (
        "target_include_directories(capture_storage PUBLIC"
        in (root / "libs/cpp/capture_storage/CMakeLists.txt").read_text()
    )
