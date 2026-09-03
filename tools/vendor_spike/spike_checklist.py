#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Print (and optionally write) the vendor spike checklist for lab notes.

No vendor SDK imports. Python 3.12+.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

VENDORS = ("infineon", "xsens", "delsys")

SECTIONS = (
    ("1. Exact product / board / firmware / SDK version and license terms", ()),
    (
        "2. How devices are discovered and what stable identity fields exist",
        (),
    ),
    (
        "3. Threading / callback model (who owns buffers, can you block?)",
        (),
    ),
    (
        "4. Timestamp format, units, clock domain, and drift behavior",
        (),
    ),
    ("5. Start / stop / arm semantics and first-sample latency", ()),
    (
        "6. Disconnect / reconnect behavior and sequence numbering",
        (),
    ),
    ("7. Maximum sustained rate and payload sizes observed", ()),
    ('8. Whether any "hardware sync" mode is real vs marketing', ()),
)

CONTEXT = {
    "infineon": {
        "title": "Infineon BGT60TR13C (M6)",
        "stub": "docs/design/adapters/infineon_bgt60tr13c.md",
        "notes": (
            "V1 target: BGT60TR13C - not interchangeable with BGT60LTR11AIP.",
            "Needs Infineon RDK (not webcam-style open).",
            "Sim today: sim.radar.1 / sim.radar.2, MATRIX_2D preview.",
            "No multi-radar sync claims until validated on real boards.",
        ),
    },
    "xsens": {
        "title": "Xsens (M7)",
        "stub": "docs/design/adapters/xsens.md",
        "notes": (
            "Exact family / receiver / sensors TBD at lab.",
            "Sim today: sim.imu.upper, ORIENTATION preview in UI.",
            "Pairing and logical slots TBD on hardware.",
        ),
    },
    "delsys": {
        "title": "Delsys Trigno (M8)",
        "stub": "docs/design/adapters/delsys.md",
        "notes": (
            "Sim today: sim.emg.main, TRACE_BLOCK preview.",
            "Credentials via Windows Credential Manager (OPERATIONS.md).",
            "No secrets in repo, settings, logs, or diagnostic bundles.",
        ),
    },
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def render(vendor: str, *, dated: bool) -> str:
    ctx = CONTEXT[vendor]
    lines = [
        f"# Spike checklist - {ctx['title']}",
        "",
        f"Stub: `{ctx['stub']}`",
        "Source of truth for required fields: `docs/design/VENDOR_SPIKE.md`",
        "Standalone probes only - do not depend on capture_daemon.",
        "",
    ]
    if dated:
        lines.append(f"Date: {dt.date.today().isoformat()}")
        lines.append("")
    lines.append("## Known context")
    lines.append("")
    for note in ctx["notes"]:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## Checklist")
    lines.append("")
    for title, _ in SECTIONS:
        lines.append(f"### {title}")
        lines.append("")
        lines.append("- Observation: TBD")
        lines.append("- Evidence / command: TBD")
        lines.append("")
    lines.append("## Decision notes")
    lines.append("")
    lines.append("- TBD")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the CaptureSuite vendor spike checklist."
    )
    parser.add_argument(
        "vendor",
        choices=VENDORS,
        help="Vendor key: infineon | xsens | delsys",
    )
    parser.add_argument(
        "--write-notes",
        action="store_true",
        help=(
            "Write docs/design/adapters/notes/<vendor>_YYYY-MM-DD.md "
            "(fails if the file already exists)"
        ),
    )
    args = parser.parse_args(argv)

    text = render(args.vendor, dated=args.write_notes)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")

    if args.write_notes:
        notes_dir = repo_root() / "docs" / "design" / "adapters" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        out = notes_dir / f"{args.vendor}_{dt.date.today().isoformat()}.md"
        if out.exists():
            print(f"refusing to overwrite existing notes: {out}", file=sys.stderr)
            return 2
        out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
