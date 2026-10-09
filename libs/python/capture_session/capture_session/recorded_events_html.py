# SPDX-License-Identifier: GPL-3.0-only
"""Standalone presentation of records returned by the existing package reader."""

from __future__ import annotations

import json
from dataclasses import asdict
from html import escape

from capture_session.package_reader import ReviewSummary

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f4f6f8;
  --panel: #ffffff;
  --panel-alt: #eef1f5;
  --border: #c8d0da;
  --text: #1a2332;
  --dim: #5a6573;
  --accent: #2563eb;
  --warning: #d97706;
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 24px;
  --space-2xl: 32px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12161c;
    --panel: #1a2029;
    --panel-alt: #212934;
    --border: #2c3542;
    --text: #dfe6ef;
    --dim: #8d9aab;
    --accent: #3d8bfd;
    --warning: #f0a13a;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: auto; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 11pt/1.35 "Segoe UI", system-ui, sans-serif;
}
main { max-width: 80rem; margin: auto; padding: var(--space-xl); }
header, section, footer { margin-bottom: var(--space-xl); }
h1 { font-size: 16pt; font-weight: 600; margin: 0 0 var(--space-sm); }
h2 { font-size: 13pt; font-weight: 600; margin: 0 0 var(--space-md); }
p, ul { margin: var(--space-sm) 0; }
li + li { margin-top: var(--space-xs); }
a { color: var(--accent); text-underline-offset: 3px; }
a:focus-visible, summary:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: var(--space-xs);
}
nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
  margin: var(--space-lg) 0;
}
.panel, details, .notice {
  padding: var(--space-lg);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 6px;
}
.notice { border-left: 4px solid var(--warning); }
.subtitle, .dim { color: var(--dim); }
table { width: 100%; border-collapse: collapse; margin-top: var(--space-md); }
caption { text-align: left; font-weight: 600; margin-bottom: var(--space-sm); }
th, td { padding: var(--space-sm); border: 1px solid var(--border); text-align: left; }
th { background: var(--panel-alt); font-weight: 600; }
td { font-family: Consolas, ui-monospace, monospace; }
dl { display: grid; grid-template-columns: minmax(10rem, 1fr) 3fr; gap: var(--space-sm); }
dt { font-weight: 600; }
dd { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }
pre {
  margin: var(--space-md) 0 0;
  padding: var(--space-md);
  border: 1px solid var(--border);
  background: var(--panel-alt);
  font: 10pt/1.2 Consolas, ui-monospace, monospace;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
details { margin-top: var(--space-md); }
summary { cursor: pointer; font-weight: 600; }
footer { border-top: 1px solid var(--border); padding-top: var(--space-lg); }
@media (max-width: 42rem) {
  main { padding: var(--space-md); }
  dl { grid-template-columns: 1fr; }
  dd { margin-bottom: var(--space-sm); }
}
@media print {
  :root {
    color-scheme: light;
    --bg: #ffffff;
    --panel: #ffffff;
    --panel-alt: #f4f6f8;
    --border: #c8d0da;
    --text: #1a2332;
    --dim: #5a6573;
    --accent: #2563eb;
    --warning: #d97706;
  }
  main { max-width: none; padding: 0; }
  nav { display: none; }
  h1, h2, summary { break-after: avoid; }
  pre { overflow: visible; }
}
"""


def _text(value: object) -> str:
    # JSON permits escaped lone surrogates. Keep their escape notation without
    # making the generated UTF-8 file invalid or converting them to replacement text.
    text = str(value).encode("utf-8", errors="backslashreplace").decode("utf-8")
    return escape(text, quote=True)


def _json(value: object) -> str:
    return _text(json.dumps(value, ensure_ascii=False, indent=2))


def _records(section_id: str, title: str, singular: str, rows: list[dict]) -> str:
    parts = [
        f'<section id="{section_id}" aria-labelledby="{section_id}-title">',
        f'<h2 id="{section_id}-title">{title}</h2>',
        f'<p class="dim">{len(rows)} returned; reader order is preserved.</p>',
    ]
    if not rows:
        parts.append(
            f"<p>No {title.lower()} were returned. "
            "This does not prove that the package contained none.</p>"
        )
    for index, row in enumerate(rows):
        parts.extend(
            [
                "<details open>",
                f"<summary>{singular} {index + 1}</summary>",
                f'<pre data-kind="{section_id}" data-index="{index}">{_json(row)}</pre>',
                "</details>",
            ]
        )
    parts.append("</section>")
    return "\n".join(parts)


def render_recorded_events_html(summary: ReviewSummary) -> str:
    """Render returned records without interpreting, sorting or changing values.

    Event dictionaries remain complete. Gaps deliberately use GapSummary's
    normalized fields; this function cannot reconstruct omitted source content.
    No raw stream, integrity or recovery report body is read by the renderer.
    """
    counts = (
        ("checkpoints", "Checkpoint records returned", len(summary.checkpoints)),
        ("annotations", "Annotation records returned", len(summary.annotations)),
        ("sync-anchors", "Sync records returned", len(summary.sync_anchors)),
        ("gaps", "Normalized gap records returned", len(summary.gaps)),
    )
    metadata = (
        ("Package path read", summary.package_path),
        ("Session ID reported", summary.session_id),
        ("State reported", summary.state),
        ("Start wall time reported", summary.t0_wall_utc),
        ("Finalized time reported", summary.finalized_utc),
        ("Source identifiers returned", summary.source_ids),
        ("Recovery report paths returned; contents not opened", summary.recovery_reports),
    )
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\'; '
        'base-uri \'none\'; form-action \'none\'">',
        "<title>CaptureSuite — recorded-event report</title>",
        f"<style>{_STYLE}</style>",
        "</head>",
        "<body><main>",
        "<header>",
        "<h1>Recorded-event report</h1>",
        '<p class="subtitle">CaptureSuite · reader-returned records</p>',
        '<nav aria-label="Report sections">',
        '<a href="#overview">Package</a>',
        '<a href="#coverage">Coverage and limits</a>',
        '<a href="#checkpoints">Checkpoints</a>',
        '<a href="#annotations">Annotations</a>',
        '<a href="#sync-anchors">Sync records</a>',
        '<a href="#gaps">Gaps</a>',
        "</nav>",
        "</header>",
        '<section id="coverage" class="notice" aria-labelledby="coverage-title">',
        '<h2 id="coverage-title">Coverage and limits</h2>',
        "<p>This report shows only records returned by the package reader. "
        "Returned counts do not establish a complete or repaired capture.</p>",
        "<ul>",
        "<li>Missing optional event files, unsupported container shapes and filtered "
        "nonobject entries may be omitted. The reader does not enumerate these omissions; "
        "a zero returned count is not proof that no records existed.</li>",
        "<li>Checkpoint, annotation and sync dictionaries are shown in full as returned. "
        "Gap records are the reader's normalized projection: aliases and coercions "
        "are already applied and unknown raw gap fields are not retained.</li>",
        "<li>Record order and exact returned values are preserved. No time precedence, "
        "alignment, section boundaries, interpolation or gap duration is inferred. "
        "Gap closure and end time remain separate reported fields.</li>",
        "<li>The reported state is metadata, not verified integrity. This read is not "
        "an atomic filesystem snapshot and does not detect concurrent package changes. "
        "Raw streams and recovery report contents are not inspected.</li>",
        "</ul>",
        "</section>",
    ]
    if summary.state == "finalized_recovered":
        parts.extend(
            [
                '<section class="notice" aria-labelledby="recovered-title">',
                '<h2 id="recovered-title">Recovered session — recorded gaps preserved</h2>',
                "<p>The reader reports finalized_recovered. "
                "This does not establish pristine or complete data.</p>",
                "</section>",
            ]
        )
    parts.extend(
        [
            '<section id="overview" class="panel" aria-labelledby="overview-title">',
            '<h2 id="overview-title">Reader-reported package</h2>',
            "<dl>",
        ]
    )
    for label, value in metadata:
        parts.append(f"<dt>{label}</dt><dd>{_json(value)}</dd>")
    parts.extend(["</dl>", "<table>", "<caption>Returned record counts</caption>", "<tbody>"])
    for key, label, count in counts:
        parts.append(
            f'<tr><th scope="row">{label}</th><td id="count-{key}">{count}</td></tr>'
        )
    parts.extend(["</tbody></table>", "</section>"])
    parts.append(_records("checkpoints", "Checkpoint records", "Checkpoint", summary.checkpoints))
    parts.append(_records("annotations", "Annotation records", "Annotation", summary.annotations))
    parts.append(_records("sync-anchors", "Sync records", "Sync record", summary.sync_anchors))
    parts.append(
        '<section class="panel" aria-labelledby="gap-projection-title">'
        '<h2 id="gap-projection-title">Gap projection</h2>'
        "<p>The following seven-field objects are normalized GapSummary values, "
        "not copies of the original gap JSON. Integer time fields are nanoseconds; "
        "null means the reader returned no end value. A closed flag does not fill "
        "a missing end, and an end value does not override an open flag.</p></section>"
    )
    parts.append(
        _records(
            "gaps", "Normalized gap records", "Normalized gap",
            [asdict(g) for g in summary.gaps],
        )
    )
    parts.extend(
        [
            "<footer>",
            "<p>This file is self-contained and needs no server or network. "
            "Use the source package for original evidence. Expand record sections "
            "before printing if you have collapsed them.</p>",
            "</footer>",
            "</main></body></html>",
        ]
    )
    return "\n".join(parts) + "\n"
