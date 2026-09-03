# SPDX-License-Identifier: GPL-3.0-only
"""Open a finalized package (OpenSession), then export with --verify."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "libs" / "python" / "capture_protocol"),
    str(ROOT / "libs" / "python" / "capture_session"),
]

from capture_protocol.control_client import ControlClient  # noqa: E402
from capture_protocol.generated.capture.v1 import control_pb2  # noqa: E402
from capture_session import load_review_summary  # noqa: E402

PY = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
if not PY.is_file():
    PY = Path(sys.executable)

SESSIONS = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "CaptureSuite" / "sessions"
)


def _newest_package(pattern: str) -> Path | None:
    pkgs = sorted(SESSIONS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return pkgs[0] if pkgs else None


def _ensure_idle(client: ControlClient) -> None:
    try:
        client.stop_rehearsal()
    except Exception:
        pass
    view = client.get_session_view()
    active = {
        control_pb2.SESSION_STATE_PREPARING,
        control_pb2.SESSION_STATE_ARMING,
        control_pb2.SESSION_STATE_RECORDING,
        control_pb2.SESSION_STATE_STOPPING,
        control_pb2.SESSION_STATE_RECOVERING,
        control_pb2.SESSION_STATE_FAILED,
    }
    if view.state in active:
        tok = client.request_stop()
        if tok.confirmation_token:
            client.stop_session(tok.confirmation_token)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "package",
        nargs="?",
        help="package path; default newest soak/kill/ui package",
    )
    args = ap.parse_args()
    package = Path(args.package) if args.package else None
    if package is None:
        for pat in (
            "soak-cam-radar-*.mmsession",
            "kill-*.mmsession",
            "ui-probe-*.mmsession",
            "reopen-*.mmsession",
            "*.mmsession",
        ):
            package = _newest_package(pat)
            if package is not None:
                break
    if package is None or not package.is_dir():
        print("FAIL no package found")
        return 1

    summary = load_review_summary(package)
    print(
        "reader",
        summary.session_id,
        summary.state,
        "sources",
        len(summary.source_ids),
        "gaps",
        len(summary.gaps),
        "checkpoints",
        len(summary.checkpoints),
    )

    client = ControlClient(timeout_s=60.0)
    client.connect()
    try:
        _ensure_idle(client)
        opened = client.open_session(str(package))
        if opened.error.code:
            print("FAIL open_session", opened.error.code, opened.error.message)
            return 1
        sid = opened.session_id or ""
        path = opened.package_path or ""
        print("opened", sid, path)
        if not sid and not path:
            print("FAIL open reply missing session_id/package_path")
            return 1
        view = client.get_session_view()
        if view.error.code:
            print("FAIL session_view", view.error.code, view.error.message)
            return 1
        print(
            "view state",
            view.state,
            "lanes",
            len(view.lanes),
            "checkpoints",
            len(view.checkpoints),
            "package",
            view.package_path,
        )
        # Read-only: Start must stay blocked until CreateSession.
        # Soft check: creating a new session should clear review.
    finally:
        client.close()

    out = Path(tempfile.mkdtemp(prefix="open_recover_export_"))
    proc = subprocess.run(
        [str(PY), str(ROOT / "tools" / "export_session.py"), str(package), str(out), "--verify"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        print("FAIL export --verify")
        return 1
    print("PASS open_recover_export", package.name, "→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
