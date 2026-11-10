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
  direct. Its current CLI discovery is useful, but it still lacks a desktop
  column chooser connected to the same exporter.
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

The next export usability gap is contextual selection: the dialog presents
unavailable modalities and does not summarize discovered data or the timing
basis before export. Its actual values remain reusable. Full native desktop
navigation/distribution and real-instrument judgment remain separate gaps.
Producing task `capturesuite-numeric-sample-export-lark61c2`; separate use verdict
`capturesuite-numeric-export-use-tern93ab`.

## Ranked gaps

1. **Prove the complete researcher workflow with real recordings.** Existing
   portable checks use synthetic values in real MCAP files. Independent operator
   judging and real-device validation remain separate from those checks.
2. **Bring retained results into the maintained desktop.** Saved-history,
   nested-figure and selected-feature handoffs should be reachable in the actual
   Analysis workspace. PRs 71, 80, 81 and 94 contain earlier work; inspect current
   main and integrate useful parts rather than restarting them.
3. **Make distribution practical across supported workflows.** The Linux offline
   executable is experimental. Windows capture, native desktop delivery and
   sustained acquisition/recovery need current runnable releases and direct use.
4. **Expand device and timing confidence from measurements.** Preserve the
   documented simulation/replay development path while closing measured vendor
   and multi-device gaps; no inferred hardware synchronization.

Independent judging findings belong above these standing gaps when they reveal a
more immediate user problem. Track current work and verdicts on the taskboard;
keep [README.md](README.md) and the release notes accurate about what runs.

## Current improvement

Selected-feature export from the existing PR 81 is connected to the
maintained offline executable in this source. It adds table/column discovery and external
CSV/Parquet handoff while preserving source warnings, row order and job metadata.
The taskboard record is `capturesuite-retained-feature-export-mizunagi`;
a merge, runnable release and separate analyst judgment must be recorded before
this is described as shipped.

Recorded numeric sample export now complements derived-feature handoff:
the existing Export dialog and offline `export-session` command preserve
channel values, original native/MCAP clocks and copied gaps. Missing native
clocks remain unknown; within-batch session estimates are explicitly
uncalibrated. Producing task: `capturesuite-numeric-sample-export-lark61c2`;
the source is merged and the exact downloadable Linux CLI was independently
downloaded and used by Tern93ab. The native dialog is source-delivered; the archive
does not include a Windows desktop. See the release and verdict above.
