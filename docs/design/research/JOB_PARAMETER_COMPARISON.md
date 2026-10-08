# Inspect and compare saved analysis parameters

The Analysis Workbench's **Job inspector** exposes **Parameters / compare…**
for its loaded, completed job. A reviewer can read the saved settings, choose
another completed job from the same session's jobs directory, and see which
settings differ without rerunning analysis or changing the loaded result.
This implements the parameter inspection and comparison part of
[Analysis Workbench §6](ANALYSIS_WORKBENCH.md).

## Operator workflow

1. In the loaded result's Job inspector, select **Parameters / compare…**.
   **Loaded job parameters** shows the complete parsed `params.json` and its
   input provenance. The text is read-only and can be selected and copied.
2. Select **Compare with saved job…**. In the native directory chooser, choose
   a different completed job in the same jobs directory. Both saved records
   must identify the same session. Cancelling the chooser preserves the
   current comparison.
3. Read the **Parameter comparison** table. Its columns consistently show
   **Other job** on the left and **Loaded job** on the right. Select a row with
   the mouse or keyboard to read both complete values below the table.
   Table previews may be shortened; the selected value panes retain the full
   value. **Comparison provenance** shows both source records and digests.
4. Use **Reload saved parameters** to read later changes to the saved files.
   Clearing the Job inspector or loading another job closes the old dialog
   and clears its comparison state.

The chooser does not change the main loaded job. The dialog does not edit
settings, launch analysis, register jobs or write to the session. Job discovery
and reopening results continue to belong to the Workbench's existing result
selection lifecycle.

## How differences are represented

The comparison is a deterministic comparison of the parsed JSON parameter
documents. Object keys are sorted; array positions retain their order. A row
is marked **Changed**, **Only in other**, or **Only in loaded**. A missing value
is displayed as `(absent)` and remains distinct from JSON `null`.

| Saved values | Result |
| --- | --- |
| `true` and `1` | Different types; a changed row |
| `1` and `1.0` | Integer and floating-point forms remain different |
| `-0.0` and `0.0` | The sign of floating-point zero remains different |
| `[1, 2]` and `[2, 1]` | Differences at the two array positions |
| Missing key and a key containing `null` | A one-sided row, with `null` retained |
| Empty object and empty array | A changed row at that parameter path |

Paths use JSON Pointer escaping. `/` separates an object key or array index;
`~1` represents a slash inside a key and `~0` represents a tilde. For example,
the key `a/b` containing the key `~label` appears as `/a~1b/~0label`.
The complete selected path is also shown as a quoted JSON string, preserving
unusual characters. Values in the full panes are formatted JSON, so a string
`"null"` remains distinguishable from the value `null`.

Displayed JSON is reformatted with sorted object keys and Unicode text. The
original saved bytes remain the input to file-digest checks. Formatting changes
in a saved file can change its file digest without producing a parameter-value
difference. Equivalent parsed floating-point forms, such as `1e0` and `1.0`,
do not produce a difference solely because their original spelling differs.

Zero differences means these saved parameter documents compare equally under
the rules above. It does not establish that input data, software versions,
models, numerical results or scientific conclusions are equivalent.

## What provenance is checked

The loaded job and comparison job each retain an immutable read of the original
`job_manifest.json` and `params.json` bytes. The viewer requires:

- A real job directory, a supported `capture.analysis_job/1` manifest, a job
  ID matching the directory, and a nonempty recorded session ID.
- A `completed` or `completed_with_warnings` job status.
- Exactly one `params.json` output entry of kind `params`, with its exact
  byte count and SHA-256 matching the saved parameter file.
- A `paramsDigest` matching the producer's canonical JSON encoding: sorted
  keys, compact separators and escaped non-ASCII characters.
- For a comparison, the same resolved parent directory and recorded session
  identity in both jobs. The dialog also rejects choosing the loaded job itself.

The provenance panes distinguish the verified recorded `paramsDigest` from
newly computed SHA-256 values for the two actual saved files. They also label
the analysis version and capture-manifest digest as **recorded** values.
The viewer does not reopen raw capture data or verify every output artifact.
Historical manifests may include a self-entry whose digest describes an older
serialization; that entry is not treated as a verification of the current
manifest. Current manifests which omit that self-entry are supported.

Copies returned through the helper API are fresh decoded views; mutating a
returned dictionary does not alter the retained input bytes or another view.

## Changed or invalid saved jobs

The dialog rechecks the exact directory identity and saved metadata bytes when
opened, before and after comparison, and during explicit reload. If the loaded
source changes, it clears the displayed parameters and comparison, disables
comparison, and asks the reviewer to reload. If only a selected comparison is
invalid, it clears that comparison and preserves the valid loaded parameters.
After the files are repaired or restored, **Reload saved parameters** can
recover the view.

This is a read-only snapshot at those action boundaries. It is not a live file
watcher or a filesystem transaction. An already displayed snapshot remains a
snapshot until the next action or reload.

The native inspector retains ordinary metadata and output labels for valid
failed jobs even when they have no saved parameter file or `paramsDigest`.
Their parameter button is disabled. Malformed manifest roots, invalid output
rows, invalid UTF-8, unsupported job identity and symbolic-link manifests
produce a visible refusal instead of escaping from the Qt load callback.

Reads are bounded to 4 MiB per metadata file. Parameter trees are limited to
10,000 nodes and depth 48, with the root at depth zero. A comparison is limited
to 5,000 differences; exceeding that limit refuses the whole comparison rather
than presenting a partial list. Duplicate JSON keys, non-finite numbers,
malformed JSON, linked job directories, symbolic-link files and non-regular
inputs are refused. A refusal leaves the source files unchanged.

## Implementation and receiving

`analysis_job_comparison.py` owns bounded reads, immutable input snapshots,
provenance admission and typed differences. `widgets_analysis_comparison.py`
provides the native PySide6 dialog and its Job inspector action bar.
`JobInspector` retains its public `clear()` / `load_job_dir(Path)` lifecycle.
The same module's figure gallery and sync dashboard are unchanged by this
feature, and the backend, schemas and job writer remain separately owned.

`tests/ui/test_analysis_job_comparison.py` includes malformed and stale inputs,
typed differences, source preservation, failed-job metadata, native keyboard
and clear/reload behavior, and a real QC producer pair made from the bundled
synthetic mini-session. That fixture is not a physical measurement. The added
`extra` fields in the pair exercise saved-document comparison; they do not
claim that the QC implementation consumes those example fields.

Source pins, original failures, author results, independent receiving and
rendered native views are retained in
[the receiving evidence](../../evidence/job-parameter-comparison-ac386303dce2/README.md).
Hosted Windows receiving and installed-application adoption are separate from
local source and Qt qualification.
