# SPDX-License-Identifier: GPL-3.0-only
"""Entry point for CaptureSuite desktop UI.

Live capture uses the Windows daemon; --analysis [PACKAGE] opens offline results.

    py -3.12 -m capture_desktop
"""

from __future__ import annotations

import argparse
import os
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
    ):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def main() -> int:
    parser = argparse.ArgumentParser(description="CaptureSuite desktop")
    parser.add_argument(
        "--analysis", nargs="?", const="", metavar="PACKAGE",
        help="Open offline analysis, optionally with a .mmsession recording.",
    )
    args = parser.parse_args()
    analysis_only = args.analysis is not None or os.name != "nt"
    _ensure_path()
    from capture_protocol.structured_log import get_logger

    from capture_desktop.app import run_app

    log = get_logger("desktop")
    log.info("desktop_started", "CaptureSuite desktop launching")
    return run_app(
        auto_connect=not analysis_only,
        analysis_only=analysis_only,
        package_path=args.analysis or "",
    )


if __name__ == "__main__":
    raise SystemExit(main())
