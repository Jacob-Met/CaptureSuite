# SPDX-License-Identifier: GPL-3.0-only
"""Launch the capture desktop, or its existing offline analysis workspace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_path() -> None:
    """Allow running from a source checkout without editable install."""
    here = Path(__file__).resolve()
    desktop = here.parents[1]
    repo = here.parents[2]
    for path in (
        desktop,
        repo / "libs" / "python" / "capture_protocol",
        repo / "libs" / "python" / "capture_session",
        repo / "libs" / "python" / "capture_analysis",
    ):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CaptureSuite desktop")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="open recorded sessions in the Analysis workspace without connecting to a daemon",
    )
    parser.add_argument("package", nargs="?", help="recorded .mmsession package to open offline")
    pin = Path(sys.executable).resolve().parent / "SOURCE_COMMIT"
    version = (
        pin.read_text().strip()
        if getattr(sys, "frozen", False) and pin.is_file()
        else "source checkout"
    )
    parser.add_argument("--version", action="version", version=f"CaptureSuite desktop ({version})")
    args = parser.parse_args(argv)
    if args.package and not args.offline:
        parser.error("opening a recorded package requires --offline")
    _ensure_path()
    from capture_protocol.structured_log import get_logger

    log = get_logger("desktop")
    log.info("desktop_started", "CaptureSuite desktop launching")
    if args.offline:
        from capture_desktop.offline import run_offline

        return run_offline(args.package or "")
    from capture_desktop.app import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
