# SPDX-License-Identifier: GPL-3.0-only
"""Readable context for a collected measurement handoff; no new statistics."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return "Not recorded"
    return html.escape(str(value), quote=True)


def _seconds(value: int | None) -> str:
    if value is None:
        return "?"
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 1_000_000_000)
    return sign + str(whole) + (f".{fraction:09d}".rstrip("0") if fraction else "")


def _value(value: Any) -> str:
    if value is None:
        return '<span class="missing">null</span>'
    if isinstance(value, float):
        if math.isnan(value):
            return '<span class="missing">NaN</span>'
        if math.isinf(value):
            return "−∞" if value < 0 else "∞"
        return _text(f"{value:.8g}")
    return _text(value)


def write_collection_review(
    path: Path,
    records: list[dict[str, Any]],
    columns: list[dict[str, Any]],
    notices: list[str],
    previews: list[list[dict[str, Any]]],
    output_format: str,
) -> None:
    """Write an offline, responsive report with condition/scope before provenance."""
    conditions = len({record["condition"] for record in records})
    rows = sum(record["rows"] for record in records)
    input_rows = []
    warning_sections = []
    for record in records:
        scope = record["timeRange"] or {}
        clock = f"{_seconds(scope.get('startSessionNs'))}–{_seconds(scope.get('endSessionNs'))} s"
        scope_name = scope.get("mode") or "Scope not recorded"
        binding = (
            f"{_text(record['sourceId'])} / {_text(record['streamId'])}"
            if record["sourceId"] is not None and record["streamId"] is not None
            else "Source / stream binding not recorded"
        )
        warnings = record["warnings"]
        review = "Review warnings" if warnings else "No job warnings"
        input_rows.append(
            "<tr>"
            f'<th scope="row" data-label="Condition">{_text(record["condition"])}</th>'
            f'<td data-label="Recording">{_text(record["sessionId"])}'
            f"<small>{binding}</small></td>"
            f'<td data-label="Recorded scope"><span class="number">{clock}</span>'
            f"<small>{_text(scope_name)} · {_text(record['gapPolicy'])} gaps</small></td>"
            f'<td data-label="Rows" class="number">{record["rows"]}</td>'
            f'<td data-label="Review" class="{"warning" if warnings else ""}">{review}'
            f"<small>{_text(record['jobStatus'])}</small></td>"
            "</tr>"
        )
        if warnings:
            warning_sections.append(
                f"<li><strong>{_text(record['condition'])} · "
                f"{_text(record['sessionId'])}</strong><ul>"
                + "".join(f"<li>{_text(warning)}</li>" for warning in warnings)
                + "</ul></li>"
            )
    definition_rows = "".join(
        "<tr>"
        f'<th scope="row">{_text(column["name"])}</th>'
        f"<td>{_text(column['units'])}</td>"
        f"<td>{'Calibrated' if column['calibrated'] else 'Uncalibrated'}"
        f"{' · provisional' if column.get('provisional') else ''}</td>"
        "</tr>"
        for column in columns
    )
    preview_names = [column["name"] for column in columns[:6]]
    preview_header = "".join(f"<th>{_text(name)}</th>" for name in preview_names)
    preview_rows = "".join(
        "<tr>"
        f'<th scope="row">{_text(record["condition"])}</th>'
        + "".join(f'<td class="number">{_value(row[name])}</td>' for name in preview_names)
        + "</tr>"
        for record, sample in zip(records, previews, strict=True)
        for row in sample
    )
    download_links = "".join(
        f'<a href="table.{kind}" download>Download {kind.upper()}</a>'
        for kind in ("csv", "parquet")
        if output_format in {kind, "both"}
    )
    warning_content = (
        '<h2>Review before combining results</h2><ul class="warnings">'
        + "".join(warning_sections)
        + "".join(f"<li>{_text(notice)}</li>" for notice in notices)
        + "</ul>"
        if warning_sections or notices
        else ""
    )
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Collected measurements · CaptureSuite</title>
<style>
:root{color-scheme:light;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
color:#18262d;background:#fff;font-size:14px}
body{margin:0}main{max-width:1180px;margin:0 auto;padding:28px 32px 48px}
header{border-bottom:3px solid #244f60;padding-bottom:18px;margin-bottom:20px}
h1{font-size:26px;letter-spacing:-.025em;font-weight:650;margin:0 0 8px}
h2{font-size:17px;font-weight:650;margin:28px 0 10px}
p{line-height:1.55;margin:8px 0;color:#41535c}
nav{display:flex;gap:20px;flex-wrap:wrap;margin-top:14px}
a{color:#175267;text-underline-offset:3px;font-weight:600}
table{border-collapse:collapse;width:100%;text-align:left}
th,td{padding:11px 12px;border-bottom:1px solid #d3dce0;vertical-align:top;
overflow-wrap:anywhere}
thead th{font-size:12px;color:#52666f;font-weight:600;border-top:1px solid #8ca1ab}
tbody th{font-weight:600}small{display:block;font-size:12px;color:#60747e;margin-top:5px}
.number{font-variant-numeric:tabular-nums;font-family:ui-monospace,monospace}
.warning,.warnings{color:#8b3d16}.warnings{border-left:3px solid #b75b27;padding-left:23px;
line-height:1.55}.warnings li{margin:8px 0}.missing{color:#875734;font-style:italic}
.scroll{overflow:auto;max-width:100%}.preview{font-size:13px;min-width:560px}
.preview td{white-space:nowrap}.preview th{min-width:100px}
.note{max-width:85ch;font-size:13px}
details{margin-top:28px;border-top:1px solid #b7c6cd;padding-top:12px}
summary{cursor:pointer;color:#41535c}
footer{margin-top:24px;color:#60747e;font-size:12px}
@media(max-width:640px){
main{padding:20px 16px 32px}h1{font-size:22px}
.inputs thead{display:none}.inputs,.inputs tbody,.inputs tr{display:block}
.inputs tr{padding:14px 0;border-bottom:1px solid #b7c6cd}
.inputs th,.inputs td{display:block;padding:5px 0;border:0}
.inputs th{font-size:17px;margin-bottom:3px}
.inputs td:before{content:attr(data-label) ": ";font-family:system-ui,sans-serif;
font-size:12px;font-weight:600;color:#52666f}
.inputs small{margin-top:2px}
.measurements{font-size:12px}.measurements th,.measurements td{padding:8px 5px}
nav{gap:16px}.warnings{padding-left:19px}
}
</style></head><body><main>"""
    document += (
        "<header><h1>Collected measurements</h1>"
        f"<p>{conditions} conditions · {len(records)} saved tables · "
        f"<strong>{rows} window rows</strong></p>"
        f'<nav aria-label="Export files">{download_links}</nav></header>'
        '<table class="inputs"><thead><tr><th>Condition</th><th>Recording / source</th>'
        "<th>Recorded scope</th><th>Rows</th><th>Review</th></tr></thead><tbody>"
        + "".join(input_rows)
        + "</tbody></table>"
        '<p class="note">Values and session clocks are unchanged. Scope endpoints follow the '
        "saved analysis. Rows are feature windows, not independent experimental trials; "
        "unequal durations and missing samples can change how conditions should be compared.</p>"
        + warning_content
        + "<h2>Selected measurements</h2>"
        '<table class="measurements"><thead><tr><th>Measurement</th><th>Recorded unit</th>'
        "<th>Recorded status</th></tr></thead><tbody>" + definition_rows + "</tbody></table>"
        '<p class="note">Matching saved definitions permit a typed table handoff. They do not '
        "establish sensor accuracy, physical units or experimental comparability.</p>"
        "<h2>First rows from each input</h2>"
        f'<p class="note">Up to three original rows per input; showing '
        f"{len(preview_names)} of {len(columns)} selected measurements. "
        "The downloaded tables contain every original row plus its condition, "
        "session, job, source, scope, warning count and original row index.</p>"
        '<div class="scroll" tabindex="0" aria-label="Measurement preview">'
        '<table class="preview"><thead><tr><th>Condition</th>'
        + preview_header
        + "</tr></thead><tbody>"
        + preview_rows
        + "</tbody></table></div>"
        "<details><summary>Saved analysis details and machine-readable schema</summary>"
        '<p><a href="manifest.json">Input records, settings and warnings</a> · '
        '<a href="_schema.json">Column types and CSV reader settings</a></p>'
        '<p class="note">No averaging, session alignment, statistical testing or '
        "feature recalculation occurs during collection.</p></details>"
        "<footer>CaptureSuite · offline measurement handoff</footer></main></body></html>"
    )
    path.write_text(document, encoding="utf-8")
