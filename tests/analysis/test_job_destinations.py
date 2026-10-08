# SPDX-License-Identifier: GPL-3.0-only
"""Analysis destinations must not redirect output into recorded or unrelated data."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from capture_analysis import JobParams, hash_sources_tree, run

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    dest = tmp_path / "mini.mmsession"
    shutil.copytree(FIXTURE, dest)
    return dest


def _snapshot(root: Path) -> dict[str, bytes | str]:
    result: dict[str, bytes | str] = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[name] = f"symlink:{os.readlink(path)}"
        elif path.is_dir():
            result[name] = "directory"
        else:
            result[name] = path.read_bytes()
    return result


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks unavailable: {exc}")


def _expect_rejected_without_mutation(package: Path, job_id: str, *extra: Path) -> None:
    roots = (package, *extra)
    before = [_snapshot(root) for root in roots]
    failure: Exception | None = None
    try:
        run(package, JobParams(command="qc", overwrite_job_id=job_id))
    except Exception as exc:  # noqa: BLE001
        failure = exc
    assert [_snapshot(root) for root in roots] == before, "rejected jobs must not change data"
    assert isinstance(failure, ValueError), f"expected destination rejection, got {failure!r}"
    assert "job ID" in str(failure) or "job destination" in str(failure)


@pytest.mark.parametrize("absolute", [False, True], ids=["traversal", "absolute"])
def test_raw_sources_cannot_be_an_overwrite_destination(package: Path, absolute: bool) -> None:
    job_id = str(package / "sources") if absolute else "../../sources"
    _expect_rejected_without_mutation(package, job_id)


@pytest.mark.parametrize(
    "job_id",
    ["", ".", "..", "nested/job", r"nested\job", "C:job", "qc.", "qc ", "NUL.txt",
     "qc?one", ".attempt_existing", "qc\x00one"],
)
def test_job_ids_are_portable_single_visible_names(package: Path, job_id: str) -> None:
    _expect_rejected_without_mutation(package, job_id)


@pytest.mark.parametrize("component", ["processing", "jobs", "job"])
@pytest.mark.parametrize("outside", [False, True], ids=["raw-sources", "outside-package"])
def test_linked_output_paths_are_rejected(
    package: Path, tmp_path: Path, component: str, outside: bool
) -> None:
    target = tmp_path / "unrelated" if outside else package / "sources"
    if outside:
        target.mkdir()
        (target / "keep.txt").write_bytes(b"unrelated existing data")
    processing = package / "processing"
    if component == "processing":
        shutil.rmtree(processing)
        link = processing
    elif component == "jobs":
        link = processing / "jobs"
    else:
        (processing / "jobs").mkdir()
        link = processing / "jobs" / "qc-test"
    _symlink(link, target)
    _expect_rejected_without_mutation(package, "qc-test", target)


def test_dangling_destination_link_is_rejected(package: Path, tmp_path: Path) -> None:
    jobs = package / "processing" / "jobs"
    jobs.mkdir()
    target = tmp_path / "missing"
    _symlink(jobs / "qc-test", target)
    _expect_rejected_without_mutation(package, "qc-test")
    assert not target.exists()


@pytest.mark.parametrize("job_id", [None, "qc-test", "walking trial_é"])
def test_ordinary_jobs_preserve_raw_sources(package: Path, job_id: str | None) -> None:
    before = hash_sources_tree(package)
    result = run(package, JobParams(command="qc", overwrite_job_id=job_id))
    assert result.job_dir.parent == package.resolve() / "processing" / "jobs"
    assert result.job_dir.name == result.job_id
    if job_id is not None:
        assert result.job_id == job_id
    assert (result.job_dir / "reports" / "qc.json").is_file()
    assert hash_sources_tree(package) == before


def test_package_root_link_remains_supported(package: Path, tmp_path: Path) -> None:
    link = tmp_path / "linked.mmsession"
    _symlink(link, package)
    before = hash_sources_tree(package)
    result = run(link, JobParams(command="qc", overwrite_job_id="linked-qc"))
    assert result.job_dir == package.resolve() / "processing" / "jobs" / "linked-qc"
    assert hash_sources_tree(package) == before


@pytest.mark.skipif(os.name != "nt", reason="native Windows junction semantics")
def test_windows_output_junction_cannot_redirect_into_sources(package: Path) -> None:
    link = package / "processing" / "jobs"
    proc = subprocess.run(
        ["cmd", "/d", "/c", "mklink", "/J", str(link), str(package / "sources")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert link.is_junction()
    _expect_rejected_without_mutation(package, "qc-test")
