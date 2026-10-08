# Windows checkpoint-selection compatibility

The failed Windows Python job is a maintained numeric-test selection that still assumes a checkpoint opens the following section. It is a direct composition consequence of the corrected closing-section contract, not a Windows, Qt, dependency or numeric-handler failure.

The exact maintained fixture has trial at 5.08 seconds and rest at 6.6 seconds. The public job test selected trial while preserving expected numeric values for the interval between those markers. With the corrected resolver, trial closes [0, 5.08], retaining two numeric samples. The unchanged numeric extractor requires ten samples for its one-second window at 10 Hz and therefore emits no feature table. This matches the actual failed job manifest.

The adaptation changes only that test's selector from trial to rest and adds one closing-marker comment. Rest closes [5.08, 6.6], the same ten samples the existing assertions describe. Every bound, mean, RMS, schema, provisional/calibrated flag and raw/output hash assertion remains unchanged. No production source or additional test is changed, and no local/hosted test is rerun by this receiver.

## Exact failed receiving

- Repository: Jacob-Met/CaptureSuite; PR #68 head fef2d0307645de3e3a67592e2778bd560b9dfa69.
- Base: d43bdea867d6198a707a5f55e29216c76054517e.
- Hosted run 37792726943, attempt 1; Windows python job 113364093148.
- Actual checkout: synthetic merge 171d2f90b83484151c4283542ee3cd71a1beebc4, with the two commits above as parents. Its tree 73b206a257de681295e5669a929c3d61652208f9 equals the published head tree.
- Result: 1 failed, 429 passed, 6 skipped, 2 nonfatal protobuf deprecation warnings. The skipped cases are the Python job's six unbuilt-daemon cases. CMake was still configuring when this receipt was collected.
- Sole failure: NumericReceiving.test_public_checkpoint_job_exports_exact_native_bounds_math_and_metadata, at tests/analysis/test_numeric_receiving.py:171, zero feature tables versus one expected.
- The maintained test is byte-identical at base and head, blob cee5571f3802a2ca452f4591afc2fd4c86c6beba.

job-113364093148.log preserves the complete 60307-character decoded log returned by the purpose-built GitHub job-log tool, including its original line endings. failed-manifest.json is parsed from the preserved assertion text; its original representation remains in the log. Source copies, checkout metadata, workflow steps, artifact metadata, patch and hashes are retained alongside it.

The purpose-built artifact-download tool returned a reusable ZIP reference. Direct transfer of its still-valid signed URI to the isolated native Mac returned HTTP403. That failure and public artifact ID/digest are retained; no ZIP bytes are claimed in native custody and no alternative account or endpoint was attempted. The decoded job log and source evidence are independently sufficient for this narrow attribution.

Root owns application of the exact test delta to the complete feature tree and the hosted CI rerun. This packet does not claim the adapted test or the whole PR has passed a subsequent run.
