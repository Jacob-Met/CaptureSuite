# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path

import check_ci_contract as contract
import pytest

SHA = "b322364f06308bdd24823f9d8f03fe0cc86fd46f"


def _write_macos_bootstrap_contract(root: Path) -> None:
    presets = {
        "version": 6,
        "configurePresets": [
            {
                "name": "macos-arm64-base",
                "hidden": True,
                "generator": "Ninja",
                "cacheVariables": {
                    "VCPKG_TARGET_TRIPLET": "arm64-osx",
                    "CMAKE_OSX_ARCHITECTURES": "arm64",
                    "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
                    "CAPTURE_ENABLE_CAMERA_WORKER": "OFF",
                    "CAPTURE_ENABLE_RADAR_WORKER": "OFF",
                },
                "toolchainFile": "$env{VCPKG_ROOT}/scripts/buildsystems/vcpkg.cmake",
            },
            {
                "name": "macos-arm64-debug",
                "inherits": "macos-arm64-base",
                "binaryDir": "${sourceDir}/build/macos-arm64-debug",
                "cacheVariables": {"CMAKE_BUILD_TYPE": "Debug"},
            },
            {
                "name": "macos-arm64-release",
                "inherits": "macos-arm64-base",
                "binaryDir": "${sourceDir}/build/macos-arm64-release",
                "cacheVariables": {"CMAKE_BUILD_TYPE": "Release"},
            },
        ],
        "buildPresets": [
            {"name": "macos-arm64-debug", "configurePreset": "macos-arm64-debug"},
            {"name": "macos-arm64-release", "configurePreset": "macos-arm64-release"},
        ],
    }
    (root / "CMakePresets.json").write_text(json.dumps(presets))
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "bootstrap-macos.sh").write_text(
        "uname -s\n"
        "uname -m\n"
        'python -c \'print("builtin-baseline")\'\n'
        "VCPKG_ROOT=/tmp/vcpkg\n"
        "bootstrap-vcpkg.sh\n"
        'cmake --preset "$preset"\n'
        'cmake --build --preset "$preset"\n'
        "--provision-vcpkg\n"
        "refusing to reset an existing checkout\n"
    )


@pytest.fixture
def configured(tmp_path: Path) -> Path:
    (tmp_path / "vcpkg.json").write_text(json.dumps({"builtin-baseline": SHA}))
    folder = tmp_path / ".github/workflows"
    folder.mkdir(parents=True)
    for name in ("ci.yml", "release.yml"):
        (folder / name).write_text(
            f'vcpkgGitCommitId: "{SHA}" # version pin\n'
            "python -m pip install -r requirements-ci.txt\n"
            "python tools/check_ci_contract.py --check-environment\n"
            "ctest --no-tests=error\n"
            "cmake --build x --target session_doctor -j 4\n"
            "python -m pip install -r requirements-native-ci.txt\n"
            "CAPTURE_TEST_BUILD_DIR: build/windows-release\n"
            "python tools/run_native_ci_tests.py\n"
            "build/evidence/native-*/\n"
        )
    (tmp_path / "requirements-ci.txt").write_text("\n".join(f"-e ./{m}" for m in contract.MEMBERS))
    (tmp_path / "requirements-native-ci.txt").write_text(
        "-e ./libs/python/capture_protocol\n-e ./libs/python/capture_session\npytest>=8\n"
    )
    for member in contract.MEMBERS:
        folder = tmp_path / member.split("[", 1)[0]
        folder.mkdir(parents=True)
        (folder / "pyproject.toml").write_text("[project]\n")
    _write_macos_bootstrap_contract(tmp_path)
    return tmp_path


def test_real_repository_contract():
    assert contract.check(contract.ROOT) == []


def test_valid_complete_contract(configured):
    assert contract.check(configured) == []


@pytest.mark.parametrize("bad", ["2024.12.16", "b322364", "z" * 40, 42, None])
def test_invalid_registry_pin_is_rejected(configured, bad):
    (configured / "vcpkg.json").write_text(json.dumps({"builtin-baseline": bad}))
    assert contract.check(configured)


@pytest.mark.parametrize("name", ["ci.yml", "release.yml"])
def test_divergent_workflow_pin_is_rejected(configured, name):
    p = configured / ".github/workflows" / name
    p.write_text(p.read_text().replace(SHA, "a" * 40))
    assert any(name in e for e in contract.check(configured))


def test_missing_manifest_is_a_diagnostic(configured):
    (configured / "vcpkg.json").unlink()
    assert any("builtin-baseline" in e for e in contract.check(configured))


def test_optional_dependencies_cannot_be_omitted(configured):
    p = configured / "requirements-ci.txt"
    p.write_text(p.read_text().replace("-e ./desktop[analysis]", "-e ./desktop"))
    assert any("desktop[analysis]" in e for e in contract.check(configured))


@pytest.mark.parametrize("gate", ["--check-environment", "--no-tests=error"])
def test_missing_runtime_gates_are_rejected(configured, gate):
    p = configured / ".github/workflows/ci.yml"
    p.write_text(p.read_text().replace(gate, ""))
    assert contract.check(configured)


@pytest.mark.parametrize(
    "gate",
    [
        "session_doctor -j 4",
        "python -m pip install -r requirements-native-ci.txt",
        "CAPTURE_TEST_BUILD_DIR: build/windows-release",
        "python tools/run_native_ci_tests.py",
        "build/evidence/native-*/",
    ],
)
def test_missing_native_integration_gate_is_rejected(configured, gate):
    p = configured / ".github/workflows/ci.yml"
    p.write_text(p.read_text().replace(gate, ""))
    assert contract.check(configured)


def test_native_dependency_file_cannot_drop_capture_session(configured):
    p = configured / "requirements-native-ci.txt"
    p.write_text(p.read_text().replace("-e ./libs/python/capture_session\n", ""))
    assert any("capture_session" in error for error in contract.check(configured))


def test_macos_triplet_drift_is_rejected(configured):
    path = configured / "CMakePresets.json"
    presets = json.loads(path.read_text())
    base = next(p for p in presets["configurePresets"] if p["name"] == "macos-arm64-base")
    base["cacheVariables"]["VCPKG_TARGET_TRIPLET"] = "x64-windows"
    path.write_text(json.dumps(presets))
    assert any("VCPKG_TARGET_TRIPLET" in error for error in contract.check(configured))


def test_macos_bootstrap_script_cannot_disappear(configured):
    (configured / "scripts/bootstrap-macos.sh").unlink()
    assert any("bootstrap-macos.sh" in error for error in contract.check(configured))


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


def test_each_native_ci_check_fails_its_own_step():
    import yaml

    workflow = yaml.safe_load((contract.ROOT / ".github/workflows/ci.yml").read_text())
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" not in step:
                continue
            commands = [
                line.strip()
                for line in step["run"].splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            assert len(commands) == 1, (
                f"Native command failures must not be masked by a later command: {step['name']}"
            )


def test_only_generated_proto_headers_are_external():
    root = contract.ROOT
    text = (root / "libs/cpp/capture_proto/CMakeLists.txt").read_text()
    assert (
        "target_include_directories(capture_proto SYSTEM PUBLIC ${CAPTURE_PROTO_GEN_DIR})" in text
    )
    warnings = (root / "cmake/CompilerWarnings.cmake").read_text()
    assert "/W4" in warnings and "/WX" in warnings and "CAPTURE_WERROR" in warnings
    workflow = (root / ".github/workflows/ci.yml").read_text()
    assert "python tools/check_cpp_warning_boundary.py" in workflow
    assert (
        "target_include_directories(capture_storage PUBLIC"
        in (root / "libs/cpp/capture_storage/CMakeLists.txt").read_text()
    )
