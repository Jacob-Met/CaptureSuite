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
