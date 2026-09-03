# SPDX-License-Identifier: GPL-3.0-only
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for path in (
    REPO / "libs" / "python" / "capture_protocol",
    REPO / "libs" / "python" / "capture_session",
    REPO / "workers" / "python_host",
    REPO / "desktop",
):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
