# Export selected analysis figures

The native Analysis workbench can package selected original PNG figures from a
completed job into a ZIP with that job's recorded provenance. This implements the
figure-selection and report-bundle workflow in
[Analysis Workbench §5 and §9](ANALYSIS_WORKBENCH.md).

## Researcher workflow

1. Load an analysis job in the existing gallery. Jobs with status `completed` or
   `completed_with_warnings` can export their recorded PNG figures.
2. Choose **Export figures…**. The dialog identifies the job, session, gap policy,
   parameters digest and recorded completion status. The list includes the static
   sync-dashboard PNG as well as other manifest-recorded PNG figures.
3. Check the figures to include. Selecting a row previews its original image.
   **Select all**, **Select none**, and the Space key operate the checkboxes.
4. Choose a ZIP destination outside the source session/job, then **Export ZIP**.
   Replacing an existing file requires an explicit confirmation. A cancelled file
   picker does not select a destination or create an export.
5. The success message names the completed destination and number of figures.
   On failure, the dialog retains the selection and destination for a retry.
   Closing or changing the loaded job requests cancellation of an active export.
   Cancellation is checked before publication; an already published ZIP remains complete.

The ZIP includes the job's original metadata and parameters, including recorded
session identifiers, paths, warnings, tooling and any extra provenance fields.
Review the displayed job identity before sharing it. The recorded package path
is the path saved by the analysis job; moving a session does not rewrite it.

An empty or invalid job leaves the export action disabled with a reason. A PNG
that has changed, is missing, cannot be read, or does not decode cannot be
exported as a successful figure. Files absent from the job's output inventory
are not offered. An unselected missing PNG does not prevent exporting other
valid figures.

## Bundle format: `capture.analysis_figure_bundle/1`

The archive contains exactly the chosen original PNGs, `source/job_manifest.json`,
`source/params.json`, and `manifest.json`. PNG member paths preserve each recorded
`outputs[].relativePath`; selection order is retained in the figure inventory.
PNG bytes are copied without resizing, conversion, replotting or metadata edits.
The two source JSON files are also copied byte-for-byte, including unknown fields
and original formatting. No raw stream, feature table, report or log is added.

The UTF-8 `manifest.json` object has the following version 1 fields:

| Field | Type | Meaning |
|---|---|---|
| `schemaId` | string | Exactly `capture.analysis_figure_bundle/1`. |
| `createdUtc` | string | UTC ISO 8601 time when this bundle manifest was prepared. |
| `jobId` | string | Exact saved job ID; loading requires it to match the job directory. |
| `sessionId` | string | Exact nonempty session ID recorded by the job. |
| `paramsDigest` | string | Saved canonical-parameters SHA-256, verified against `params.json`. |
| `figures` | array of file records | The explicitly selected original PNGs, in selection order. |
| `sourceFiles` | array of file records | The original job manifest and parameters, in that order. |

Each file record contains `path` (archive-relative POSIX path),
`sourceRelativePath` (path relative to the loaded job), `bytes` (actual byte
count), and `sha256` (lowercase hexadecimal SHA-256 of those exact exported
bytes). Member paths are portable, relative paths without traversal or linked
source files. Case-insensitive duplicate paths in a job inventory are rejected
so the bundle has one interpretation on Windows and POSIX.

Parameters use the existing analysis-job canonicalization:
`json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`
encoded as UTF-8. The original `params.json` byte digest is a separate value;
formatting differences must not be mistaken for a different canonical parameter
set. Duplicate JSON keys and non-finite values are rejected.

Recorded PNG byte counts and digests, and the recorded `params.json` output, must
match their actual inputs. The bundle's source-file digests are newly computed
from the original JSON bytes. In particular, an older job manifest may contain
its own historical output hash from before its final rewrite. That entry remains
unchanged inside the original manifest; it is **not** used to claim verification
of the current manifest bytes. `sourceFiles` identifies the actual bytes included.

All source identities, units, grids, masks, gaps, warnings and tooling remain the
job producer's recorded claims. Export verifies the selected artifacts and saved
parameters; it does not recompute scientific results, validate hardware timing,
rehash the session's raw streams or convert recorded provenance into a new
scientific or hardware qualification.

## Failure and resource behavior

The loader binds the job directory, original manifest bytes and original
parameters. Export refuses a changed job, parameters or selected figure. PNG
decoding uses the same native Qt image facilities as the desktop. Version 1
bounds each source JSON file to 4 MiB, each PNG to 64 MiB, and selected PNG bytes
to 512 MiB. Export a smaller selection when the aggregate bound is exceeded.
Only one PNG payload is retained at a time by the writer.

Work runs in a Qt worker thread. The UI remains available to request cancellation;
the worker checks cancellation between bounded file operations and before
publication. A clear/reload invalidates the old dialog, prevents exporting its
selection for a new job, and lets any worker finish cancellation before closing.
Application shutdown requests cancellation and joins its worker.

The archive is staged in a uniquely owned temporary file beside its destination,
closed and flushed before publication. A failed read, validation, write, flush,
cancellation or refused publication leaves a previous export unchanged. A new
destination cannot silently overwrite a file that appeared while export ran.
Windows publishes a new file with non-replacing rename; POSIX uses a same-directory
hard link, so new-file export requires hard-link support on the chosen POSIX
filesystem. Explicit replacement uses `os.replace`. Any temporary-file cleanup
failure is logged with the retained path; cleanup cannot turn an already
published bundle into a reported failure.

This is bounded exception/cancellation recovery for a local export. It does not
lock the source package or coordinate concurrent external writers. It does not
promise a multi-file snapshot of a live changing job or directory durability
after power loss. Only completed jobs are eligible, and all source/session files
are opened read-only. The export destination may not be inside the source job
or its containing capture session.

## Receiving and ownership

`tests/ui/test_analysis_figure_export.py` exercises exact subset bytes and full
original provenance, malformed jobs/inventories, stale and invalid images,
output-write/flush/publication failures, concurrent destination arrival, native
keyboard selection, cancellation, clear/reload, and retry after explicit
replacement confirmation. Its final scenario runs the actual MCAP-backed
analysis producer and exports the resulting figures through the native dialog.

The existing `FigureGallery.clear()` / `load_job_dir(Path)` contract, sync image
loading and JobInspector are preserved. Saved-job history owns its screen and
package-selection hooks separately. No capture, worker, analysis computation,
job publication, raw/session export, settings or dependency behavior changes.
Local offscreen Linux/Qt receiving is separate from the proposed-head Windows CI
gate and makes no live-device or installed-desktop claim.
