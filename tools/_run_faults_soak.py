# SPDX-License-Identifier: GPL-3.0-only
"""One-shot: restart daemon, run fault probes + 5min soak (debug helper)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python312" / "python.exe"
sys.path[:0] = [
    str(ROOT / "tools"),
    str(ROOT / "libs" / "python" / "capture_protocol"),
]

from run_premanual_debug import _restart_daemon, _run, _write_report  # noqa: E402


def main() -> int:
    os.chdir(ROOT)
    if not _restart_daemon():
        return 1
    out_dir = (
        Path(os.environ["LOCALAPPDATA"])
        / "CaptureSuite"
        / "debug_runs"
        / f"faults_{int(time.time())}"
    )
    results = []
    steps = [
        (
            "kill_camera_worker",
            [str(PY), "tools/probe_kill_worker_mid_record.py", "--kill", "camera"],
        ),
        (
            "kill_radar_worker",
            [str(PY), "tools/probe_kill_worker_mid_record.py", "--kill", "radar"],
        ),
        ("inject_disconnect", [str(PY), "tools/probe_inject_disconnect.py"]),
        ("soak_5min", [str(PY), "tools/soak_camera_radar.py", "300"]),
    ]
    for label, argv in steps:
        entry = _run(label, argv)
        results.append(entry)
        if not entry["ok"]:
            _restart_daemon()
    if results and results[-1]["ok"] and results[-1]["label"] == "soak_5min":
        sessions = Path(os.environ["LOCALAPPDATA"]) / "CaptureSuite" / "sessions"
        pkgs = sorted(
            sessions.glob("soak-cam-radar-*.mmsession"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if pkgs:
            results.append(
                _run(
                    "export_5min",
                    [
                        str(PY),
                        "tools/export_session.py",
                        str(pkgs[0]),
                        str(out_dir / "export_5min"),
                    ],
                )
            )
    report = _write_report(out_dir, results)
    print("Report:", report)
    failed = [r for r in results if not r["ok"]]
    if failed:
        print("FAILED:", ", ".join(r["label"] for r in failed))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
