# Independent receiving: completed checkpoint sections stay isolated from later work

## Decision and beneficiary

**Accept the frozen checkpoint resolver for this offline saved-package boundary.**
A researcher selecting the phase closed by checkpoint B receives that completed
phase's feature table. Editing a later checkpoint or later samples no longer
changes its analysis, while changing a sample inside the completed phase does.

This is an independent receiver of estate_product's source. It adds no production
changes and does not replace the author's 30-case API/CLI suite.

## Exact source and environment

| Item | Pin |
| --- | --- |
| Public baseline | Jacob-Met/CaptureSuite `72c15d6b623e217291a824e4e4808a385df896a9` |
| Public baseline tree | `221cf5c7bb3c3392a7c4186ba0bcf5a8664135d1` |
| Owner candidate | `4fcd0aa4319b6594af637af8644c187fcbff3cf5` |
| Only overlaid production path | `libs/python/capture_analysis/capture_analysis/windows.py` |
| Candidate Git blob | `aaafd8db78f82a5a56178135dbed5bfd4f45c634` |
| Candidate SHA-256 | `5cf401b7b7d201225c966b804cfff39c3f6d59669da7e488dd68c4253a829c32` |
| Canonical reviewer baseline commit | `53efcc586f903472a55b9bd07818ec0a3a9f6c64` |
| Corrected receiver freeze | `251a69414a9f406d0689e7ce0305c9aeee396a5c` |
| Receiver SHA-256 | `0779ae505ae3b784177960504185f0276215c4b853969a222316167f142f08d2` |
| Decisive baseline receipt commit | `1efa5f5162358d4c4915ece2db7394c06a2e40d1` |
| Reviewer candidate composition | `e188fabb2e82ef353206768baa429c8aecab7731` |

The isolated Mac fixture uses its own CPython 3.12.8 virtual environment. It has no
editable links to the owner's source or environment. The dependency pins, actual
installed freeze, installation output and pip check are retained. Both source
compositions contain exactly 668 upstream paths; the candidate changes only the
one reviewed resolver blob and preserves the other 667 files. No owner test or
new support module was substituted into the runtime composition.

Every run verifies all 668 source files before and after execution. Each
interpreter records 45 loaded application modules with paths, SHA-256 and Git
blob IDs; packaging verifies each against the appropriate full source manifest.
The native raw evidence contains the exact process command, result and all input
and output files.

## Receiver and results

One metamorphic receiving method creates four saved `.mmsession` packages, each
with 721 real protobuf IMU frames at 60 Hz from 0 through 12 seconds. The saved
checkpoint file contains A at 2 seconds, selected B at 6 seconds, and C at
9 seconds. The interval named by B is the inclusive interval [2 s, 6 s], according
to `docs/design/SESSION_FORMAT.md`'s captured-checkpoint contract.

The receiver calls the actual package reader and public
`capture_analysis.run(package, JobParams(command="features",
checkpoint_section="B", overwrite_job_id="section-B"))` on a fresh package.
The production MCAP loader, plugin registry, numerical feature code and
CSV/Parquet writer execute without mocks. Each package gets a new job directory;
there is no replacement or cleanup of an existing job.

| Package variation | Original source | Candidate |
| --- | --- | --- |
| Reference | Resolves [6 s, 9 s], emits 29 rows | Resolves [2 s, 6 s], emits 39 rows |
| Move only later C from 9 s to 12 s | Changes the selected window to [6 s, 12 s] and emits 59 rows | Window and complete feature table stay identical to reference |
| Change only raw samples strictly after 6 s | Changes the selected feature table | Complete feature table stays identical to reference |
| Change only the sample at 4 s | Leaves the selected feature table unchanged | Changes feature values while preserving the selected window and feature timestamps |

The identical corrected receiver has **26 checks within this one four-package
method**. The original source passes 19 and fails 7: four observed-interval
checks, both future-invariance relations, and the inside-section sensitivity
control. The candidate passes all 26. These are not 26 independent test methods.

All valid-run jobs complete without warnings or errors. Each CSV agrees with its
actual Parquet table. The candidate's reference, future-marker and future-data
CSV bytes share SHA-256
`b858bafe27fa54841d68952020c13168f6b042c2192c81cd2f4c78e92081cff6`.
The inside-section edit produces
`3c72f90f1d55259249d44674b4f485ed4eb83652eb4a77edd863cd035ebbce2c`.
The receiver checks fixture isolation by serialized message hashes: only indices
361–720 change for the future-data variant; only index 240 changes for the
inside-data variant. All eight raw package files remain byte-identical before
and after every analysis, including the checkpoints and original MCAP.

## Preserved reviewer setup failures

The original v1 receiver used the unrecognized fixture keys
`originalSessionTimeNs` and `effectiveSessionTimeNs`. The canonical persisted
protocol uses `originalTimestampNs` and `effectiveTimestampNs`. The reader kept
the unknown keys and the existing resolver defaulted every marker to zero.
The receiver's interval and sensitivity checks rejected that fixture. Its
original driver, raw packages, outputs and receipt are retained as a **reviewer
fixture error**, excluded from the product red/green claim.

Only those two dictionary keys were corrected before candidate intake. The
assertions, input timing/data, expected interval and production source were
unchanged. The fixed driver was frozen and rerun on the original source first.

Source intake also retained two representation diagnostics before any product
test: eight Windows scripts in the transfer archive had prescribed CRLF checkout
bytes, and two historical upstream raw evidence logs were normalized by Git's
inherited text rules. The reviewer reconstructed the eight scripts only when
that produced their exact known upstream blob, preserved the two raw logs using
a targeted reviewer Git `info/attributes` serialization exemption, and verified
all 668 canonical disk and indexed blobs. The first normal add reused stat
entries; the retained follow-on applies the targeted index refresh. No scripts,
hooks, production data or owner source were executed or changed by this intake.

## Reproduction and evidence map

Materialize the exact baseline Git blobs listed in
`baseline-source-manifest.json`; the byte checker intentionally rejects checkout
line-ending changes. For the candidate, retain the same paths and substitute
only the resolver blob listed in `candidate-source-manifest.json`.

Use a private Python 3.12.8 environment with `dependency-pins.txt`, clear
`PYTHONPATH` and `PYTHONHOME`, and choose private cache/output paths. Then run the
same receiver in a fresh interpreter per source:

```sh
python -B receive_closed_section_isolation.py \
  --source /absolute/path/to/canonical/source \
  --manifest /absolute/path/to/source-manifest.json \
  --output /absolute/path/to/new-owned-output \
  --label baseline-or-candidate
```

The exact native commands and environment values are inside each archived
`process-receipt.json`. Each output path must be new. The baseline deliberately
exits 1 on the semantic counterexamples; the candidate exits 0.

`raw-receiving-evidence.tar.xz` preserves all three runs, including the rejected
v1 fixture. `raw-receiving-manifest.json` lists and hashes every archive member.
Archive bytes are lossless; packaging rereads every member and checks it against
both the native original and the manifest. `qualification.json` provides the
compact result/source binding. `publication-path-map.json` identifies each
published evidence path and its native original.

## Scope of acceptance

This qualifies the actual offline persisted-package analysis boundary with
controlled synthetic IMU data. It does not claim hardware timing fidelity,
scientific validity of feature formulas, native scope-picker rendering, or a
live capture/daemon run. The separate owner suite covers aliases, first/last
sections, zero/ties, signed invalid bounds, full/custom modes and CLI output.
No repeat of that suite was needed for this distinct receiving challenge.
