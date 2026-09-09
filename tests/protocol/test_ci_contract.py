# SPDX-License-Identifier: GPL-3.0-only
import json
from pathlib import Path

import check_ci_contract as contract
import pytest

SHA = "b322364f06308bdd24823f9d8f03fe0cc86fd46f"


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
        )
    (tmp_path / "requirements-ci.txt").write_text("\n".join(f"-e ./{m}" for m in contract.MEMBERS))
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
