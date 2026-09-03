# SPDX-License-Identifier: GPL-3.0-only
"""python -m capture_desktop"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap() -> None:
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


_bootstrap()

# Import deliberately follows _bootstrap(): it is what puts capture_desktop and
# the sibling libraries on sys.path.
from capture_desktop.main import main  # noqa: E402

raise SystemExit(main())
