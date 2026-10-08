# Independent ML-bundle receiving — 03ac6e86ba72

Independent receiver: `estate-03ac6e86ba72/mac_production`, under the standing HAMON execution mandate. Scope was announced in [CaptureSuite #72](https://github.com/Jacob-Met/CaptureSuite/issues/72#issuecomment-6063382174). The implementation and final integration remain with `estate-713adaab`.

## Result

**Accepted within the exercised native CLI and retained-Parquet boundary.** All twelve public CLI invocations exit 0. The identical receiver reports original **48 passed / 15 failed**, candidate **63 passed / 0 failed**, and paired preservation **8 passed / 0 failed**.

The fifteen original failures are five metadata expectations repeated over three fixtures; they are not fifteen independent numeric defects. Original numeric outputs and consumer controls pass. The corrected producer describes the existing values and timing truthfully without changing the emitted window tables or downstream predictions.

| Source | Exact identity |
| --- | --- |
| Original canonical commit | `70f34e3b982523b544a9370d2316a1b69d79bd70` |
| Frozen authored candidate | `f151a1d85a9c9e09c7708701c4a1faadfe0ad777` |
| Original producer SHA-256 | `c14c74760e20c818ce5e2428d0b03a8a949899b0bba6c46e37fa8fd797631c75` |
| Candidate producer SHA-256 | `38b7161f081ef038e6ce464dd3b82ca2b49f775ad8988010243743274d6fc5e6` |
| Independent receipt SHA-256 | `5258916e4e7a6d9e656df0817bbfc9013eac16c7c9b32660f4945f40bf9e3525` |

Only the producer differs across the 201 pinned runtime/schema/tool files. All 201 files per side remain unchanged after execution. Each CLI invocation records 41 actually imported project modules and their hashes. The unchanged `tools/run_analysis.py` executes through a small `runpy` wrapper that records imported source paths after exit; it does not replace producer, parser, job, evaluator or persistence behavior.

## Independent cases

| Input | Independently specified observations |
| --- | --- |
| Irregular nonlinear target values with nearest-feature ties | Centers at 200, 450 and 700 million ns; raw energies 500, 500 and 1300; target medians 25, 50.5 and 50; angular-velocity medians 2, 2.5 and 21; validity true, false, false. |
| One exactly fitting window and numeric-column feature fallback | An odd requested nanosecond width admits one regular center at 200 million ns. A tie selects the right feature row; its two-column mean is 200. This is `regular_hop`, despite there being only one output row. |
| Short, uneven, even-length teacher series | The fallback center is 45 million ns. Its nearest-feature tie selects raw energy 84, with target median 40 and velocity median 4. It reports `median_fallback`, with configured rate separated from an observed cadence. |

All requests deliberately use a separate rate that differs from the configured integer hop. Quantized hop/window inputs are retained in `params.json`; the bundle records original requests and effective integer timing. Final bundle files pass the existing JSON schema.

The receiver runs the maintained identity evaluator on every result, preserving all four angle/velocity target columns and valid-window counts. All three original/candidate `windows.parquet` pairs and all three `predictions.parquet` pairs are byte-identical. Every seeded input remains unchanged. The enclosing bundle job inventory matches the physical final bytes.

All six bundle jobs report `completed_with_warnings` with the same retained fixture-duration warning: the intentionally small package has no integrity entry carrying `endSessionTimeNs`. The warning is recorded in every observed result. No schema warning is accepted, and no strict-warning or scientific-performance success is claimed.

## Packet and reproducibility

- [receiving-03ac6e86ba72.tar.gz](receiving-03ac6e86ba72.tar.gz): **110,825 bytes**, SHA-256 `e87637dc0496fa23655263b7b0c214c33c095e00f883b8c0f70974ba420f4372`.
- [manifest.json](manifest.json): all **183** regular members, **608,797** expanded bytes, with byte counts, SHA-256 and modes.
- The archive contains the exact receiver and CLI tracer, seeded Parquet inputs, actual original/candidate job outputs, logs, module manifests, before/after source hashes, frozen producer files and production patch.
- Native workspace: `/Users/me/Developer/capturesuite-ml-metadata-independent-03ac6e86ba72`.
- Existing macOS arm64 Python **3.12.8**, NumPy **2.5.3**, pandas **3.0.6**, PyArrow **25.0.1** were used without installing dependencies.

Both sparse clones preserve genuine source ancestry and use the original repository's objects read-only. This evidence branch adds only this unique evidence directory to canonical source; it does not adopt the authored producer change.

The first archive readback failed because macOS tar inserted AppleDouble members absent from the evidence directory. That original archive remains retained on the Mac and its hash, member names and failure are recorded in `packaging-preparation.json`. The corrected archive uses explicit regular files, and every accepted member was reopened and matched to its original bytes. No source, input, output, assertion or CLI run changed during packaging.

This is native producer/consumer receiving on authored analysis Parquet fixtures. It does not qualify raw acquisition, feature extraction, kinematics estimation, external model evaluation, Windows, GUI, hardware, training or deployment. The pre-existing internal submanifest self-digest convention remains outside this correction; the enclosing final job inventory was checked.
