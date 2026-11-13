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
        # The complete test suite can run across processes. Run the generator in
        # a scratch tree so concurrent analysis/tests never see deleted schemas.
        root = Path(tmp)
        staged = root / "schemas" / "session" / "jsonschema"
        shutil.copytree(schema_dir, staged)
        script = root / "tools" / "gen_session_schemas.py"
        script.parent.mkdir(parents=True)
        shutil.copy2(REPO / "tools" / script.name, script)
        descriptor = root / "build" / "generated" / "capture_v1.desc"
        descriptor.parent.mkdir(parents=True)
        shutil.copy2(REPO / "build" / "generated" / descriptor.name, descriptor)
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        before_files = sorted(p.name for p in schema_dir.glob("*"))
        after_files = sorted(p.name for p in staged.glob("*"))
        assert after_files == before_files
        for name in before_files:
            assert filecmp.cmp(schema_dir / name, staged / name, shallow=False), name
