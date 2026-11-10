# SPDX-License-Identifier: GPL-3.0-only
"""Read selected finalized packages into a new external native-QC review."""

from __future__ import annotations

import json
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any

from capture_session import SessionPackageError, load_manifest

from capture_analysis.qc import collect_qc
from capture_analysis.report_html import render_qc_html

MAX_PACKAGES = 32
FINAL_STATES = ("finalized", "finalized_recovered")


class QcPackageReviewInputError(ValueError):
    """The explicit request cannot safely create a new external review."""


def _resolve_request(
    package_paths: Sequence[str | Path], output_directory: str | Path,
) -> tuple[list[tuple[str, Path]], Path]:
    if not 1 <= len(package_paths) <= MAX_PACKAGES:
        raise QcPackageReviewInputError(f"select between 1 and {MAX_PACKAGES} package paths")
    selected = []
    try:
        for value in package_paths:
            spelling = str(value)
            if not spelling:
                raise QcPackageReviewInputError("a package path must not be empty")
            selected.append((spelling, Path(spelling).resolve()))
        requested_output = Path(output_directory)
        output = requested_output.resolve()
        if requested_output.is_symlink() or output.exists():
            raise QcPackageReviewInputError(f"output already exists: {requested_output}")
        for _, package in selected:
            if output.is_relative_to(package):
                raise QcPackageReviewInputError(
                    f"output must be outside every selected package: {package}"
                )
        if not output.parent.is_dir():
            raise QcPackageReviewInputError(f"output parent must exist: {output.parent}")
    except (OSError, RuntimeError) as exc:
        raise QcPackageReviewInputError(f"cannot resolve the explicit paths: {exc}") from exc
    return selected, output


def _collect_entry(
    ordinal: int, spelling: str, package: Path, *, inspect_payloads: bool = False,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ordinal": ordinal,
        "inputPath": spelling,
        "packagePath": str(package),
        "status": "failed",
        "qc": None,
        "error": None,
        "reports": None,
    }
    try:
        manifest = load_manifest(package)
        if not isinstance(manifest, dict) or manifest.get("state") not in FINAL_STATES:
            raise SessionPackageError(
                "package manifest must explicitly be finalized or finalized_recovered"
            )
        qc = collect_qc(package, inspect_payloads=inspect_payloads).to_dict()
        # The native reader reads the manifest itself. Retain the final-state
        # admission if that second read observes a changed package.
        if qc["packageState"] not in FINAL_STATES:
            raise SessionPackageError("package is no longer finalized during collection")
    except Exception as exc:
        entry["error"] = {"type": type(exc).__name__, "message": str(exc) or type(exc).__name__}
    else:
        entry.update(
            status="collected",
            qc=qc,
            reports={
                "json": f"reports/{ordinal:03d}-qc.json",
                "html": f"reports/{ordinal:03d}-qc.html",
            },
        )
    return entry


def _text(value: Any) -> str:
    return escape(str(value), quote=True)


_DECODED_STATES = {
    "numeric_samples_checked", "emg_samples_checked", "imu_frames_checked",
}
_INSPECTION_LABELS = {
    "numeric_samples_checked": "Numeric samples decoded",
    "emg_samples_checked": "EMG samples decoded",
    "imu_frames_checked": "IMU frames decoded",
    "mcap_messages_checked": "Structure only — values not decoded",
    "not_requested": "Samples not inspected",
    "not_applicable": "No sample segments inspected",
    "failed": "Payload inspection failed",
}


def summarize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Describe native observations without assigning a signal-quality score."""
    qc = entry["qc"]
    if qc is None:
        return {"attention": True, "decoded": 0, "structureOnly": 0, "unchecked": 0}
    streams = qc["streams"]
    statuses = [(stream.get("payloadInspection") or {}).get("status") for stream in streams]
    return {
        "attention": bool(
            qc["warnings"] or not streams
            or any(level in ("warn", "fail") for level in qc["trafficLights"].values())
        ),
        "decoded": sum(status in _DECODED_STATES for status in statuses),
        "structureOnly": statuses.count("mcap_messages_checked"),
        "unchecked": sum(
            status not in _DECODED_STATES and status != "mcap_messages_checked"
            for status in statuses
        ),
    }


def _duration(nanoseconds: int) -> str:
    if nanoseconds <= 1:
        return "Unknown"
    seconds = nanoseconds / 1_000_000_000
    if seconds < 60:
        return f"{seconds:g} s"
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}m {remainder:g}s"


def _details_html(entry: dict[str, Any]) -> str:
    qc = entry["qc"]
    paths = (
        '<dl class="paths"><dt>Selected path</dt>'
        f'<dd>{_text(entry["inputPath"])}</dd><dt>Resolved package</dt>'
        f'<dd>{_text(entry["packagePath"])}</dd></dl>'
    )
    if qc is None:
        error = entry["error"]
        return (
            f'<p class="error"><strong>{_text(error["type"])}</strong>: '
            f'{_text(error["message"])}</p>{paths}'
        )
    warning_rows = "".join(f"<li>{_text(w)}</li>" for w in qc["warnings"])
    warnings = (
        f'<h3>Reported warnings</h3><ul class="warnings">{warning_rows}</ul>'
        if warning_rows else '<p>No warnings reported by the native collector.</p>'
    )
    stream_rows = []
    for stream in qc["streams"]:
        inspection = stream.get("payloadInspection") or {"status": "not_requested"}
        status = inspection.get("status", "not_requested")
        label = _INSPECTION_LABELS.get(status, str(status))
        detail = inspection.get("detail", "")
        stream_rows.append(
            "<tr>"
            f'<td>{_text(stream["sourceId"])}<small>{_text(stream["streamId"])}</small></td>'
            f'<td>{_text(stream["modality"])}</td>'
            f'<td>{_text(label)}'
            + (f'<small>{_text(detail)}</small>' if detail else "")
            + "</td></tr>"
        )
    stream_table = (
        '<div class="stream-scroll"><table class="streams"><caption>Inspection coverage'
        '</caption><thead><tr><th scope="col">Source / stream</th>'
        '<th scope="col">Modality</th><th scope="col">Evidence</th></tr></thead>'
        f'<tbody>{"".join(stream_rows)}</tbody></table></div>'
        if stream_rows else '<p class="error">No streams found in this recording.</p>'
    )
    indicators = "; ".join(
        f"{source}: {level}" for source, level in qc["trafficLights"].items()
    ) or "No source indicators reported"
    return (
        f'<div class="detail-content"><div>{warnings}{stream_table}'
        f'<p class="indicators">Native source indicators: {_text(indicators)}</p></div>'
        f'<div><p class="report-links">'
        f'<a href="{_text(entry["reports"]["html"])}">Open full QC report</a>'
        f'<a href="{_text(entry["reports"]["json"])}">QC JSON</a></p>'
        f'<p>Session ID <code>{_text(qc["sessionId"])}</code></p>{paths}</div></div>'
    )


def _package_html(entry: dict[str, Any]) -> str:
    ordinal = entry["ordinal"]
    qc = entry["qc"]
    summary = summarize_entry(entry)
    label = Path(entry["packagePath"]).name or entry["inputPath"]
    if qc is None:
        findings = '<strong class="error">Unavailable</strong>'
        findings += f'<small>{_text(entry["error"]["message"])}</small>'
        duration, inspection, gaps = "—", "Not inspected", "—"
        name_detail = "Could not collect this recording"
    else:
        duration = _duration(qc["durationNs"])
        inspection = f'{summary["decoded"]} / {qc["streamCount"]} streams decoded'
        if summary["structureOnly"]:
            inspection += f'<small>{summary["structureOnly"]} structure only</small>'
        if summary["unchecked"]:
            inspection += f'<small>{summary["unchecked"]} not decoded</small>'
        gaps = f'{qc["openGapCount"]} open · {qc["closedGapCount"]} closed'
        name_detail = f'{qc["sessionId"]} · {qc["packageState"]}'
        warnings = qc["warnings"]
        if summary["attention"]:
            warning_label = f"{len(warnings)} warning" + ("" if len(warnings) == 1 else "s")
            findings = f'<strong class="attention">{warning_label}</strong>'
            if warnings:
                findings += f'<small>{_text(warnings[0])}</small>'
            elif not qc["streams"]:
                findings = '<strong class="attention">No streams found</strong>'
            else:
                findings = '<strong class="attention">Source needs attention</strong>'
        else:
            findings = '<span>No native warnings</span>'
    return (
        f'<tbody data-qc-review-ordinal="{ordinal}" '
        f'data-attention="{str(summary["attention"]).lower()}">'
        '<tr class="recording-row">'
        f'<td class="ordinal" data-label="Number">{ordinal:02d}</td>'
        f'<th scope="row" class="recording-name">{_text(label)}'
        f'<small>{_text(name_detail)}</small></th>'
        f'<td data-label="Duration">{duration}</td>'
        f'<td data-label="Inspection">{inspection}</td>'
        f'<td data-label="Gaps">{gaps}</td>'
        f'<td data-label="Findings">{findings}</td></tr>'
        '<tr class="detail-row"><td colspan="6">'
        f'<details><summary>Inspect recording {ordinal}: warnings, streams and reports</summary>'
        f'{_details_html(entry)}</details></td></tr></tbody>'
    )


_STYLE = """
:root { color-scheme: light; --ink:#182730; --muted:#52636d; --rule:#cbd3d7;
  --paper:#fff; --wash:#f2f5f6; --accent:#00677b; --warning:#8d5100; --error:#a32c30; }
* { box-sizing:border-box; }
body { margin:0; background:var(--paper); color:var(--ink); font:14px/1.5 system-ui,sans-serif; }
.appbar { display:flex; align-items:center; justify-content:space-between; gap:20px;
  padding:14px 28px; border-bottom:2px solid var(--ink); }
.brand { font-weight:750; letter-spacing:-.025em; font-size:17px; }
.appbar a { font-size:13px; }
main { max-width:1520px; margin:auto; padding:26px 28px 40px; }
h1 { margin:0; font-size:28px; letter-spacing:-.035em; line-height:1.2; }
h3 { font-size:14px; margin:0 0 8px; }
.heading { display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; margin-bottom:18px; }
.counts { margin:0; color:var(--muted); }
.scope { border-left:3px solid var(--accent); background:var(--wash);
  padding:10px 14px; margin:0 0 22px; max-width:100ch; }
.toolbar { display:flex; align-items:end; gap:24px; justify-content:space-between;
  padding-bottom:14px; }
.search { display:grid; gap:5px; font-weight:600; font-size:12px; flex:0 1 360px; }
input[type="search"] { width:100%; padding:9px 10px; border:1px solid #81929c;
  border-radius:2px; background:white; color:var(--ink); font:14px system-ui,sans-serif; }
.filters { display:flex; gap:0; }
.filters button { background:white; color:var(--ink); padding:9px 13px;
  border:1px solid #81929c; font:inherit; cursor:pointer; }
.filters button + button { border-left:0; }
.filters button[aria-pressed="true"] { background:var(--ink); color:white; }
a { color:var(--accent); text-underline-offset:3px; }
button:focus-visible,input:focus-visible,a:focus-visible,summary:focus-visible {
  outline:3px solid #2e91a6; outline-offset:3px; }
.comparison { width:100%; border-collapse:collapse; table-layout:fixed; }
.comparison > caption { text-align:left; padding-bottom:8px; color:var(--muted); font-size:12px; }
.comparison > thead th { text-align:left; font-size:12px; font-weight:650;
  padding:10px 12px; background:var(--wash); border-block:1px solid var(--rule); }
.comparison > thead th:nth-child(1) { width:5%; }
.comparison > thead th:nth-child(2) { width:25%; }
.comparison > thead th:nth-child(3) { width:11%; }
.comparison > thead th:nth-child(4) { width:20%; }
.comparison > thead th:nth-child(5) { width:14%; }
.comparison > thead th:nth-child(6) { width:25%; }
.recording-row > td,.recording-row > th { text-align:left; vertical-align:top;
  padding:15px 12px 5px; overflow-wrap:anywhere; font-weight:400;
  font-variant-numeric:tabular-nums; }
.recording-row > .recording-name { font-weight:650; }
small { display:block; font-size:12px; font-weight:400; color:var(--muted);
  margin-top:4px; overflow-wrap:anywhere; white-space:pre-wrap; }
.ordinal { color:var(--muted); font-family:ui-monospace,monospace; }
.error { color:var(--error); } .attention { color:var(--warning); }
.detail-row > td { padding:0 12px 10px; border-bottom:1px solid var(--rule); }
summary { cursor:pointer; color:var(--accent); width:fit-content; padding:6px 0; font-size:12px; }
details[open] > summary { margin-bottom:8px; }
.detail-content { display:grid; grid-template-columns:minmax(0,1.8fr) minmax(0,1fr);
  gap:32px; padding:14px 12px 18px; background:var(--wash); }
.warnings { margin:0 0 18px; padding-left:20px; overflow-wrap:anywhere; }
.warnings li { margin:5px 0; white-space:pre-wrap; }
.streams { width:100%; border-collapse:collapse; font-size:12px; table-layout:fixed; }
.streams caption { text-align:left; font-weight:650; margin-bottom:6px; }
.streams th,.streams td { text-align:left; padding:7px 8px; vertical-align:top;
  border-bottom:1px solid var(--rule); overflow-wrap:anywhere; }
.streams th { font-size:11px; }
.streams small { font-size:11px; }
.paths { margin:14px 0 0; }
.paths dt { font-size:11px; color:var(--muted); margin-top:10px; }
.paths dd { margin:3px 0 0; font:12px/1.6 ui-monospace,monospace; overflow-wrap:anywhere;
  white-space:pre-wrap; }
code { font-size:12px; overflow-wrap:anywhere; white-space:pre-wrap; }
.report-links { display:flex; flex-wrap:wrap; gap:8px 20px; margin-top:0; }
.indicators { color:var(--muted); font-size:12px; overflow-wrap:anywhere; }
#empty { border-bottom:1px solid var(--rule); padding:28px 12px; margin:0; }
footer { margin-top:20px; max-width:105ch; font-size:12px; color:var(--muted); }
footer p { margin:6px 0; }
[hidden] { display:none !important; }
@media (max-width:800px) {
  .appbar { padding:12px 16px; } main { padding:20px 16px 28px; }
  .heading { gap:10px; } .toolbar { align-items:stretch; flex-direction:column; gap:12px; }
  .search { flex:auto; } .filters button { flex:1; }
  .comparison,.comparison > tbody { display:block; }
  .comparison > thead { display:none; } .comparison > caption { display:block; }
  .recording-row { display:grid; grid-template-columns:32px minmax(0,1fr) minmax(0,1fr); }
  .recording-row > td,.recording-row > th { padding:10px 6px 5px; }
  .recording-row > .ordinal { grid-column:1; grid-row:1; }
  .recording-row > .recording-name { grid-column:2/4; }
  .recording-row > td:nth-child(3) { grid-column:2; }
  .recording-row > td:nth-child(4) { grid-column:3; }
  .recording-row > td:nth-child(5),.recording-row > td:nth-child(6) { grid-column:2/4; }
  .recording-row > td:not(.ordinal)::before { content:attr(data-label); display:block;
    color:var(--muted); font-size:11px; margin-bottom:2px; }
  .detail-row,.detail-row > td { display:block; }
  .detail-row > td { padding-left:38px; }
  .detail-content { grid-template-columns:1fr; padding:12px; gap:14px; margin-left:-32px; }
  .streams { font-size:11px; } .streams th,.streams td { padding:6px 4px; }
  h1 { font-size:25px; }
}
@media print {
  .toolbar,.appbar a { display:none; }
  body { font-size:10pt; } main { padding:0; }
  .scope { background:none; } .comparison { table-layout:auto; }
  a { color:inherit; } footer { font-size:9pt; }
}
"""

_SCRIPT = """
(() => {
  const entries = Array.from(document.querySelectorAll('[data-qc-review-ordinal]'));
  const search = document.getElementById('search');
  const filters = Array.from(document.querySelectorAll('[data-filter]'));
  const count = document.getElementById('visible-count');
  const empty = document.getElementById('empty');
  let attentionOnly = false;
  const texts = entries.map(entry => entry.textContent.toLocaleLowerCase());
  function refresh() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    entries.forEach((entry, index) => {
      const matches = (!attentionOnly || entry.dataset.attention === 'true')
        && (!query || texts[index].includes(query));
      entry.hidden = !matches;
      if (matches) visible++;
    });
    count.textContent = visible + ' of ' + entries.length + ' recordings shown';
    empty.hidden = visible !== 0;
  }
  search.addEventListener('input', refresh);
  filters.forEach(button => button.addEventListener('click', () => {
    attentionOnly = button.dataset.filter === 'attention';
    filters.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    refresh();
  }));
  document.getElementById('clear').addEventListener('click', () => {
    search.value = ''; attentionOnly = false;
    filters.forEach(item => item.setAttribute(
      'aria-pressed', String(item.dataset.filter === 'all')));
    refresh(); search.focus();
  });
  refresh();
})();
"""


def render_qc_package_review_html(review: dict[str, Any]) -> str:
    """Put comparable evidence first, while keeping each complete native report."""
    packages = "\n".join(_package_html(entry) for entry in review["packages"])
    attention = sum(summarize_entry(entry)["attention"] for entry in review["packages"])
    scope = (
        "Recorded payloads inspected where supported. The table shows how many streams "
        "were decoded; unsupported streams remain explicitly unverified."
        if review.get("inspectPayloads") else
        "Metadata review — recorded samples were not inspected. Use --inspect-payloads "
        "to decode supported streams before making a sample-quality decision."
    )
    count = review["packageCount"]
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Compare recordings · CaptureSuite</title>'
        f"<style>{_STYLE}</style></head><body>"
        '<header class="appbar"><span class="brand">CaptureSuite</span>'
        '<a href="review.json" download>Download comparison JSON</a></header><main>'
        '<div class="heading"><h1>Compare recordings</h1>'
        f'<p class="counts">{count} selected · {attention} with warnings or unavailable'
        f' · {review["collectedCount"]} reports collected</p></div>'
        f'<p class="scope">{_text(scope)}</p>'
        '<div class="toolbar"><div class="filters" aria-label="Recording filter">'
        '<button type="button" data-filter="all" aria-pressed="true">All recordings</button>'
        '<button type="button" data-filter="attention" aria-pressed="false">'
        'Warnings or unavailable</button></div>'
        '<label class="search">Find recording, source or warning'
        '<input id="search" type="search" placeholder="Search selected recordings"></label></div>'
        '<table class="comparison"><caption id="visible-count" aria-live="polite">'
        f'{count} recordings in selection order</caption><thead><tr>'
        '<th scope="col">No.</th><th scope="col">Recording</th><th scope="col">Duration</th>'
        '<th scope="col">Inspection coverage</th><th scope="col">Recorded gaps</th>'
        f'<th scope="col">Findings</th></tr></thead>{packages}</table>'
        '<p id="empty" hidden>No recordings match. <button type="button" id="clear">'
        'Clear filters</button></p>'
        '<footer><p>Collected reports can contain warnings or failed inspections. '
        'No native warnings does not establish calibration, complete data coverage or '
        'scientific suitability. Gap counts are observations, not summed downtime.</p>'
        '<p>Each selection remains separate, including repeated paths or equal session IDs. '
        'Original recordings and saved analysis jobs are unchanged. Keep this folder together '
        'to retain the linked full reports.</p></footer></main>'
        f"<script>{_SCRIPT}</script></body></html>"
    )


def _write_bytes(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)


def create_qc_package_review(
    package_paths: Sequence[str | Path], output_directory: str | Path,
    *, inspect_payloads: bool = False,
) -> dict[str, Any]:
    """Write a new external review, retaining partial output if a write fails.

    Invalid requests raise QcPackageReviewInputError before creating output.
    Package read failures are returned as explicit entries. Output exceptions
    propagate to the caller; no existing file is replaced or removed.
    """
    selected, output = _resolve_request(package_paths, output_directory)
    try:
        output.mkdir()
    except FileExistsError as exc:
        raise QcPackageReviewInputError(f"output already exists: {output}") from exc
    (output / "reports").mkdir()
    packages = [
        _collect_entry(ordinal, spelling, package, inspect_payloads=inspect_payloads)
        for ordinal, (spelling, package) in enumerate(selected, 1)
    ]
    collected = sum(entry["status"] == "collected" for entry in packages)
    review = {
        "schemaId": "capture.qc_package_review/2",
        "inspectPayloads": inspect_payloads,
        "packageCount": len(packages),
        "collectedCount": collected,
        "failedCount": len(packages) - collected,
        "packages": packages,
    }
    for entry in packages:
        if entry["qc"] is not None:
            _write_bytes(
                output / entry["reports"]["json"],
                json.dumps(entry["qc"], indent=2, sort_keys=True).encode("utf-8"),
            )
            _write_bytes(
                output / entry["reports"]["html"],
                render_qc_html(entry["qc"]).encode("utf-8"),
            )
    _write_bytes(
        output / "review.json", json.dumps(review, indent=2, sort_keys=True).encode("utf-8")
    )
    _write_bytes(output / "index.html", render_qc_package_review_html(review).encode("utf-8"))
    return review
