# SPDX-License-Identifier: GPL-3.0-only
"""Minimal HTML reports for analysis jobs."""

from __future__ import annotations

from html import escape
from typing import Any

from capture_analysis.report_numeric_preview import numeric_previews_html


def _seconds(value: str | int | None) -> str:
    if value is None:
        return "unknown"
    ns = int(value)
    seconds, remainder = divmod(abs(ns), 1_000_000_000)
    return f"{'-' if ns < 0 else ''}{seconds}.{remainder:09d}"


def _gap_rows(qc: dict[str, Any]) -> str:
    gaps = qc.get("gaps")
    if not isinstance(gaps, list):
        return "<tr><td colspan='8'>Gap details are not available in this report.</td></tr>"
    if not gaps:
        return "<tr><td colspan='8'>No gap records listed.</td></tr>"
    unknown = {
        "open": "unknown (open gap)",
        "missing_end": "unknown (end not recorded)",
        "end_before_start": "unknown (end precedes start)",
    }
    rows = []
    for gap in gaps:
        duration = gap.get("durationNs")
        duration_text = (
            _seconds(duration)
            if duration is not None
            else unknown.get(gap.get("durationStatus"), "unknown")
        )
        cells = (
            str(gap.get("sourceId") or "(unspecified)"),
            str(gap.get("streamId") or "(source-wide)"),
            str(gap.get("cause") or "unknown"),
            "closed" if gap.get("closed") else "open",
            _seconds(gap.get("startSessionTimeNs")),
            _seconds(gap.get("endSessionTimeNs")),
            duration_text,
            str(gap.get("estimatedLostCount", "unknown")),
        )
        rows.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>")
    return "".join(rows)


def _payload_frames(stream: dict[str, Any]) -> str:
    frames = (stream.get("payloadInspection") or {}).get("sampleFramesChecked")
    return escape(str(frames if frames is not None else "—"))


def _inspection_cell(stream: dict[str, Any]) -> str:
    inspection = stream.get("payloadInspection") or {}
    status = str(inspection.get("status", "not_requested"))
    notes: list[str] = []
    if status == "failed":
        notes.append(str(inspection.get("detail") or "payload unreadable"))
    if inspection.get("channelIds"):
        notes.append("channels: " + ", ".join(str(x) for x in inspection["channelIds"]))
    if inspection.get("sensorIds"):
        notes.append("sensors: " + ", ".join(str(x) for x in inspection["sensorIds"]))
    presence = inspection.get("sensorFramePresence")
    if isinstance(presence, dict):
        notes.append(
            "sensor presence (decoded frames): "
            + ", ".join(
                f"{sid} {values['framesPresent']}/{values['totalFrames']}"
                for sid, values in sorted(presence.items())
            )
        )
    if inspection.get("constantChannels"):
        notes.append("constant: " + ", ".join(str(x) for x in inspection["constantChannels"]))
    continuity = inspection.get("sampleIndexContinuity")
    if isinstance(continuity, dict):
        notes.append(
            f"sample-index transitions checked: {continuity['transitionsChecked']}; "
            f"forward jumps: {continuity['forwardJumpCount']}; "
            f"overlaps/resets: {continuity['overlapOrResetCount']}"
        )
        examples = continuity.get("examples", [])
        total = continuity["forwardJumpCount"] + continuity["overlapOrResetCount"]
        if total > len(examples):
            notes.append(f"showing first {len(examples)} of {total} discontinuities")
        for example in examples:
            notes.append(
                f"{example['segment']} message {example['messageInSegment']}: "
                f"expected {example['expectedFirstSampleIndex']}, "
                f"observed {example['actualFirstSampleIndex']}"
            )
    zero_quaternions = inspection.get("zeroQuaternionSensorSamples")
    if zero_quaternions:
        notes.append(f"zero quaternion sensor samples: {int(zero_quaternions)}")
    detail = (
        "<div class='meta'>" + "<br/>".join(escape(note) for note in notes) + "</div>"
        if notes else ""
    )
    return escape(status) + detail


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
        f"<td>{_inspection_cell(s)}</td>"
        f"<td>{_payload_frames(s)}</td>"
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
<meta name="viewport" content="width=device-width, initial-scale=1"/>
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
.meta {{ color: #555; font-size: 0.85rem; overflow-wrap: anywhere; line-height: 1.4; }}
.table-scroll {{ overflow-x: auto; }}
.warnings {{ padding-left: 1.4rem; overflow-wrap: anywhere; }}
.warnings li {{ margin-bottom: 0.6rem; }}
.preview {{ margin: 24px 0; border-top: 2px solid #c8d0da; padding-top: 12px; }}
.preview h3 {{ margin: 0 0 8px; font-size: 1rem; overflow-wrap: anywhere; }}
.preview p {{ max-width: 90ch; line-height: 1.45; }}
.trace {{ margin: 12px 0; }}
.trace figcaption {{ font-weight: 600; overflow-wrap: anywhere; }}
.trace-chart {{ display: grid; grid-template-columns: 64px minmax(0, 1fr); max-width: 1100px; }}
.trace svg {{ display: block; width: 100%; height: 140px; }}
.trace-y {{ display: flex; flex-direction: column; justify-content: space-between;
  padding: 13px 8px 13px 0; text-align: right; }}
.trace-y, .trace-x, .trace-axis {{ font: 12px Consolas, ui-monospace, monospace; color: #5a6573; }}
.trace-x {{ grid-column: 2; display: flex; justify-content: space-between; }}
.trace-axis {{ margin: 8px 0 0 64px; text-align: center; max-width: 1036px; }}
.trace .batch {{ stroke: #8d9aab; stroke-width: 1; stroke-dasharray: 4 4; }}
.trace text {{ font: 12px Consolas, ui-monospace, monospace; fill: #5a6573; }}
.trace .signal {{ stroke: #2563eb; stroke-width: 1.5; fill: none; }}
.trace .point {{ fill: #2563eb; }}
.trace .grid {{ stroke: #c8d0da; stroke-width: 1; }}
.preview summary {{ cursor: pointer; padding: 8px 0; }}
.preview .meta {{ overflow-wrap: anywhere; }}
@media (max-width: 600px) {{ body {{ margin: 12px; }} }}
.gaps td:nth-child(n+5) {{ font-family: Consolas, ui-monospace, monospace; }}
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

<section aria-labelledby="warnings-title">
<h2 id="warnings-title">Warnings</h2>
<ul class="warnings">{warn_items}</ul>
</section>

<h2>Recorded gaps</h2>
<p class="meta">Times are seconds relative to session T0, with nanosecond precision.
Each row is one reported gap. Loss counts are reported estimates in source-defined units.</p>
<div class="table-scroll">
<table class="gaps">
<tr><th>source</th><th>stream</th><th>cause</th><th>state</th>
<th>start (session s)</th><th>end (session s)</th><th>duration (s)</th>
<th>estimated lost count</th></tr>
{_gap_rows(qc)}
</table>
</div>

<h2>Streams</h2>
<p class="meta">Source lights evaluate recorded metadata and gaps.
A green light does not establish signal quality. Payload inspection is optional: run
<code>run_analysis.py qc PACKAGE --inspect-payloads</code> to read segment bytes.
"mcap_messages_checked" confirms structural reading only; only
"numeric_samples_checked", "emg_samples_checked", and "imu_frames_checked"
confirm decoded measurements and checked frame counts.
None of these statuses establishes calibrated sensor accuracy.</p>
<div class="table-scroll">
<table>
<tr><th>source</th><th>stream</th><th>modality</th><th>schema</th>
<th>rate Hz</th><th>units</th><th>mcap/mkv</th>
<th>payload inspection</th><th>sample frames checked</th></tr>
{stream_rows or "<tr><td colspan='9'>(none)</td></tr>"}
</table>
</div>
{numeric_previews_html(qc.get("streams") or [])}

</body>
</html>
"""
