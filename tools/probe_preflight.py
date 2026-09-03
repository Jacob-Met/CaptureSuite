# SPDX-License-Identifier: GPL-3.0-only
"""Print preflight check results, which reveal the active camera code path."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "libs" / "python" / "capture_protocol")]

from capture_protocol.control_client import ControlClient  # noqa: E402


def main() -> int:
    client = ControlClient()
    client.connect()
    sources = list(client.list_sources().sources)
    cams = [s for s in sources if s.source_type == "camera"]
    only = sys.argv[1].lower() if len(sys.argv) > 1 else "brio"
    cams = [s for s in cams if only in (s.alias or "").lower()] or cams[:1]
    ids = [s.source_id for s in cams]
    client.select_sources(ids)
    reply = client.run_preflight(ids)
    print("ok =", reply.ok)
    for c in reply.checks:
        print("  ", str(c).replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
