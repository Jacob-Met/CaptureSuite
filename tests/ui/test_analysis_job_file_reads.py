# SPDX-License-Identifier: GPL-3.0-only
"""A stable file can expose different path/handle clocks without losing read guards."""

from __future__ import annotations

import os
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from capture_desktop.analysis_job_comparison import JobParameterError, _read_regular


def _with_ctime(info, value):
    fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
    fields["st_ctime_ns"] = value
    fields["st_ctime"] = value / 1_000_000_000
    return SimpleNamespace(**fields)


def test_stable_file_allows_distinct_path_and_handle_ctime(tmp_path, monkeypatch):
    path = tmp_path / "params.json"
    original = b'{"retained": true}\n'
    path.write_bytes(original)
    actual_fstat = os.fstat

    def handle_clock(fd):
        info = actual_fstat(fd)
        return _with_ctime(info, info.st_ctime_ns + 1_000_000_000)

    # CPython 3.12.10 on Windows exposes creation time through lstat's ctime
    # and change time through fstat's ctime. Preserve that documented receiver
    # distinction without changing the actual file ID, size, mtime or bytes.
    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", handle_clock)
        assert _read_regular(path) == original
    assert path.read_bytes() == original


def test_change_in_handle_metadata_during_read_is_still_refused(tmp_path, monkeypatch):
    path = tmp_path / "params.json"
    original = b'{"retained": true}\n'
    path.write_bytes(original)
    actual_fstat = os.fstat
    calls = 0

    def changed_handle(fd):
        nonlocal calls
        calls += 1
        info = actual_fstat(fd)
        return _with_ctime(info, info.st_ctime_ns + (1_000_000_000 if calls > 1 else 0))

    with monkeypatch.context() as patch:
        patch.setattr(os, "fstat", changed_handle)
        with pytest.raises(JobParameterError, match="changed while being read"):
            _read_regular(path)
    assert calls == 2
    assert path.read_bytes() == original


def test_replaced_path_after_handle_close_is_refused_even_with_identical_bytes(
    tmp_path, monkeypatch
):
    path = tmp_path / "params.json"
    retained = tmp_path / "retained-original.json"
    original = b'{"retained": true}\n'
    path.write_bytes(original)
    actual_fdopen = os.fdopen

    @contextmanager
    def replace_after_close(fd, mode):
        with actual_fdopen(fd, mode) as stream:
            yield stream
        # The handle is closed before replacement, so the real fixture also
        # works on Windows where an ordinary open descriptor prevents rename.
        path.rename(retained)
        path.write_bytes(original)

    with monkeypatch.context() as patch:
        patch.setattr(os, "fdopen", replace_after_close)
        with pytest.raises(JobParameterError, match="changed"):
            _read_regular(path)
    assert path.read_bytes() == retained.read_bytes() == original


def test_another_file_opened_after_path_inspection_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "params.json"
    retained = tmp_path / "retained-original.json"
    original = b'{"retained": true}\n'
    path.write_bytes(original)
    actual_open = os.open

    def replace_before_open(name, flags):
        path.rename(retained)
        path.write_bytes(original)
        return actual_open(name, flags)

    with monkeypatch.context() as patch:
        patch.setattr(os, "open", replace_before_open)
        with pytest.raises(JobParameterError, match="changed while being opened"):
            _read_regular(path)
    assert path.read_bytes() == retained.read_bytes() == original
