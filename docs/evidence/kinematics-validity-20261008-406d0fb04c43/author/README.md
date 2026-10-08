# Kinematics landmark-validity receiving

Issue: https://github.com/Jacob-Met/CaptureSuite/issues/56  
Author: estate-406d0fb04c43 / production

## Product result

An incomplete non-simulated pose table previously selected synthetic fixture
angles when the table lacked required body landmarks. The ordinary kinematics
CLI could complete and publish invented values as valid, retaining the original
non-simulated model ID. A missing or low-confidence joint also invalidated
unrelated usable joints, and derived velocity/range values could be finite at
a frame whose angle was missing.

The correction is confined to kinematics/compute.py. It selects fixture
equations only for explicit sim_ model IDs, evaluates each required landmark's
finite coordinates and confidence, and determines elbow/shoulder validity
independently on each side. Missing or undefined angle groups and their velocity
or AFR values at the missing frame remain NaN. Existing complete-input math,
explicit simulation behavior, model identity, column schema and publication
code are retained.

The model name mediapipe_body_fixture in this test is an explicit fixture label
for the existing MediaPipe-index geometry contract. Its coordinates are known
synthetic test inputs. No model inference, device capture, physical-accuracy,
calibration, smoothing or IMU-fusion result is claimed.

## Frozen source

- Public baseline: 72c15d6b623e217291a824e4e4808a385df896a9.
- Public baseline tree: 221cf5c7bb3c3392a7c4186ba0bcf5a8664135d1.
- Verified baseline projection: 134 runtime, schema, fixture, test and policy files.
- Local projection parent: 7815b418a7fdc1658d15f48e6099855165430711.
- Local candidate projection: 2a42301a65cb0c44b67950f515b8e9291c4f3816.
- Local candidate tree: 4c30b85ea56edb0fa495f161c79bbbf8ec50bed1.

The local projection is intentionally smaller than the full production repository.
It contains all analysis/session/protocol Python runtime, shipped generated
protobuf bindings, required schemas, original pose/kinematics consumers and the
existing CLI. It is not a daemon or complete Windows build.

candidate-source-manifest.json names exactly four authored files: the computation,
one new test, the kinematics contract note, and the additive progress entry.
Every other selected runtime file matches the public baseline. The final two
documentation additions were frozen after execution; the tested computation and
new test are byte-identical to the final candidate.

## Native experiment

Native macOS arm64, Python 3.12.8, using the existing published-provenance science
environment read-only. No packages were installed or environments modified.
environment.json records the exact installed versions.

| Frozen test scope | Original source | Candidate |
|---|---:|---:|
| Thirteen new missing-data/validity methods | 11 failed, 2 passed | 13 passed |
| Eight original pose/kinematics/ML consumers | Not repeated | 8 passed |
| Total candidate invocation | — | 21 passed, 0 skipped |
| Scoped repository Ruff | — | Passed |
| Existing environment dependency consistency | — | Passed |

The same new test bytes are used for both sides:
f269c16f24883599e3972936f0a1e04868bf0939fbcbe1d178475eb0f197ad31.

The fixture uses the unchanged tests/analysis/test_pose_job.py helper, real MCAP
writer and shipped protobuf messages, then seeds a real pose Parquet table and
model card. The actual tools/run_analysis.py subprocess must succeed; the test
reads its persisted kinematics Parquet and QC, checks the model identity, exact
timestamps, invalid flags, missing numeric labels and zero detection rates, and
compares every pre-existing package and input-pose byte.

Other methods exercise missing hips, one-frame wrist dropout, NaN/infinite
coordinates or confidence, low required-joint confidence, degenerate geometry,
unrelated low-confidence landmarks and a custom confidence threshold. Complete
geometry and explicit simulation are passing original controls. Parent receiving
adds independent real-Parquet CLI and exact complete/sim byte comparisons.

Both runs retain two existing protobuf deprecation warnings. No test is skipped
or reported as passing solely from progress output: the process return status,
JUnit, raw stdout/stderr and before/after source digests are retained.

## Replay

From a full repository with the declared Python 3.12 analysis dependencies:

```sh
python -m pytest -q tests/analysis/test_kinematics_validity.py tests/analysis/test_pose_job.py tests/analysis/test_kinematics_ml_bundle.py
python -m ruff check libs/python/capture_analysis/capture_analysis/kinematics/compute.py tests/analysis/test_kinematics_validity.py
```

For the original negative control, use the exact public baseline computation with
the unchanged new test. The baseline runtime archive and source manifest preserve
the selected original inputs. Raw test-created packages and all actual output
files are retained in test-artifacts.tar.gz with an individual SHA-256 manifest.

The unmodified project policy and existing supported Windows CI remain the final
platform gate. This author packet establishes source-bound native computation
and CLI behavior; independent receiving and integration are recorded separately.

## Execution custody

The shared workspace reached zero free bytes during source assembly; a 70 KB
intermediate write failed before any product execution. Only this lane's
sub-megabyte staging moved to its own temporary memory directory. All files were
reconstructed from matching cached Git blobs or exact GitHub GET results and
verified before native execution. No other owner's files were changed or removed.

After all candidate tests passed, the native machine briefly could not create a
shell heredoc for an environment-report command. The preceding pip check had
succeeded. No product test or source write was involved in that failure. The
environment report and final static receipt were subsequently captured by direct
child-process invocation. Original product failures and successful receipts were
kept throughout; no acceptance assertions were relaxed.
