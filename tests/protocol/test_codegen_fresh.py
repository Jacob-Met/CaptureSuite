# SPDX-License-Identifier: GPL-3.0-only
"""CI guard: regenerating protos/schemas must not change committed outputs."""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_gen_protos_is_idempotent() -> None:
    before = REPO / "libs" / "python" / "capture_protocol" / "capture_protocol" / "generated"
    assert before.is_dir()
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "gen_protos.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # Spot-check descriptor exists and a known file still imports
    assert (REPO / "build" / "generated" / "capture_v1.desc").is_file()
    sys.path.insert(0, str(REPO / "libs" / "python" / "capture_protocol"))
    from capture_protocol.generated.capture.v1 import common_pb2  # noqa: F401


def test_session_schemas_match_regeneration() -> None:
    schema_dir = REPO / "schemas" / "session" / "jsonschema"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Copy current schemas, regenerate, compare
        snapshot = tmp_path / "before"
        shutil.copytree(schema_dir, snapshot)
        result = subprocess.run(
            [sys.executable, str(REPO / "tools" / "gen_session_schemas.py")],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        after_files = sorted(p.name for p in schema_dir.glob("*"))
        before_files = sorted(p.name for p in snapshot.glob("*"))
        assert after_files == before_files
        for name in after_files:
            assert filecmp.cmp(snapshot / name, schema_dir / name, shallow=False), name
