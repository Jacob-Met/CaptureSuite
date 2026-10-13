# SPDX-License-Identifier: GPL-3.0-only
"""CLI result and failure text must not replace the actual analysis exit status."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "mini_session"


@pytest.fixture
def cli():
    spec = importlib.util.spec_from_file_location(
        "received_analysis_cli", ROOT / "tools/run_analysis.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stream(encoding):
    buffer = io.BytesIO()
    return buffer, io.TextIOWrapper(buffer, encoding=encoding, errors="strict", newline="\n")


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
@pytest.mark.parametrize(
    ("status", "strict", "expected"),
    [
        ("completed", False, 0),
        ("completed_with_warnings", False, 0),
        ("completed_with_warnings", True, 2),
        ("failed", False, 1),
    ],
)
def test_result_text_preserves_job_status(cli, monkeypatch, encoding, status, strict, expected):
    package = Path("recordings/café-分析-🙂.mmsession")
    result = SimpleNamespace(
        job_id="job-雪",
        status=status,
        job_dir=package / "processing/jobs/job-雪",
        qc={"streamCount": 1, "openGapCount": 0, "closedGapCount": 1, "warnings": ["warning"]},
    )
    calls = []

    def run(path, params):
        calls.append((path, params))
        return result

    monkeypatch.setattr(cli, "run", run)
    buffer, stream = _stream(encoding)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        code = cli.main(["qc", str(package), *(["--strict-warnings"] if strict else [])])
        stream.flush()
    assert code == expected
    text = buffer.getvalue().decode(encoding)
    assert f"dir={result.job_dir}".encode(encoding, "backslashreplace").decode(encoding) in text
    assert f"status={status}" in text
    assert "streams=1 gaps_open=0 gaps_closed=1 warnings=1" in text
    assert len(calls) == 1 and calls[0][0] == package
    assert stream.encoding == encoding and stream.errors == "strict"


@pytest.mark.parametrize("encoding", ["ascii", "cp1252", "utf-8"])
def test_error_and_recovery_notes_stay_visible(cli, monkeypatch, encoding):
    error = OSError("could not write café-分析")
    error.add_note("retained failed attempt: output/雪")

    def run(*args):
        raise error

    monkeypatch.setattr(cli, "run", run)
    buffer, stream = _stream(encoding)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stderr", stream)
        code = cli.main(["qc", "package"])
        stream.flush()
    assert code == 1
    expected = "FAIL: could not write café-分析\nretained failed attempt: output/雪\n"
    assert buffer.getvalue() == expected.encode(encoding, "backslashreplace")
    assert stream.encoding == encoding and stream.errors == "strict"


def test_string_stream_preserves_unicode(cli, monkeypatch):
    stream = io.StringIO()
    result = SimpleNamespace(job_id="job", status="completed", job_dir=Path("分析"), qc=None)
    monkeypatch.setattr(cli, "run", lambda *args: result)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", stream)
        assert cli.main(["qc", "package"]) == 0
    assert "dir=分析\n" in stream.getvalue()


@pytest.mark.parametrize("error", [BrokenPipeError("consumer closed"), OSError("write failed")])
def test_nonencoding_output_failures_are_not_silenced(cli, monkeypatch, error):
    class FailedStream(io.StringIO):
        def write(self, text):
            raise error

    result = SimpleNamespace(job_id="job", status="completed", job_dir=Path("result"), qc=None)
    monkeypatch.setattr(cli, "run", lambda *args: result)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", FailedStream())
        with pytest.raises(type(error), match=str(error)):
            cli.main(["qc", "package"])


def _fingerprints(package):
    return {
        str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in package.rglob("*")
        if p.is_file() and "processing" not in p.relative_to(package).parts
    }


@pytest.mark.parametrize("encoding", ["cp1252", "utf-8"])
def test_real_cli_unicode_package_retains_written_job(tmp_path, encoding):
    package = tmp_path / "recording café-分析.mmsession"
    shutil.copytree(FIXTURE, package)
    before = _fingerprints(package)
    env = dict(os.environ, PYTHONIOENCODING=f"{encoding}:strict")
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/run_analysis.py"), "qc", str(package)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    jobs = list((package / "processing/jobs").iterdir())
    assert len(jobs) == 1
    manifest = json.loads((jobs[0] / "job_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] in {"completed", "completed_with_warnings"}
    expected = f"dir={jobs[0]}".encode(encoding, "backslashreplace")
    assert expected in result.stdout
    assert _fingerprints(package) == before
