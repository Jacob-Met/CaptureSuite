# SPDX-License-Identifier: GPL-3.0-only
"""Minimal HTML reports for analysis jobs."""

from __future__ import annotations

from html import escape
from typing import Any


def render_qc_html(qc: dict[str, Any]) -> str:
    lights = qc.get("trafficLights") or {}
    light_rows = "".join(
        f"<tr><td>{escape(sid)}</td><td class='{escape(level)}'>{escape(level)}</td></tr>"
        for sid, level in sorted(lights.items())
    )
    stream_rows = "".join(
        "<tr>"
        f"<td>{escape(str(s.get('sourceId', '')))}</td>"
        f"<td>{escape(str(s.get('streamId', '')))}</td>"
        f"<td>{escape(str(s.get('modality', '')))}</td>"
        f"<td>{escape(str(s.get('dataSchemaId', '')))}</td>"
        f"<td>{escape(str(s.get('nominalRateHz', '')))}</td>"
        f"<td>{escape(str(s.get('units', '') or '—'))}</td>"
        f"<td>{int(s.get('mcapSegments') or 0)}/{int(s.get('mkvSegments') or 0)}</td>"
        "</tr>"
        for s in (qc.get("streams") or [])
    )
    warn_items = (
        "".join(f"<li>{escape(w)}</li>" for w in (qc.get("warnings") or [])) or "<li>(none)</li>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>QC — {escape(str(qc.get("sessionId", "")))}</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 24px; color: #222; }}
h1 {{ font-size: 1.4rem; }}
table {{ border-collapse: collapse; margin: 12px 0 24px; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; font-size: 0.9rem; }}
th {{ background: #f4f4f4; }}
.ok {{ color: #1a7f37; font-weight: 600; }}
.warn {{ color: #9a6700; font-weight: 600; }}
.fail {{ color: #cf222e; font-weight: 600; }}
.meta {{ color: #555; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Analysis QC</h1>
<p class="meta">
session <b>{escape(str(qc.get("sessionId", "")))}</b> ·
state <b>{escape(str(qc.get("packageState", "")))}</b> ·
streams {int(qc.get("streamCount") or 0)} ·
gaps open/closed {int(qc.get("openGapCount") or 0)}/{int(qc.get("closedGapCount") or 0)} ·
checkpoints {int(qc.get("checkpointCount") or 0)}
</p>
<p class="meta">package: {escape(str(qc.get("packagePath", "")))}</p>
<p class="meta">manifest sha256: {escape(str(qc.get("manifestSha256", "")))}</p>

<h2>Sources</h2>
<table>
<tr><th>source</th><th>light</th></tr>
{light_rows or "<tr><td colspan='2'>(none)</td></tr>"}
</table>

<h2>Streams</h2>
<table>
<tr><th>source</th><th>stream</th><th>modality</th><th>schema</th>
<th>rate Hz</th><th>units</th><th>mcap/mkv</th></tr>
{stream_rows or "<tr><td colspan='7'>(none)</td></tr>"}
</table>

<h2>Warnings</h2>
<ul>{warn_items}</ul>
</body>
</html>
"""
