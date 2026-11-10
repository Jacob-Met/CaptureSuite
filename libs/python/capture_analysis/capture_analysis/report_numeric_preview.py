# SPDX-License-Identifier: GPL-3.0-only
"""Self-contained recorded numeric excerpts for the ordinary QC report."""

from __future__ import annotations

from html import escape
from typing import Any


def _trace(
    channel: str, units: str, batches: list[dict[str, Any]], column: int, shown: int, number: int
) -> str:
    values = [row[column] for batch in batches for row in batch["values"]]
    low, high = min(values), max(values)
    # Scaling before subtracting also handles opposite finite float64 extremes.
    scale = max(abs(low), abs(high), 1.0)
    lower, upper = low / scale, high / scale
    spread = upper - lower

    def x(frame: int) -> float:
        return 960 * frame / max(shown - 1, 1)

    def y(value: float) -> float:
        return 70 if spread == 0 else 120 - 100 * (value / scale - lower) / spread

    paths = []
    for batch in batches:
        points = [
            (x(batch.get("displayFirstFrame", batch["firstFrame"]) + i), y(row[column]))
            for i, row in enumerate(batch["values"])
        ]
        if len(points) > 1:
            coords = " ".join(f"{a:.3f},{b:.3f}" for a, b in points)
            paths.append(f'<polyline class="signal" points="{coords}"/>')
        for a, b in points:
            paths.append(f'<circle class="point" cx="{a:.3f}" cy="{b:.3f}" r="1.7"/>')
    label = escape(channel)
    unit_label = escape(units or "units unspecified")
    boundaries = "".join(
        '<path class="batch" d="M'
        f"{x(batch.get('displayFirstFrame', batch['firstFrame']) - 0.5):.3f}"
        ' 10V130"/>'
        for batch in batches[1:]
    )
    description = escape(
        f"{channel}: {shown} recorded samples, minimum {low:.6g}, maximum {high:.6g}. "
        "Each line stops at its recorded batch boundary. The axis is sample position, not time."
    )
    return f"""<figure class="trace">
<figcaption>{label} <span class="meta">· {unit_label}
· excerpt range {low:.6g} to {high:.6g}</span></figcaption>
<div class="trace-chart">
<div class="trace-y" aria-hidden="true"><span>{high:.6g}</span><span>{low:.6g}</span></div>
<svg viewBox="0 0 960 140" preserveAspectRatio="none" role="img"
aria-labelledby="trace-title-{number} trace-desc-{number}">
<title id="trace-title-{number}">{label} recorded sample excerpt</title>
<desc id="trace-desc-{number}">{description}</desc>
<path class="grid" d="M0 20H960 M0 70H960 M0 120H960"/>
{boundaries}{"".join(paths)}
</svg>
<div class="trace-x" aria-hidden="true"><span>1</span><span>{shown}</span></div>
</div>
<p class="trace-axis">Recorded sample position (not elapsed time)</p>
</figure>"""


def numeric_previews_html(streams: list[dict[str, Any]]) -> str:
    sections = []
    chart_number = 0
    for stream in streams:
        inspection = stream.get("payloadInspection") or {}
        preview = inspection.get("numericPreview")
        if inspection.get("status") != "numeric_samples_checked" or not preview:
            continue
        batches = preview["batches"]
        channels = preview["channelIds"]
        shown = preview["framesShown"]
        if not channels:
            continue
        interval = preview.get("selection") == "session_interval"
        interval_note = ""
        if interval:
            start = preview.get("intervalStartNs") or "unbounded"
            end = preview.get("intervalEndNs") or "unbounded"
            interval_note = (
                f"<p><strong>Excerpt interval: {escape(start)} to {escape(end)} "
                "session ns (inclusive).</strong> "
                "Membership uses each recorded MCAP batch anchor plus native timestamp deltas; "
                "this is not a clock calibration. Whole-recording QC checks and warnings "
                "remain outside this display selection.</p>"
                f"<p>{preview.get('matchingFrames', 0):,} timed frames match; "
                f"{preview.get('untimedFramesExcluded', 0):,} frames without native timestamps "
                "cannot be placed precisely and are excluded from this interval excerpt.</p>"
            )
        if not shown:
            if interval:
                sections.append(
                    f'<section class="preview"><h3>{escape(str(stream.get("sourceId", "")))} / '
                    f"{escape(str(stream.get('streamId', '')))}</h3>{interval_note}"
                    "<p>No timed samples to display in this interval. This is not an empty "
                    "recording or a passing signal-quality assessment.</p></section>"
                )
            continue
        figures = []
        for column, channel in enumerate(channels):
            chart_number += 1
            figures.append(_trace(channel, preview["units"], batches, column, shown, chart_number))
        origin_rows = []
        for batch in batches:
            native = batch["nativeTimeNs"]
            native_text = f"{native[0]} → {native[-1]}" if native else "not recorded"
            mapped = batch.get("mappedSessionTimeNs") or []
            mapped_text = f"{mapped[0]} → {mapped[-1]}" if mapped else "not available"
            first = batch["firstFrame"] + 1
            last = first + len(batch["values"]) - 1
            cells = (
                str(batch["segment"]),
                str(batch["messageIndex"] + 1),
                f"{first}–{last}",
                str(batch["sessionTimeNs"]),
                native_text,
                mapped_text,
            )
            origin_rows.append(
                "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in cells) + "</tr>"
            )
        selection_label = (
            f"First {shown:,} of {preview.get('matchingFrames', 0):,} matching timed sample frames"
            if interval
            else f"First {shown:,} of {preview['framesChecked']:,} recorded sample frames"
        )
        sections.append(f"""<section class="preview">
<h3>{escape(str(stream.get("sourceId", "")))} / {escape(str(stream.get("streamId", "")))}</h3>
{interval_note}
<p><strong>{selection_label}</strong>
· {len(channels)} of {preview["totalChannels"]} channels shown.
Exact values, no averaging or downsampling. Later samples and unshown channels are not plotted.</p>
<p class="meta">Each channel has its own amplitude scale. Points are spaced by recorded sample
position, not elapsed time; this view does not show gap duration. Lines stop at batch boundaries,
marked by dashed vertical lines.
Use Recorded gaps and Warnings when judging continuity. A short excerpt does not
establish quality across the recording. Units come from the stream descriptor.</p>
{"".join(figures)}
<details><summary>Show excerpt source and native timestamps</summary>
<p class="meta">Timestamp integers are retained unchanged. Session anchors and native device
timestamps are separate clocks; this excerpt does not calibrate or synchronize them.</p>
<div class="table-scroll"><table>
<tr><th>MCAP segment</th><th>message</th><th>sample positions</th>
<th>batch session anchor (ns)</th><th>first → last native timestamp (ns)</th>
<th>mapped excerpt session timestamps (ns)</th></tr>
{"".join(origin_rows)}</table></div></details>
</section>""")
    if not sections:
        return ""
    return "<h2>Recorded numeric excerpts</h2>" + "".join(sections)
