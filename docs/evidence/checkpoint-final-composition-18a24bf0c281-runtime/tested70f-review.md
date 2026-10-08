# CaptureSuite PR68: tested current-parent composition review

## Decision

The exact synthetic merge `427766ed4beee603ea2e3eadcaceee9f7f76a538` is accepted for the bounded source-composition and hosted CI review described here. Its first parent is `70f34e3b982523b544a9370d2316a1b69d79bd70`; its second parent is the unchanged PR68 head `cd1a2c4ba00f722e69c9e1bc992850bed8a5385d`.

This receipt covers that tested parent only. Any later main advance requires its own static delta assessment. The receipt does not authorize or claim a merge, deployment, recording, hardware acquisition, or installed desktop operation.

## Exact source identities

| Role | Commit | Git tree | Leaves |
| --- | --- | --- | ---: |
| Earlier reviewed main | d43bdea867d6198a707a5f55e29216c76054517e | fea0e03773742d330963b89e0ceb72a22c7ad495 | 892 |
| Tested current main | 70f34e3b982523b544a9370d2316a1b69d79bd70 | 1537621f793d5d5c9b331f3c4d37a79a4af824b7 | 919 |
| PR68 feature head | cd1a2c4ba00f722e69c9e1bc992850bed8a5385d | 020ce927f40be01cb3dd4d27b03f864182e26cb5 | 977 |
| Actual hosted checkout | 427766ed4beee603ea2e3eadcaceee9f7f76a538 | 53a055761cd91359819445f392efc71da8e9099a | 1004 |

All four complete recursive Git trees were retrieved with `truncated: false`. The verifier reconstructs every listed tree object from its immediate entries and checks its Git SHA, including modes and Git link identities. It then compares every file/Git link leaf.

The feature changes 91 leaves relative to the earlier reviewed main. The tested merge retains **89 exactly**; the only composed feature files are the two shared documents below. All **913 unrelated current-main leaves** are retained exactly. There are no feature deletions, unexpected merged paths, or unaccounted mode changes. The full per-path comparison is in `proof/tree-retention.json`.

## Documentation composition

The verifier reads byte-verified copies of all four revisions of both documents. The feature delta is one pure insertion in each file, with no removals:

| Document | Feature insertion | Exact bytes |
| --- | ---: | ---: |
| docs/design/ANALYSIS.md | 55 lines | 3,069 |
| docs/design/research/PROGRESS.md | 33 lines | 2,118 |

Each insertion occurs exactly once in both the feature and tested merge. Removing its exact bytes from the feature reproduces the earlier reviewed main byte for byte. Removing the same bytes from the tested merge reproduces the corresponding 70f file byte for byte. `proof/documentation-subtraction.json` binds the four Git blobs and both retained insertion files.

## Review of d43 to 70f

The parent advance contains eight commits and 32 changed leaves: 27 additions and five modifications. Source scope was inspected from the exact Git blobs and complete compare patches; no product code was edited.

The successful job finalization change in `libs/python/capture_analysis/capture_analysis/jobs.py` (blob `70a27b677384dac61cb25bea86f80632c1bf328e`) removes the premature manifest write and its impossible self-checksum inventory entry. It finalizes `logs/job.log` before serializing the manifest that refers to the same outputs list. Window resolution, pipeline dispatch, calculations, stored window inputs, failure cleanup and the existing replacement/publication boundary are unchanged. This makes the persisted successful inventory include the final log without changing checkpoint resolution.

The new figure exporter `desktop/capture_desktop/analysis_figure_export.py` (blob `3c7b5c2be3639b6086551eb8d2dda18aa1507b44`) consumes a completed job's saved manifest, parameters and recorded PNG outputs. It accepts the manifest through its fixed filename, so it does not depend on a manifest self-inventory entry. It validates original metadata and figure bytes, writes the exact selected PNG and saved metadata bytes into a separate ZIP, and refuses a destination within the source session/job. It neither resolves a checkpoint window nor reruns analysis.

The UI workflow `desktop/capture_desktop/widgets_figure_export.py` (blob `de619492f9b360608c58ecd04002def52be5f7a0`) invokes that saved-artifact export in its worker. The gallery change in `widgets_analysis_plots.py` (blob `2d6cbf65e20a9ec813254f380b51cebe203647b4`) adds five hook lines: import, construction/layout, clear, and completed-job load. It retains existing plot rendering and invalidates the previous export source when the gallery changes. No checkpoint resolver or feature calculation is introduced through these hooks.

The peer test change in `tests/analysis/test_numeric_cli_receiving.py` (blob `0dabc2786a771903322e240039522c0bbdea8f9a`) makes the historical self-entry diagnostic optional and records the physical manifest digest externally. It preserves the surrounding receiving assertions. This is a different file from PR68's unchanged final selector adaptation in `tests/analysis/test_numeric_receiving.py` (blob `d2d80dca85375acd58c4970e0c9490ee662c75f9`).

The checkpoint resolver remains exact blob `aaafd8db78f82a5a56178135dbed5bfd4f45c634`; checkpoint tests remain `7dfc0ad216f9b4ed512ee3b33c3b65ba44895727`; desktop scope tests remain `2ee653a05e27e8586e74439d2bdc9eccf06505ef`. All historical author and independent negative evidence remains byte-identical in the tested tree.

## Hosted CI, run 37796872973

Both final Windows jobs report `completed / success`, with every reported step successful, on the same actual checkout 427766ed. The complete decoded logs are preserved with their initial BOM and CRLF sequences; their UTF-8 hashes are recorded below. This is custody of the connector's complete decoded job text, not a claim of raw HTTP transport bytes or artifact ZIP retrieval.

| Job | Observed result | Decoded UTF-8 bytes | SHA-256 |
| --- | --- | ---: | --- |
| Python 113378503488 | 477 passed, 6 skipped, 2 warnings | 54,108 | c261886ab5574f5270d6fc4fdc08f98b059d537050027fd1fb2c888800f78d9c |
| CMake 113378503111 | 30/30 CTest; 6 native integration passed, 2 warnings | 312,298 | 02ea8b52c39f783a55eed68caf9b2b07e73aea9eb6c105b99346638837124282 |

The CMake job configured the Windows release preset with `CAPTURE_WERROR=ON`, built `capture_daemon`, `capture_core_tests` and `session_doctor`, ran CTest with `--no-tests=error`, and ran `tools/run_native_ci_tests.py`. The Python job ran `tools/run_ci_tests.py` after the dependency, schema/protobuf drift, Ruff and license checks. Exact commands, timestamped summaries, logged checkout lines and job steps are in `proof/ci-receipt.json`.

Ordinary configure capability probes and warning text remain in the full CMake log; success is taken from the final job/step conclusions and executed test summaries. No failing final job or command is being waived. No extra CI run was dispatched. The full Python aggregate is not represented as individually named Qt-case evidence beyond what the retained log reports.

- Python job: https://github.com/Jacob-Met/CaptureSuite/actions/runs/37796872973/job/113378503488
- CMake job: https://github.com/Jacob-Met/CaptureSuite/actions/runs/37796872973/job/113378503111

## Metadata and historical limits

The observed PR response still lists d43 in `base.sha`, while its merge commit and the independently retrieved synthetic commit identify the actual 70f + cd1 parents. This review uses the actual commit object and logged checkout, preserving the PR response without rewriting it.

The PR body also retains an older statement that the manifest self-entry limitation remains. That statement describes the preserved earlier receiving evidence; the tested current parent has since repaired successful manifest/log finalization. The old red artifacts remain valid historical evidence and were not replaced or rerun.

## Reproduction and custody

Run `/usr/bin/python3 verify_review.py` in this evidence directory to reproduce only the static tree, source-byte, document-subtraction and log-binding checks. It reads the retained intake and writes proof receipts; it does not build or execute CaptureSuite or contact GitHub.

The isolated Mac workspace is evidence custody and static verification only. Windows test execution occurred on the hosted runner. All changes in this directory are review artifacts; no production file, PR head or shared repository was modified.
