# Compare selected recordings

Use a single table to inspect several finalized CaptureSuite recordings, find
warnings, and open the evidence behind each result. This continues the original
multi-package review from PR #79; tools/compare_qc_reports.py remains available
for comparing the literal values of two already-saved JSON reports.

## Run the standalone command

Select the recordings explicitly and choose a new folder outside all of them:

~~~bash
./capturesuite-analysis review \
  "/data/force-baseline.mmsession" "/data/force-repeat.mmsession" \
  --inspect-payloads --strict-warnings --output "/data/review-nov10"
~~~

Open the printed index.html in a browser. No server or account is needed.
Keep the entire review folder together when moving it; full per-recording HTML
and JSON reports use relative links.

From a source checkout with the documented Python 3.12 analysis dependencies:

~~~bash
python tools/review_qc_packages.py first.mmsession repeat.mmsession \
  --inspect-payloads --output ../review-nov10
~~~

The command accepts 1–32 explicit paths. It does not search for extra recordings.
It reads the current source packages and writes only to the new external review.
It does not create analysis jobs inside the source packages.

## Read the comparison

The first screen compares recording duration, decoded-stream coverage, recorded
gap counts and native warnings. Selection order is retained, including repeated
paths or recordings with equal session IDs. Use **Warnings or unavailable** to
focus on native warnings, source failures, missing streams and collection errors.
Search includes recording names, session/source IDs, paths and warning text.

Expand a recording to see its warning list, each stream's inspection state,
source indicators and paths. **Open full QC report** exposes the native report;
**QC JSON** preserves its complete machine-readable observations.

| What is shown | What was observed |
| --- | --- |
| Streams decoded | The native collector decoded supported numeric, EMG or IMU payloads. |
| Structure only | MCAP messages were parsed; the schema's sample values were not decoded. |
| Not decoded | Samples were not requested, were not applicable, or inspection failed; expand for the exact state. |
| No native warnings | The collector listed no warnings. This does not establish calibration, complete coverage or scientific suitability. |
| Unavailable | This selected package could not be collected. Other valid selections still receive reports. |

Without --inspect-payloads, the output explicitly says **Metadata review**,
and coverage remains zero decoded streams. A green native metadata indicator is
not promoted into a statement about recorded sample quality. Unsupported schemas
remain structure-only even when payload inspection is requested.

Gap counts are not added into a downtime estimate: gaps can overlap or have no
known end. Native durations, loss counts, timestamps and warning text remain in
the individual reports. The command does not infer matching participants from
session IDs or score the scientific quality of a recording.

## Exit status and output

| Exit | Meaning |
| --- | --- |
| 0 | Every selection was collected. Warnings can still exist when strict mode is off. |
| 1 | A selection could not be collected, or output writing failed. A complete review keeps failed selections visible. |
| 2 | Invalid invocation/destination, or strict mode found native warnings, failed source indicators or no streams. A completed strict-warning review is retained. |

If both collection failures and QC warnings occur, exit 1 takes precedence.
An existing output directory or output inside any input package is refused.
A write failure reports that output may be partial; it never labels that output
a completed review or replaces an older review.

The review.json schema is capture.qc_package_review/2. The inspectPayloads field
records the requested inspection mode, alongside packageCount, collectedCount,
failedCount and the ordered packages list. Version 2 extends the original
unshipped PR79 contract with explicit payload-inspection scope. Each entry retains
its ordinal, requested/resolved paths, collection status, complete native qc,
error or relative report links. Per-recording files use the original ordinal
(reports/003-qc.html and reports/003-qc.json), even when an earlier selection failed.

## Product direction

The comparison follows the useful part of
[LabChart Lightning's cross-recording table workflow](https://www.adinstruments.com/support/videos/labchart-lightning-introductory-series-webinar-3-cross-recording-analysis):
put recordings next to one another and make their evidence accessible.
CaptureSuite currently provides an offline QC comparison. It does not match
LabChart's interactive waveform selection, region measurements or project-wide
statistical analysis. Those are real product gaps, not claims made by this review.

Validation uses generated, genuinely encoded protobuf MCAP with known finite,
nonfinite, unsupported-schema and missing-input cases. This establishes the
software's behavior on those recordings; it does not substitute for independent
review using physical instruments or long experimental sessions.
