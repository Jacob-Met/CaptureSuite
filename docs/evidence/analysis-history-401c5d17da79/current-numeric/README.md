# Current numeric output: retained gallery limitation

During the final current-parent check, main advanced to
`0ed1ccaa023a5327495565d59e1dd0b28b2ee5bd` (tree
`b8990a709744eab58b25b875596c79d0865cce4a`) by accepting numeric analysis
[PR #49](https://github.com/Jacob-Met/CaptureSuite/pull/49), owned by
`estate-e82707f2bc62` under issue #43. The six accepted numeric production
files remain unchanged in this history publication.

Those handlers write channel figures below
`figures/numeric/source-…/stream-…/channel_*.png`. The existing
`FigureGallery.load_job_dir` enumerates only `figures/*.png`. Its exact
unchanged source is:

- Path: `desktop/capture_desktop/widgets_analysis_plots.py`
- Git blob: `bb6c3033b5e4ed96a2e08857d38715b836926bf5`
- SHA-256: `85c73f881ee7d60ef2f868f7ff73fc57c0a4ef99a717f7f5015534db23e1ab86`

## One native reproduction

Runtime tree `210832e8a07ccc6dff8ead12e9bf45dde3b31652` combines that
actual main with the unchanged, accepted history runtime `37443f0d`.
The receiver uses the current accepted numeric test's small MCAP/protobuf
fixture helpers, then invokes the real `run(..., JobParams(command="all"))`.
It does not run the numeric owner's test suite or change its implementation.

The actual job writes two valid channel PNGs. Opening the retained job through
the native history selects the correct job and manifest in the inspector,
but the gallery contains only its **Sync** tab. Directly loading the same
job into a standalone instance of the unchanged gallery produces the same
missing channel tabs. This locates the gap in the pre-existing current-main
gallery reader rather than in saved-history selection.

The process exits 1 with **six positive checks and one failed presentation
check**, no exceptions. All 141 frozen source/fixture files and every generated
package/job byte remain unchanged while viewing; history starts no computation
thread. The only stderr is the standard offscreen `propagateSizeHints` warning.
The current history hooks, job identities and read-only behavior remain intact.

The snapshot `numeric-run/numeric-history-gap.png` is the first event-callback
frame before later paint/layout settling. Its visible Sync-only tab state is
supporting evidence; the exact widget tab counts and two valid on-disk PNGs in
`numeric-run/receipt.json` are the receiving proof. This frame is not a visual
layout qualification.

## Publication boundary

This history PR preserves its three-file production scope and the existing
gallery source. Nested numeric channel figures remain listed in the job's
saved output inventory and accessible in its job folder; the Sync result can
be selected, while individual nested channel tabs await a separately
coordinated gallery repair. This publication does not claim all current
numeric figures are displayed in the gallery.

The e43 QC/2 success remains separately pinned under `../current-qc/`.
Neither that success nor this current-main finding replaces the author's
14-test receipt or the independent 19-check native history receipt.

## Exact pins

| Artifact | SHA-256 |
| --- | --- |
| `check_numeric_gallery.py` | `c6d9c3aaf73e1cfef62c86dc36491440d3d6c6001996f149e2b978c97e2959d8` |
| `numeric-run/receipt.json` | `8e9f7cb7a8ce219b4fea8090cff5e1c602b6d4fb100a6d011983594206e3ef29` |
| `numeric.stdout.log` | `9d5c3d3907cd95f62cf380cc2b5196c33f183bfdeb5665ad0c3af42f2855eeaa` |
| `numeric.stderr.log` | `caeb11f6473c6c7125dd27478e588b85ffd6b31784e9adb1371a60f1661eb00f` |

The source manifest records the complete 141-file projection, including the
unchanged accepted fixture helper. `process.json` retains the exact command
and 4.471-second execution. Replaying `check_numeric_gallery.py` uses the same
`--source`, `--inputs`, and new private `--output` directory contract as the
current-QC companion. Its output must be outside the verified source.
