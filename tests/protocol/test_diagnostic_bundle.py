# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from diagnostic_bundle.__main__ import build_bundle


def test_diagnostic_bundle_excludes_raw_by_default(tmp_path: Path) -> None:
    pkg = tmp_path / "demo.mmsession"
    (pkg / "logs").mkdir(parents=True)
    (pkg / "sources" / "sim.emg.main" / "streams" / "raw" / "segments").mkdir(
        parents=True
    )
    (pkg / "manifest.json").write_text(
        json.dumps(
            {
                "session_id": "s1",
                "participant": {"id": "guid-1", "name": "Alice"},
            }
        ),
        encoding="utf-8",
    )
    (pkg / "integrity.json").write_text("{}", encoding="utf-8")
    (pkg / "logs" / "daemon.log").write_text(
        '{"event":"x"}\n', encoding="utf-8"
    )
    (pkg / "sources" / "sim.emg.main" / "source.json").write_text(
        "{}", encoding="utf-8"
    )
    (
        pkg
        / "sources"
        / "sim.emg.main"
        / "streams"
        / "raw"
        / "segments"
        / "000000.mcap"
    ).write_bytes(b"raw")

    con = sqlite3.connect(pkg / "journal.sqlite")
    con.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, kind TEXT, "
        "session_time_ns INTEGER, wall_utc TEXT, source_id TEXT, "
        "stream_id TEXT, payload_json TEXT)"
    )
    con.execute(
        "INSERT INTO events(kind, session_time_ns, wall_utc, source_id, "
        "stream_id, payload_json) VALUES ('SESSION_CREATED',0,'','','','{}')"
    )
    con.commit()
    con.close()

    out = tmp_path / "diag.zip"
    summary = build_bundle(pkg, out, include_raw=False, include_identifiers=False)
    assert out.is_file()
    assert any(p.endswith("manifest.json") for p in summary["included"])
    assert not any(p.endswith(".mcap") for p in summary["included"])

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "bundle_manifest.json" in names
        assert "manifest.json" in names
        assert "000000.mcap" not in {Path(n).name for n in names}
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["participant"] == {"id": "guid-1"}
