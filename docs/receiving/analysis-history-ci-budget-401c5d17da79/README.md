# Analysis history: hosted CI time allowance

The full Windows Python suite reached its existing 300-second subprocess limit twice while reviewing PR71. The retained attempts used actual proposed merge `0de94b767061ec1fe5c05d11c6baa36ec9ddf16b`, a clean unchanged source tree, and no final JUnit. Neither timeout is classified as a passing product run.

- Original job: https://github.com/Jacob-Met/CaptureSuite/actions/runs/37811934426/job/113430721070
- One unchanged-job retry: https://github.com/Jacob-Met/CaptureSuite/actions/runs/37811934426/job/113459881579

A temporary autouse fixture then recorded entry/exit around each of this PR's eight unchanged history tests. On actual proposed merge `f17f811366bc9915e0f001b42d9df86afc353213`, every history test passed in 0.073–0.158 seconds; their displayed timings sum to 0.834 seconds. The full suite passed 555 with 6 daemon-availability skips in 295.60 seconds (296.7734097 seconds including wrapper evidence processing). This left about 4.4 seconds before the existing child-process deadline. This one observation establishes little timing margin; it is not a claim about every runner's speed.

Diagnostic job: https://github.com/Jacob-Met/CaptureSuite/actions/runs/37826104818/job/113479261945

## Source change

Restore `tests/ui/test_analysis_history.py` exactly to its pre-diagnostic blob `f013473f750b515a8305e2f7f8426b6520e26a65`. Change only the Python suite subprocess allowance in `tools/run_ci_tests.py` from 300 to 600 seconds. The existing 20-minute Windows job limit remains, as do all process-exit/JUnit/source-immutability acceptance predicates and the suite's existing test selection. No test is removed, skipped or weakened. The existing runner file is byte-identical in the PR source and inspected canonical main before this single-literal change.

All product source is unchanged by this correction. The previous native history qualifications retain their recorded inputs. The new source head still requires its own hosted gate; this record does not convert either prior timeout into success.

## Preserved evidence

The three complete hosted logs are adjacent to this file, along with the actual diagnostic receipt. The source owner is `estate-401c5d17da79`, working in PR71. The prepared source and raw logs are also retained under the ThinkPad estate `capturesuite-ci-a2fd-20261008` packet. The transient diagnostic-only source remains in parent commit `8747cb95bfb2ac91aa4f1ff604ad677f3597fa12`.
