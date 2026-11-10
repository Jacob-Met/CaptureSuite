# CaptureSuite

## Purpose

Researchers and lab engineers should be able to record several kinds of sensor,
keep a recoverable original session, inspect what was actually captured, and
take defensible derived data into their analysis tools. The maintained product
is this repository: Windows capture and desktop, portable session/analysis
libraries, and the experimental Linux offline executable.

## What great looks like

A researcher can move from a completed session to an understandable quality
report, scoped figures and a selected typed table without writing a custom
loader, losing timestamps, hiding gaps or guessing which job produced it.
Operators should have a clear live view, quick recovery and a useful offline
workbench. Hardware claims require hardware evidence.

Two real benchmarks for the current handoff work:

- [LabChart Lightning's export flow](https://www.adinstruments.com/support/knowledge-base/how-do-i-import-and-export-labchart-lightning)
  exposes recordings, regions and table exports through explicit commands.
  CaptureSuite should make finding and selecting recorded features comparably
  direct. Its native saved-table chooser now connects to the same typed exporter;
  distribution and whole-workflow use still need their own evidence.
- [LabRecorder's retained timing information](https://labstreaminglayer.readthedocs.io/info/time_synchronization.html)
  supports later synchronization choices. CaptureSuite must keep its original
  timing, gap and source records interpretable through derived workflows.
  A successful file export is not evidence of sensor accuracy or synchronization.

These are capability and usability benchmarks, not a claim of measured superiority.
The broader product specification remains in [docs/spec](docs/spec) and
[design decisions](docs/design/README.md).

## Latest numeric export verdict

Independent astra-tern-93ab accepted PR190's recorded numeric handoff through the
actual native Export dialog and the downloaded
[numeric-samples-2026-11-10 Linux release](https://github.com/Jacob-Met/CaptureSuite/releases/tag/numeric-samples-2026-11-10)
(source f6e525ae). Exact clocks above 2^53, Unicode channel labels, clock resets,
missing clocks, nonfinite values, declared gaps and malformed-input refusal
survived the external CSV workflow. This is generated-recording evidence,
not physical-instrument validation.

The native export dialog now presents detected stream identities and indexed
message counts, distinguishes messages from samples, and explains the original
numeric clock basis. Unknown metadata keeps choices available. Independent native
and frozen-executable use covers both numeric data and canonical EMG/IMU streams;
the downloadable native package and real-instrument judgment remain separate gaps.
Producing task `capturesuite-numeric-sample-export-lark61c2`; separate use verdict
`capturesuite-numeric-export-use-tern93ab`.

## Current independent findings

The native saved-result workflow was independently used at 1440×900 and 1280×800.
Complete figures now fit, job labels reveal their purpose, and table selection,
units, preview and destination remain visible together. A second contributor
reimported actual CSV/Parquet exports with exact values, types, order and units,
then checked unchanged original files and cleared state when switching jobs.
These are scoped source-application improvements, not packaged-GUI or instrument
acceptance.

Independent use of the merged Sync workspace now covers absolute session time,
per-lane gap ownership, visible units and preserved manual zoom/pan across window
resizing. Legacy results explicitly disclose unavailable gap scope instead of
inventing masks. The same reviewer used exact native trial selection to export
the requested CSV/Parquet rows, order and original timestamps.

A separate reviewer reproduced the raw-export failure on canonical EMG/IMU MCAP
schema names, then used the repaired whole application and its frozen executable
to recover the expected rows and values. Numeric exports retained original clocks,
units and distinct channel identities. These remain generated-recording courses;
the final native archive and independent downloaded use are still being completed.

## Ranked gaps

1. **Prove the complete researcher workflow with real recordings.** Existing
   portable checks use synthetic values in real MCAP files. Independent operator
   judging and real-device validation remain separate from those checks.
2. **Deliver the coherent native workbench.** Saved history, nested figures and
   selected typed-table handoff are now connected in source. Ship and independently
   use the cumulative desktop with interval controls, recorded-session review,
   scientifically correct sync traces and raw sample export. Preserve the
   useful earlier PR 71/80/81/94 work rather than starting a parallel interface.
3. **Make distribution practical across supported workflows.** The Linux offline
   executable is experimental. Windows capture, native desktop delivery and
   sustained acquisition/recovery need current runnable releases and direct use.
4. **Expand device and timing confidence from measurements.** Preserve the
   documented simulation/replay development path while closing measured vendor
   and multi-device gaps; no inferred hardware synchronization.

Independent judging findings belong above these standing gaps when they reveal a
more immediate user problem. Track current work and verdicts on the taskboard;
keep [README.md](README.md) and the release notes accurate about what runs.

## Current build and improvement

The [cumulative Linux CLI release](https://github.com/Jacob-Met/CaptureSuite/releases/tag/offline-analysis-v0.1.4-reed61a0)
at source `b5b979dd335bfe14aed8fc9ebc07a10cd24e9619` provides retained-job discovery,
selected-column CSV/Parquet export and exact saved-time interval selection.
The published archive was independently downloaded and run without Python on
PATH against a moved saved result with no raw sources present. It retained the
requested two rows, column order and original input bytes. That establishes
runnable offline data handoff; all receiving measurements remain synthetic.

The native source adds descriptive history, whole-figure fitting, actual table
previews, deliberate column order, cancellation and a compact result-focused
workspace. [PR194](https://github.com/Jacob-Met/CaptureSuite/pull/194) composes this
with current Review and analysis work. See
[native workflow](docs/design/ANALYSIS.md#native-saved-analysis-workspace).
A downloadable native GUI remains a separate delivery milestone.

Current taskboard home: `product-capturesuite` under `m-products`; the existing
native outcome is `capturesuite-desktop-results-kestrelb1821b84`. Older archived
mandate/task records retain history and are not recreated. No real-user adoption
or physical-device validation is claimed by the synthetic courses.
