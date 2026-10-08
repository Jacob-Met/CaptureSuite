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


def _collect_entry(ordinal: int, spelling: str, package: Path) -> dict[str, Any]:
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
        qc = collect_qc(package).to_dict()
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


def _package_html(entry: dict[str, Any]) -> str:
    ordinal = entry["ordinal"]
    qc = entry["qc"]
    if qc is None:
        heading = f"Package {ordinal}"
        disposition = '<span class="badge collection-failed">Collection failed</span>'
        detail = (
            '<div class="collection-error"><h3>Collection error</h3>'
            f'<p><strong>{_text(entry["error"]["type"])}</strong></p>'
            f'<p class="literal">{_text(entry["error"]["message"])}</p></div>'
        )
    else:
        heading = _text(qc["sessionId"])
        disposition = '<span class="badge collected">Collected</span>'
        lights = []
        for source, level in qc["trafficLights"].items():
            color = level if level in ("ok", "warn", "fail") else "unknown"
            lights.append(
                '<li class="light-row">'
                f'<span class="literal identity">{_text(source)}</span>'
                f'<span class="badge native-{color}">{_text(level)}</span></li>'
            )
        light_list = "".join(lights) or "<li>No source indicators reported.</li>"
        warnings = "".join(
            f'<li class="literal">{_text(warning)}</li>' for warning in qc["warnings"]
        ) or "<li>No warnings listed by the native collector.</li>"
        detail = (
            '<dl class="facts">'
            f'<div><dt>Package state</dt><dd>{_text(qc["packageState"])}</dd></div>'
            f'<div><dt>Sources</dt><dd>{_text(qc["sourceCount"])}</dd></div>'
            f'<div><dt>Streams</dt><dd>{_text(qc["streamCount"])}</dd></div>'
            f'<div><dt>Open / closed gaps</dt><dd>{_text(qc["openGapCount"])} / '
            f'{_text(qc["closedGapCount"])}</dd></div></dl>'
            '<h3>Native source indicators</h3>'
            f'<ul class="lights">{light_list}</ul>'
            '<h3>Native warnings</h3>'
            f'<ul class="warnings">{warnings}</ul>'
            '<p class="reports">'
            f'<a href="{_text(entry["reports"]["html"])}">Open native QC HTML</a>'
            f'<a href="{_text(entry["reports"]["json"])}">Open native QC JSON</a></p>'
        )
    return (
        f'<article class="package" data-qc-review-ordinal="{ordinal}">'
        '<header class="package-heading">'
        f'<p class="ordinal">Requested package {ordinal}</p>{disposition}'
        f'<h2 class="literal">{heading}</h2></header>'
        '<dl class="paths">'
        f'<dt>Requested path</dt><dd class="literal">{_text(entry["inputPath"])}</dd>'
        f'<dt>Resolved package</dt><dd class="literal">{_text(entry["packagePath"])}</dd>'
        f'</dl>{detail}</article>'
    )


def render_qc_package_review_html(review: dict[str, Any]) -> str:
    """Render only the new index; native report HTML is never restyled."""
    packages = "\n".join(_package_html(entry) for entry in review["packages"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Package QC review — CaptureSuite</title>
<style>
:root {{
  color-scheme: light dark;
  --bg: #f4f6f8; --panel: #ffffff; --border: #c8d0da; --text: #1a2332;
  --dim: #5a6573; --accent: #2563eb; --success: #15803d;
  --warning: #a16207; --danger: #dc2626;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #12161c; --panel: #1a2029; --border: #2c3542; --text: #dfe6ef;
    --dim: #8d9aab; --accent: #3d8bfd; --success: #35c46b;
    --warning: #f0a13a; --danger: #e5484d;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 "Segoe UI", system-ui, sans-serif;
}}
main {{ max-width: 1120px; margin: 0 auto; padding: 24px 16px 32px; }}
h1 {{ margin: 0 0 12px; font-size: 1.75rem; line-height: 1.25; }}
h2 {{ margin: 8px 0 0; font-size: 1.25rem; line-height: 1.4; }}
h3 {{ margin: 24px 0 8px; font-size: 1rem; }}
p {{ margin: 8px 0; }}
a {{ color: var(--accent); text-underline-offset: 3px; }}
a:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 4px; }}
.intro {{ max-width: 80ch; }}
.eyebrow, .ordinal, dt, .scope {{ color: var(--dim); }}
.eyebrow {{ margin: 0 0 8px; }}
.summary {{
  display: flex; flex-wrap: wrap; gap: 8px 24px; padding: 16px;
  margin: 24px 0; border: 1px solid var(--border); border-radius: 6px;
  background: var(--panel);
}}
.summary p {{ margin: 0; }}
.summary strong {{ font-size: 1.25rem; margin-right: 4px; }}
.package {{
  min-width: 0; margin: 16px 0; padding: 16px; border: 1px solid var(--border);
  border-radius: 6px; background: var(--panel);
}}
.package-heading {{ display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }}
.package-heading h2 {{ flex-basis: 100%; }}
.ordinal {{ margin: 0; }}
.badge {{
  display: inline-block; padding: 2px 8px; border: 1px solid currentColor;
  border-radius: 6px; font-size: 0.875rem; font-weight: 600; line-height: 1.5;
}}
.collected {{ color: var(--accent); }}
.collection-failed, .native-fail {{ color: var(--danger); }}
.native-warn {{ color: var(--warning); }}
.native-ok {{ color: var(--success); }}
.literal {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.paths {{ margin: 16px 0; }}
.paths dt {{ margin-top: 8px; font-size: 0.875rem; }}
.paths dd {{
  margin: 4px 0 0; font: 0.875rem/1.5 Consolas, ui-monospace, monospace;
  white-space: pre-wrap; overflow-wrap: anywhere;
}}
.facts {{ display: flex; flex-wrap: wrap; gap: 12px 24px; margin: 16px 0; }}
.facts dd {{ margin: 4px 0 0; font-variant-numeric: tabular-nums; }}
.facts dt {{ font-size: 0.875rem; }}
.lights {{ list-style: none; margin: 0; padding: 0; }}
.light-row {{ display: flex; gap: 12px; align-items: start; margin: 8px 0; }}
.identity {{ min-width: 0; flex: 1; }}
.warnings {{ padding-left: 24px; margin: 8px 0; }}
.warnings li {{ margin: 8px 0; }}
.reports {{ display: flex; flex-wrap: wrap; gap: 12px 24px; margin-top: 24px; }}
.collection-error {{
  padding-top: 8px; border-top: 1px solid var(--border); overflow-wrap: anywhere;
}}
.collection-error h3 {{ margin-top: 8px; }}
footer {{ margin-top: 24px; font-size: 0.875rem; }}
@media (max-width: 480px) {{
  main {{ padding: 16px 12px 24px; }}
  h1 {{ font-size: 1.5rem; }}
  .package {{ padding: 16px; }}
}}
</style>
</head>
<body>
<main>
<header class="intro">
<p class="eyebrow">CaptureSuite · offline package review</p>
<h1>Package QC review</h1>
<p>Each entry retains the selected package's native QC observations and its own report.
Packages stay in the requested order, even when session IDs match.</p>
<p class="scope"><strong>Collected</strong> means the native report was read successfully.
Native warnings and failure indicators remain separate below.</p>
</header>
<section class="summary" aria-label="Collection summary">
<p><strong>{review["packageCount"]}</strong> requested</p>
<p><strong>{review["collectedCount"]}</strong> collected</p>
<p><strong>{review["failedCount"]}</strong> collection failed</p>
</section>
{packages}
<footer class="scope">
<p>This review inventories package metadata and the native collector's reported observations.
It does not rehash raw streams, decode segments, certify scientific validity, combine gap durations
or establish that unreported data is healthy. Native optional-record handling is unchanged.</p>
<p>Each linked HTML and JSON file is the exact native per-package report for this collection.
Source packages and prior processing outputs are not modified by this command.</p>
</footer>
</main>
</body>
</html>
"""


def _write_bytes(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)


def create_qc_package_review(
    package_paths: Sequence[str | Path], output_directory: str | Path,
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
        _collect_entry(ordinal, spelling, package)
        for ordinal, (spelling, package) in enumerate(selected, 1)
    ]
    collected = sum(entry["status"] == "collected" for entry in packages)
    review = {
        "schemaId": "capture.qc_package_review/1",
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
