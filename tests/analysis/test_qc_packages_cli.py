# SPDX-License-Identifier: GPL-3.0-only
"""Real CLI entrypoint with narrow authored filesystem failure injection."""

from __future__ import annotations

import errno
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from capture_analysis.qc import collect_qc
from review_qc_packages import main

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mini_session"


def _inventory(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "directory"
        )
        for path in sorted(root.rglob("*"))
    }


def test_directory_creation_race_preserves_the_other_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "source.mmsession"
    shutil.copytree(FIXTURE, package)
    before = _inventory(package)
    output = tmp_path / "review"
    original_mkdir = Path.mkdir
    sentinel = b"Authored competing export: preserve.\x00\xff\n"

    def create_competing_directory(path: Path, *args, **kwargs):
        if path == output:
            original_mkdir(path, *args, **kwargs)
            (path / "prior.bin").write_bytes(sentinel)
            raise FileExistsError(errno.EEXIST, "authored competing export", str(path))
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", create_competing_directory)
    with pytest.raises(SystemExit) as refused:
        main(["--output", str(output), str(package)])

    assert refused.value.code == 2
    assert "output already exists" in capsys.readouterr().err
    assert (output / "prior.bin").read_bytes() == sentinel
    assert sorted(path.name for path in output.iterdir()) == ["prior.bin"]
    assert _inventory(package) == before


def test_mid_report_write_failure_keeps_partial_output_and_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    package = tmp_path / "source.mmsession"
    shutil.copytree(FIXTURE, package)
    before = _inventory(package)
    native = collect_qc(package).to_dict()
    output = tmp_path / "review"
    refused_html = output / "reports" / "001-qc.html"
    original_open = Path.open

    def refuse_one_output(path: Path, mode="r", *args, **kwargs):
        if path == refused_html and mode == "xb":
            raise PermissionError(errno.EACCES, "authored report write refusal", str(path))
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", refuse_one_output)
    status = main(["--output", str(output), str(package)])
    captured = capsys.readouterr()

    assert status == 1
    assert "could not be completed" in captured.err
    assert "Output may be partial" in captured.err
    assert "PermissionError" in captured.err
    assert captured.out == ""
    assert (output / "reports" / "001-qc.json").read_bytes() == json.dumps(
        native, indent=2, sort_keys=True,
    ).encode("utf-8")
    assert not refused_html.exists()
    assert not (output / "index.html").exists()
    assert not (output / "review.json").exists()
    assert _inventory(package) == before
