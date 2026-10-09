# Prepare an external prediction template

A selected ML bundle already defines the windows and target names required by
the external evaluator. This command creates the matching editable JSON file,
including the exact final-file hashes. It does not run a model.

```powershell
python tools/prepare_predictions.py "D:\\captures\\trial.mmsession" --bundle-job bundle-01 --model-id "my-model-run-17" --output "D:\\predictions\\trial.json"
```

The destination must be a new file in an existing directory outside the selected
package. Existing files, directories and links are refused, including a file
created by another writer during validation.

The result uses the unchanged `capture.eval_predictions/1` schema. Every bundle
window appears in its existing order, including invalid windows. Window IDs,
signed integer nanosecond timestamps and target names retain their exact
identity. The caller's admitted model label retains its original spaces and
Unicode characters; it is not authenticated model identity.

Every target value starts as JSON `null`, which means unavailable. Replace those
nulls with the predictions for each window. Leave genuinely unavailable values
null. Do not copy teacher values into the file and call them model predictions.
Keep every window, timestamp and target key, and retain both source hashes.

Then run the existing evaluator or select the same file in Analysis:

```powershell
python tools/run_analysis.py eval "D:\\captures\\trial.mmsession" --ml-bundle-job bundle-01 --predictions "D:\\predictions\\trial.json"
```

The evaluator can admit an unchanged all-null template structurally, but it has
zero usable prediction pairs. Its metrics remain unavailable; that result does
not indicate that a model ran or achieved accuracy. See
[external prediction evaluation](ANALYSIS.md#decision-2026-10-08-evaluate-externally-supplied-predictions).

## Source and publication behavior

The template hashes the complete selected `windows.parquet` and final
`manifest.json` bytes. It does not copy the bundle's historical embedded
manifest preimage digest. The selected package's maintained review reader
supplies the expected session identity independently of the bundle manifest.

The existing evaluator's input admission checks the staged template, selected
bundle and registry. Its source reread must agree with the hashes used in the
template. Malformed or changed inputs are refused before the final file is
published. The producer, evaluator, schemas, scoring and job APIs are unchanged.

The existing 64 MiB limit applies separately to each consumed source file and
the authored prediction JSON. It is not a bound on decompressed Parquet memory
or total process resources. Same source bytes and exact model label produce the
same template bytes, with no wall-clock metadata or extra sidecar.

A new private temporary file is fully written and closed in the destination
directory before admission and publication. Exclusive hard-link publication
never replaces a destination. Filesystems that do not support this operation
produce an error; there is no overwrite fallback. Only this attempt's temporary
file is cleaned up. If cleanup fails after publication, the error explicitly
states that the final file was published. The final file retains the temporary
file's private creation permissions. This is not a whole-package transaction,
a guarantee against concurrent parent-directory replacement, or a power-loss
durability guarantee.
