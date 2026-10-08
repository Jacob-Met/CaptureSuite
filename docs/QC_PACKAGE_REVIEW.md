# Review QC across selected packages

Use this offline command when you want one ordered review of several recorded packages,
with each package's native QC report kept separately. It reads the selected packages and
writes a new review directory outside them. It does not start an analysis job or a capture session.

## Create a review

Use the documented Python 3.12 analysis environment from the repository root. Select
1–32 package directories and a new output directory whose parent already exists:

```powershell
py -3.12 tools/review_qc_packages.py --output "D:\reviews\review-01" "D:\captures\first.mmsession" "D:\captures\second.mmsession"
```

Open `D:\reviews\review-01\index.html` directly in your browser. The index and linked
reports are local files; they do not require a web server or network access. Keep the
directory together when moving or sharing it so its relative report links continue to work.

Paths are interpreted relative to the command's working directory unless they are absolute.
The review retains the original argument spelling and the resolved package path.

Each manifest must explicitly declare `finalized` or `finalized_recovered`. Missing,
unreadable, malformed or nonfinalized packages appear as individual collection failures.
Later valid packages still receive their own reports. The command never discovers extra
packages, groups entries by session ID or drops repeated arguments.

## Read the result

The index shows packages in exactly the requested order, including failed entries.
Distinct packages with the same session ID stay separate. Each collected entry shows
its full identity and path, native warnings, source indicators and links to its exact native
HTML and JSON reports. Literal text, including markup-like content, is displayed as text.

**Collected** means the native report was read successfully. A collected package may
still have native `warn` or `fail` indicators. These are shown separately from collection
errors; they do not cause a valid report to disappear.

| File | Contents |
| --- | --- |
| `index.html` | Ordered package list, collection disposition, warnings and report links. |
| `review.json` | Versioned summary with the complete native QC dictionary or explicit error for each requested path. |
| `reports/001-qc.json` | Exact native QC JSON for the first requested package, if collected. |
| `reports/001-qc.html` | Exact native QC HTML for that package, if collected. |

Report numbers use the original one-based position. If package 2 fails and package 3
is collected, package 3 uses `003-qc.json` and `003-qc.html`; numbering is not compacted.
Native JSON uses the existing sorted, two-space serialization without an added newline.
Native HTML is retained byte-for-byte in UTF-8 and is not restyled by the index.

| Exit status | Meaning |
| --- | --- |
| `0` | Every requested package was collected. Native QC warnings or failure indicators may still be present. |
| `1` | At least one package could not be collected, or writing the review failed. Read the index if completed and the command's error output. |
| `2` | Invalid invocation, package count or destination. No review is created by a rejected request. |

An existing output file or directory is refused. Output inside a selected package is
also refused after resolving path aliases, including a not-yet-created descendant.
The command requires an existing output parent and never replaces an earlier review.
If a write fails partway through, it exits with an error and retains its partial output
for inspection. Choose a new destination for a later attempt.

## JSON contract

`review.json` has schema ID `capture.qc_package_review/1`. Its top-level fields are
`schemaId`, `packageCount`, `collectedCount`, `failedCount` and `packages`.

Each package entry has `ordinal`, `inputPath`, `packagePath`, `status`, `qc`, `error`
and `reports`. A `collected` entry retains the complete native `qc` dictionary,
`error: null` and relative `json`/`html` report paths. A `failed` entry has
`qc: null`, `reports: null` and an error object containing `type` and `message`.

No aggregate quality score or inferred identity is added. Native gap ordering and
decimal strings for large timestamps, loss counts and durations remain unchanged.

## What this review establishes

The command reads the existing package metadata and the native collector's observations.
It leaves raw, event, manifest and processing files unchanged and does not access saved
application settings or the registry. A new invocation reads current package metadata;
it does not update previously completed review directories.

The existing collector inventories stream descriptors and segment names and hashes the
manifest. It does not rehash or decode all raw streams. Its existing treatment of
optional malformed records remains unchanged. An empty warning or gap list does not
establish complete coverage or healthy data, and this review is not scientific or
clinical validation. Gap durations are not combined into a downtime total.

The maintained `mini_session` used for receiving is synthetic and has two 28-byte MCAP
placeholders. Qualification checks the real collector, exact reports, native file admission,
CLI boundaries, package conservation and local report presentation; it does not claim
hardware or raw-stream decoding results.

## Native qualification

The independent consumer is
`tests/analysis/test_qc_package_review_receiving_7879.py`; its fixed installed-browser
helper is `tools/check_qc_package_review_index_7879.mjs`. The maintained CI collects
the same core test. The separate `qc-package-review-receiving` workflow retains actual
CLI reports and, when the installed runtime is available, directly opens the exported
index and native report at desktop and phone widths.

`tests/analysis/test_qc_packages.py` exercises additional malformed final-state admission.
`tests/analysis/test_qc_packages_cli.py` checks an authored destination-creation race
and a report-write failure through the actual CLI entrypoint. These narrow filesystem
fault injections are separate from the independent subprocess consumer.
