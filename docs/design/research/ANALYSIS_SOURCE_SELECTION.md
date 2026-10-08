# Analysis source selection

Issue #62 implements the existing source-filter contract in the offline Analysis
workbench. It composes with the sealed-session time scope; acquisition, raw
recordings, package history and the backend pipeline are unchanged.

## Operator controls

**All recorded sources** keeps the existing default. **Selected sources** opens a
native checkbox chooser and requires an intentional, nonempty selection. Every
recorded stream belonging to each selected source is included. Choosing every
listed ID remains an explicit subset in job parameters, distinct from the All
default.

The chooser uses the exact source IDs returned by
`capture_analysis.discover.discover_streams`. A package's source directory name
or Review source count is not an alias for its descriptor ID. Streams are not
excluded by their descriptive modality: for example, `generic.numeric_batch/1`
can describe an EMG or EEG measurement and still use the numeric handler.

The selected IDs remain visible and can be copied. Cancelling the chooser keeps
the previous selection. Switching temporarily to All remembers the subset;
reopening the same package also preserves it. A different package resets to All,
and a failed open disables the selector with the rest of Analysis.

## Job contract

| Selection | Existing job parameters | Recorded job provenance |
|---|---|---|
| All recorded sources | `sources: []` | `sourcesSelected` contains discovered source IDs |
| Selected sources | `sources: [exact ID, ...]` | `sourcesSelected` contains the selected recorded IDs |
| Empty, vanished or unreadable subset | Job is not started | No processing output is created |

Features, Plots, Features + plots and Pose consume source filters. QC-only,
Kinematics, ML bundle and Eval require All recorded sources because their current
implementations operate on the full package or selected input jobs. The QC report
continues to describe the whole package even when a feature or pose job selects
a subset.

Each worker receives an immutable tuple and copies it into `JobParams.sources`.
Editing the next selection cannot alter a running job. The existing command
arguments, time bounds, errors, completion and history hooks retain their
behavior.

## Admission and refresh

Inventory is refreshed when a package is loaded, when the chooser opens, after
the operator accepts a choice, and immediately before job launch. Routine desktop
timer refreshes use the cached inventory and do not walk recorded files.

A vanished selected ID remains visible with an explanation and blocks Run until
the operator repairs the selection or explicitly chooses All. The UI never
silently intersects it away, substitutes a folder token, or interprets an empty
Selected choice as All. Invalid descriptor metadata makes explicit selection
unavailable; All retains the existing backend admission and error policy.

## Receiving

`tests/ui/test_analysis_sources.py` uses actual Qt controls and QThreads with
real protobuf MCAP fixtures. Its two-source, three-stream numeric package includes
numeric/EMG/EEG descriptions and a source folder that differs from its descriptor
ID. All and both source subsets are checked against derived tables, existing
parameters/manifests, whole-package QC and unchanged raw hashes. One selected
job also consumes an exact time range. Additional cases cover empty and vanished
subsets, refresh/cancel/package transitions, command limits, invalid inventory
and supported Windows MainWindow navigation.

Source pins, the original missing-control failure, the separately incomplete
standalone harness, qualification and receiving results are retained under
`docs/evidence/analysis-sources-234cae4aee53/`. That incomplete harness produced a
completed backend job but did not finish its UI lifetime; it is not a UI pass.
