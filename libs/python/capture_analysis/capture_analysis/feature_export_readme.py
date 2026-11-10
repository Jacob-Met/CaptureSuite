# SPDX-License-Identifier: GPL-3.0-only
"""Readable companion to exported measurements, with no inferred methods."""

from __future__ import annotations

from html import escape
from typing import Any

CONTEXT_SCHEMA = "capture.numeric_measurement_context/1"


def _e(value: Any) -> str:
    return escape(str(value), quote=True)


def _seconds(value: Any) -> str:
    if value is None:
        return "not recorded"
    number = int(value)
    whole, fraction = divmod(abs(number), 1_000_000_000)
    return ("−" if number < 0 else "") + f"{whole}.{fraction:09d}"


def _number(value: Any) -> str:
    return f"{value:.9g}" if isinstance(value, (int, float)) else _e(value)


def _flag(value: Any) -> str:
    return "yes" if value is True else "no" if value is False else "not recorded"


def render_feature_export_readme(
    manifest: dict[str, Any],
    params: dict[str, Any],
    schema: dict[str, Any],
    selection: dict[str, Any],
    data_files: list[str],
    context_preview: list[dict[str, Any]],
) -> str:
    metadata = schema["tableMetadata"]
    columns = metadata["columns"]
    context = metadata.get("measurementContext")
    known = isinstance(context, dict) and context.get("schemaId") == CONTEXT_SCHEMA
    rows = selection["rows"]
    warnings = manifest.get("warnings") or []
    if warnings:
        warning_html = (
            '<section class="notice" aria-labelledby="warnings"><h2 id="warnings">'
            "Original analysis warnings</h2><ul>"
            + "".join(f"<li>{_e(warning)}</li>" for warning in warnings)
            + "</ul><p>Exporting does not clear these findings.</p></section>"
        )
    elif manifest.get("status") == "completed_with_warnings":
        warning_html = '<p class="notice">The source analysis is marked with warnings.</p>'
    else:
        warning_html = (
            '<p class="status">No warnings were recorded by the source job. '
            "This does not establish calibration or complete measured coverage.</p>"
        )
    quality = []
    if any(column.get("provisional") is True for column in columns):
        quality.append("Includes provisional measurements")
    if any(column.get("calibrated") is False for column in columns):
        quality.append("includes uncalibrated columns")
    quality_html = '<p class="quality">' + _e("; ".join(quality)) + ".</p>" if quality else ""
    selected_summary = " · ".join(
        "<code>" + _e(column["name"]) + "</code> [" + _e(column["units"]) + "]"
        for column in columns[:6]
    )
    if len(columns) > 6:
        selected_summary += ' · <a href="#columns">' + str(len(columns) - 6) + " more</a>"
    links = " ".join(
        f'<a class="file" href="{name}">{label}</a>'
        for name, label in (
            ("table.csv", "Open selected CSV"),
            ("table.parquet", "Selected Parquet"),
            ("row_context.csv", "Row intervals & sample counts"),
        )
        if name in data_files
    )
    scope = selection.get("timeSelection")
    if scope:
        selection_html = (
            "<p>Rows selected where <code>" + _e(scope["column"]) + "</code> is in "
            "<strong>["
            + _seconds(scope["startNs"])
            + ", "
            + _seconds(scope["endNs"])
            + ") session seconds</strong> "
            "(start included, end excluded). "
            + _e(rows)
            + " of "
            + _e(scope["sourceRows"])
            + " retained rows.</p>"
            "<p>These bounds select existing rows. They do not crop or recompute "
            "a measurement window; its end can extend past the selected interval. "
            "Rows keep their original order.</p>"
        )
    else:
        selection_html = f"<p>All {_e(rows)} retained rows, in their original order.</p>"
    if rows == 0:
        selection_html += (
            '<p class="notice">No retained rows matched. Data files contain their '
            "column definitions and no measurement rows.</p>"
        )
    retained_range = manifest.get("timeRange") or {}
    start = retained_range.get("startSessionNs", params.get("startSessionNs"))
    end = retained_range.get("endSessionNs", params.get("endSessionNs"))
    if params.get("checkpointSection"):
        analysis_scope = (
            "Checkpoint section "
            + _e(params["checkpointSection"])
            + " · recorded start "
            + _seconds(start)
            + ", end "
            + _seconds(end)
            + " session seconds"
        )
    elif start is not None or end is not None:
        analysis_scope = (
            "Recorded start " + _seconds(start) + ", end " + _seconds(end) + " session seconds"
        )
    else:
        analysis_scope = "Full session requested"
    if known and context.get("methodId") == "numeric.basic.v2":
        method_html = (
            "<p><strong>Means and RMS use equal weights for valid retained samples.</strong> "
            "These are sample averages, not time-weighted averages.</p>"
            "<p>Elapsed window: <strong>" + _number(context["requestedWindowSeconds"])
            + " s</strong>; step: <strong>" + _number(context["requestedHopSeconds"])
            + " s</strong>. Bounds are rounded to nanoseconds. "
            "<code>t_start_ns</code> is inclusive; <code>t_end_ns</code> is exclusive. "
            "These time bounds do not prove continuous acquisition.</p>"
            "<p>Nominal rate: " + _number(context["sampleRateHz"]) + " Hz. "
            "<code>expected_sample_count</code> estimates nominal positions in each window; "
            "it is not clock calibration. <code>sample_count</code> counts retained samples, "
            "including masked ones; <code>valid_sample_count</code> counts samples used. "
            "<code>valid_fraction</code> divides used samples by the larger of nominal and "
            "retained counts. <code>gap_fraction</code> is one minus that fraction, "
            "including missing nominal positions. No samples are interpolated.</p>"
            "<p>Gap policy: <strong>" + _e(context["gapPolicy"]) + "</strong>. "
            "Mask keeps a fixed elapsed grid. Split restarts after declared gaps and "
            "retains short spans with their actual bounds. Empty windows are omitted.</p>"
        )
        if context["requestedWindowSeconds"] > context["requestedHopSeconds"]:
            method_html += (
                "<p><strong>Windows overlap.</strong> Adjacent rows can reuse samples; "
                "do not assume they are independent observations.</p>"
            )
    elif known:
        method_html = (
            "<p><strong>Means and RMS use equal weights for valid retained samples.</strong> "
            "These are sample averages, not time-weighted averages.</p>"
            '<div class="table-scroll" tabindex="0" role="region" aria-label="Window settings">'
            "<table><thead><tr><th>Setting</th><th>Requested</th><th>Retained slots</th>"
            "<th>Nominal duration</th></tr></thead><tbody><tr><th>Window</th><td>"
            + _number(context["requestedWindowSeconds"])
            + " s</td><td>"
            + _e(context["windowSampleSlots"])
            + "</td><td>"
            + _number(context["nominalWindowSeconds"])
            + " s</td></tr>"
            "<tr><th>Step within a run</th><td>"
            + _number(context["requestedHopSeconds"])
            + " s</td><td>"
            + _e(context["hopSampleSlots"])
            + "</td><td>"
            + _number(context["nominalHopSeconds"])
            + " s</td></tr></tbody></table></div>"
            "<p>Rate used: <strong>"
            + _number(context["sampleRateHz"])
            + " Hz</strong>. Requested seconds are rounded to the nearest integer "
            "sample count (ties to even), with at least one slot. Nominal durations "
            "are slot counts divided by this rate; they are <strong>not actual elapsed "
            "intervals or measured coverage</strong>.</p>"
            "<p>Each row’s <code>t_start_ns</code> is its first retained sample timestamp. "
            "<code>t_end_ns</code> is the last retained timestamp plus a rounded nominal "
            "sample period. Irregular timestamps can change this span. Intervals alone "
            "do not prove continuous acquisition.</p>"
            "<p><code>sample_count</code> includes masked slots; "
            "<code>valid_sample_count</code> counts samples actually used. "
            "Declared-gap samples are excluded, with no interpolated values. "
            "The mean is the arithmetic mean; RMS is the square root of the mean "
            "of squared valid sample values.</p>"
            "<p>Gap policy: <strong>" + _e(context["gapPolicy"]) + "</strong>. "
            "With split, window placement restarts in each retained run. Fully masked "
            "and incomplete trailing windows are omitted.</p>"
        )
        if context["windowSampleSlots"] > context["hopSampleSlots"]:
            method_html += (
                "<p><strong>Windows overlap.</strong> Adjacent rows can reuse samples; "
                "do not assume they are independent observations.</p>"
            )
    else:
        method_html = (
            '<p class="notice">The retained job does not record measurement-window '
            "or estimator details in a recognized context. No method has been inferred. "
            "Consult the original analysis before interpreting windowed values.</p>"
        )
    if schema.get("rowContext"):
        context_html = (
            '<p><a href="row_context.csv">row_context.csv</a> carries exact support '
            "for every exported row, including columns omitted from the selected table. "
            "<code>export_row</code> is <strong>one-based</strong>: 1 means the first "
            "data row after the CSV header, or the first Parquet row. It does not "
            "identify the original unfiltered row.</p>"
        )
        if context_preview:
            body = "".join(
                "<tr><th>"
                + _e(row["export_row"])
                + "</th><td>"
                + _seconds(row["t_start_ns"])
                + "</td><td>"
                + _seconds(row["t_end_ns"])
                + "</td><td>"
                + _e(row["sample_count"])
                + "</td><td>"
                + _e(row["valid_sample_count"])
                + "</td><td>"
                + _number(row["gap_fraction"])
                + "</td></tr>"
                for row in context_preview
            )
            context_html += (
                '<div class="table-scroll" tabindex="0" role="region" '
                'aria-label="Per-row support preview"><table><caption>First '
                + _e(len(context_preview))
                + " exported rows; full support is in the CSV"
                "</caption><thead><tr><th>Row</th><th>Start (session s)</th>"
                "<th>End (session s)</th><th>Slots</th><th>Used</th>"
                "<th>Masked fraction</th></tr></thead><tbody>" + body + "</tbody></table></div>"
            )
        context_html += (
            "<p>Nanosecond timestamps are exact signed integers. Use the field types "
            "in <code>_schema.json → rowContext</code>; spreadsheet numeric inference "
            "can round large integers.</p>"
        )
    else:
        context_html = (
            "<p>This retained job supplies no recognized per-row support context. "
            "Any selected time or quality columns remain in the data table. "
            "Missing support has not been reconstructed.</p>"
        )
    dictionary = "".join(
        "<tr><th><code>"
        + _e(col["name"])
        + "</code></th><td>"
        + _e(col["units"])
        + "</td><td>"
        + _e(col.get("description", "Description not recorded"))
        + "</td><td>"
        + _flag(col.get("provisional"))
        + "</td><td>"
        + _flag(col.get("calibrated"))
        + "</td></tr>"
        for col in columns
    )
    return (
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Selected measurements · """
        + _e(manifest["sessionId"])
        + """</title><style>
:root{color-scheme:light;
font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
color:#192e38;background:#fafbf9;font-size:16px;line-height:1.55}
*{box-sizing:border-box}body{margin:0;border-top:6px solid #0e6974}
main{max-width:1040px;margin:0 auto;padding:32px 36px 64px}
h1{font-size:30px;line-height:1.2;letter-spacing:-.025em;margin:0 0 8px}
h2{font-size:21px;line-height:1.3;margin:0 0 12px}
p{margin:10px 0 16px}section{margin-top:30px;padding-top:22px;border-top:1px solid #c5d0d2}
.identity{font-size:17px;margin:6px 0;overflow-wrap:anywhere}.muted{color:#4d6068}
.quality{font-weight:650;color:#714712;margin:10px 0}.status{color:#455b64;font-size:14px}
.notice{border-left:4px solid #b77723;background:#fff3de;padding:14px 18px;margin:18px 0}
.notice h2{font-size:18px}.notice p:last-child{margin-bottom:0}
a{color:#075b66;text-decoration-thickness:1.5px;text-underline-offset:3px}
a:focus-visible,.table-scroll:focus-visible{outline:3px solid #d78b19;outline-offset:3px}
.files{display:flex;gap:10px 24px;flex-wrap:wrap;margin:20px 0 8px}
.file{font-weight:650;display:inline-block;padding:8px 0}
code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}
dl{display:grid;grid-template-columns:155px minmax(0,1fr);gap:8px 18px}
dt{color:#455b64}dd{margin:0;overflow-wrap:anywhere}ul{padding-left:22px}
li{margin:5px 0;overflow-wrap:anywhere}.table-scroll{max-width:100%;overflow:auto}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.4;text-align:left}
th,td{padding:10px 12px;border-bottom:1px solid #d6dfe0;vertical-align:top}
th{font-weight:650}thead{background:#e8eff0}caption{text-align:left;font-size:13px;
color:#4d6068;padding:0 0 8px}tbody tr:nth-child(even){background:#f1f5f3}
.dictionary{min-width:620px}.dictionary th{min-width:150px}
footer{margin-top:32px;padding-top:16px;border-top:1px solid #c5d0d2;font-size:13px;color:#4d6068}
@media(max-width:600px){main{padding:22px 18px 40px}h1{font-size:27px}h2{font-size:20px}
dl{grid-template-columns:1fr;gap:2px}dd{margin-bottom:10px}th,td{padding:9px}
section{margin-top:24px}.files{gap:2px 20px}.notice{padding:12px}}
@media print{body{background:white}main{max-width:none;padding:12px}
.table-scroll{overflow:visible}a{color:inherit}section{break-inside:avoid}}
</style></head><body><main><h1>Selected measurements</h1>
<p class="identity"><strong>"""
        + _e(manifest["sessionId"])
        + """</strong></p>
<p class="identity">"""
        + _e(metadata.get("sourceId", "not recorded"))
        + " / "
        + _e(metadata.get("streamId", "not recorded"))
        + """</p><p class="muted">"""
        + _e(rows)
        + " rows · "
        + _e(len(columns))
        + """ selected columns</p>
"""
        + '<p class="identity">'
        + selected_summary
        + "</p>"
        + quality_html
        + warning_html
        + '<nav class="files" aria-label="Exported files">'
        + links
        + """</nav>
<section aria-labelledby="selection"><h2 id="selection">Which measurements are included</h2>
"""
        + selection_html
        + "<p>Original analysis: <strong>"
        + analysis_scope
        + """</strong>.</p></section>
<section aria-labelledby="method"><h2 id="method">What each number represents</h2>
"""
        + method_html
        + """</section>
<section aria-labelledby="support"><h2 id="support">Actual support for each row</h2>
"""
        + context_html
        + """</section>
<section aria-labelledby="columns"><h2 id="columns">Selected columns</h2>
<div class="table-scroll" tabindex="0" role="region" aria-label="Column definitions">
<table class="dictionary"><thead><tr><th>Column</th><th>Units</th><th>Meaning</th>
<th>Provisional</th><th>Calibrated</th></tr></thead><tbody>"""
        + dictionary
        + """</tbody></table>
</div></section><section aria-labelledby="origin"><h2 id="origin">Retained analysis record</h2>
<dl><dt>Job</dt><dd>"""
        + _e(manifest["jobId"])
        + """</dd><dt>Source job status</dt><dd>"""
        + _e(manifest["status"])
        + """</dd><dt>Original table</dt><dd><code>"""
        + _e(schema["tableRelativePath"])
        + """</code></dd></dl>
<p><a href="source/job_manifest.json">Original job</a> ·
<a href="source/params.json">Analysis parameters</a> ·
<a href="source/features_schema.json">Original feature definitions</a> ·
<a href="_schema.json">Export schema and field types</a> ·
<a href="manifest.json">Export manifest and file hashes</a></p></section>
<footer>CaptureSuite · Derived measurements. Raw recordings were not changed by this export.
Keep this folder together when handing measurements to another researcher.</footer>
</main></body></html>
"""
    )
