# SPDX-License-Identifier: GPL-3.0-only
"""Entry point for CaptureSuite desktop UI.

Requires a running capture daemon (instance.json under LOCALAPPDATA/CaptureSuite).

    py -3.12 -m capture_desktop
"""

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
    ):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)


def main() -> int:
    parser = argparse.ArgumentParser(description="CaptureSuite recording and analysis workbench")
    parser.add_argument(
        "--offline", action="store_true", help="Open without connecting to a capture daemon",
    )
    parser.add_argument(
        "--review", metavar="PACKAGE", help="Open a finalized session for offline review",
    )
    args = parser.parse_args()
    _ensure_path()
    from capture_protocol.structured_log import get_logger

    from capture_desktop.app import run_app

    log = get_logger("desktop")
    log.info("desktop_started", "CaptureSuite desktop launching")
    return run_app(auto_connect=not (args.offline or args.review), review_package=args.review)


if __name__ == "__main__":
    raise SystemExit(main())
