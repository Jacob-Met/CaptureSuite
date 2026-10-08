# Sync-anchor request admission — source and receiving record

**Latest receiving:** see [Current finalizer composition](#current-finalizer-composition--latest-qualification)
for the actual PR46 finalizer parent and current gates. Earlier sections retain
the original observation and qualification history.

Owner: **chatgpt-astra-bd1abdb2f886-20261008 / estate_mac**.
[Scope #63](https://github.com/Jacob-Met/CaptureSuite/issues/63) ·
[shared job-runner coordination](https://github.com/Jacob-Met/CaptureSuite/pull/46#issuecomment-6061195797).

## Result and boundary

The current job API cannot apply synchronization-anchor offsets. Previously,
`JobParams.apply_sync_anchors=True` was accepted and copied directly into the
saved manifest's `syncAnchorsApplied.applied` flag. The production pipeline and
grid helper do not receive or implement that request.

The correction explicitly rejects the unsupported request with
`NotImplementedError` at job admission, before progress callbacks, review/QC
reads, output creation or replacement of a saved result. It tells the caller to
use `apply_sync_anchors=False` to run without anchor alignment. The ordinary
false/default request keeps its existing behavior. Successful current jobs record
`{"applied": false, "anchors": []}`; recorded anchors remain available to package
review and QC.

This is a correction to admission and reported provenance. It does not implement
measured offset estimation or qualify feature timestamp alignment. No invented
offset or implicit fallback is introduced.

## Exact source

The initial real-job observation uses main
**284d168d7614e2465bafba1092d8cbe4b6e13b40**. The candidate receives current main
**3e3ecc5ecc1cfc79c79901eb5cffe10b0ec5852e**, tree
**18e97093f04de23de5e9878fd22c1f5ed986d5f3**, after desktop time-scope integration.
All 97 original production/schema/fixture inputs used by the observation are
byte-identical in that parent.

| Qualified payload | Git blob | SHA-256 |
| --- | --- | --- |
| `libs/python/capture_analysis/capture_analysis/jobs.py` | `3cd908898e8f56b2fa4269843c275abdf6dfc8e0` | `ab4eecbb3e17c71c6171579625c29a2474fc467e07070fb63dd3513bf6bb865f` |
| `tests/analysis/test_sync_anchor_request.py` | `ead08b6cd74455115fa1e9f2e83e9ea4a72dcd18` | `80dd9c2b3210f8198a49ba893b49b330edf345e29cc30d4f9613299db271ca30` |
| `docs/design/research/ANALYSIS_SCOPE_SEMANTICS.md` | `4f466a37459ec77154ec63bd43acc722574e47c6` | `56a332297e39d41f3a619c20c487af4d8c0a1a8d3f7bdb06a024505c8c6c1475` |

The original runner is blob `7badee5cdf5a4b30a283e0dcbb2c5d85fb787489`.
Its only production changes are the early unsupported-request refusal and the
successful manifest's literal false flag. Existing missing-package and
unknown-command admission remain in their original order. The complete
destination, cancellation, callback, output-inventory, replacement and failure
paths are preserved. PR46 retains its independent finalization correction.

The documentation adds only a current-availability note to the intended future
alignment contract. Removing that note restores current-parent scope document
`2814d8e3d13c934846b84bb1dfbb1f9bb5cb50d1` exactly, including the newly landed
desktop time-picker text. The required PROGRESS entry and this receiving record
are additional documentation; they do not change the qualified runtime source.

## Real original observation

The receiver seats the exact production packages and runs `jobs.run` directly
on two separate copies of the bundled synthetic mini-session. Each copy contains
one recorded anchor, `synthetic-tap-250ms`, with native timestamp
**250,000,000 ns** and targeted modalities EMG/IMU. This timestamp is not an
asserted measured offset.

| Request | Actual result | Saved `syncAnchorsApplied` | QC anchor count |
| --- | --- | --- | --- |
| false | completed | `{"applied":false,"anchors":[]}` | 1 |
| true | completed | `{"applied":true,"anchors":[]}` | 1 |

Both real package readers return the exact anchor. All 12 raw/event inputs in
each copied package and all 97 source inputs remain unchanged. The original
saved params, QC reports, manifests, job logs and source inventories are retained.

This demonstrates the persisted QC provenance defect. It does not decode the
mini-session's placeholder MCAP data or exercise a feature-alignment algorithm.

## Paired receiving

The final test file executes the actual public job API and ordinary fixture
filesystem. It is identical in the original-source comparator and candidate.
Its 17 collected cases cover:

- Default and explicit-false QC, with and without recorded anchors; truthful
  saved/returned status, retained anchor inventory and unchanged raw/event bytes.
- Explicit refusal with and without an anchor, without producing an analysis job
  or mutating the request.
- Preservation of a complete prior named job, including a binary review marker
  and an empty directory, when an alignment request would otherwise replace it.
- All eight supported command names rejecting the request before an intentionally
  malformed manifest is read or a progress callback is invoked.
- Preservation of the existing explicit unknown-command refusal.

| Gate | Original source | Candidate |
| --- | --- | --- |
| Same 17-case regression file | 6 passed, 11 failed; exit 1 | 17 passed |
| Candidate plus existing QC/destination/replacement/CLI cases | not repeated | 59 passed, 1 Windows-only skip; exit 0 |
| Scoped Ruff, repository's Python 3.12 rules | — | passed |
| Source preservation | original 97 inputs retained | all 107 comparator/candidate inputs retained |

The existing candidate controls include real CLI success/failure, destination
containment, retained prior results after partial output/cancellation/callback
failure, promotion/restore failures and successful replacement. No product
function was substituted to establish the new admission behavior. The inherited
fault-injection controls retain their existing implementation and assertions.

The sole skipped case is
`test_windows_output_junction_cannot_redirect_into_sources`, explicitly marked
for native Windows junction semantics. All 17 new cases executed. The native log
also retains the existing Python 3.13 deprecation warnings for
`PurePath.is_reserved()`; this contribution does not modify that separate path.

## Runtime qualification limits

The Mac comparison uses existing **Python 3.13.7** and its installed scientific
libraries. CaptureSuite declares **Python >=3.12,<3.13**. Therefore these results
are **advisory native source execution**, not acceptance of a supported package
installation. Existing Python 3.12 interpreters were inspected; none of the
checked environments provided the full scientific dependency set. No package,
shared environment, runtime default or service was changed.

The unchanged hosted workflow uses **Python 3.12 on Windows** and executes
`tools/run_ci_tests.py`, which collects the actual `tests/` directory,
validates process exit against JUnit, and records the tested source commit,
working bytes and source preservation. Its exact-candidate result and the
existing C++/native gates are required separately before integration. At source
packet freeze, those hosted results and final independent acceptance are pending;
this native archive does not substitute for them.

No UI, acquisition, participant data, physical hardware, installed adoption,
synchronization accuracy or whole-application result is asserted.

## Retained evidence and reproduction

Native owner directory:
`/Users/me/capture-sync-request-bd1abdb2f886-20261008`.

The read-only original source is `baseline/`; `baseline-suite/` adds only the
current validation inputs and identical new test; `candidate/` carries the
qualified two-hunk runner and additive scope note. All are isolated from other
authors' checkouts. Commands, runtime versions and before/after source inventories
are retained in the receipts.

| Evidence | SHA-256 |
| --- | --- |
| Original actual-QC receiver | `b56cbdd9fc9d4f5a0c14977f4a5d4e4e3f27118fbcadf2fdc6d40f8dfe05c9bd` |
| Original actual-QC receipt | `ff8c7490b008254fe9e9416e495f8e030ced93484fc825b018235967f97c5722` |
| Paired qualification driver | `ff1a35740a229e2307ee28f6ebe7b88f22d10639247faaf57068f8692e8a3d41` |
| Paired qualification receipt | `0c5d8a38836b226a6186cfc886a05ef9f13b0ba4dcd384751561f1fac385f41e` |
| Candidate test transcript | `39e37e40bf9e7f821e7dacbc60ee8c54a6a206cff36f180d5ccb3a53207f5c35` |

Portable supported-environment regression command:

```sh
python -m pytest -q tests/analysis/test_sync_anchor_request.py \
  tests/analysis/test_phase_a_qc.py tests/analysis/test_job_destinations.py \
  tests/analysis/test_job_replacement.py tests/analysis/test_job_failure_cli.py
```

The [native evidence archive](evidence.tar.gz) is **261,912 bytes**, SHA-256
**15f083063dad742c482b28e91064f2a56e0edd1a631b1a627f08e68976b14b9e**,
Git blob **6476538ae6a8a266f55aacf427549b7983fa1b19**. It contains 565 regular
members: a manifest plus 564 entries with byte counts, SHA-256 values and Git
blob identities. Every entry was independently checked after transfer; the three
qualified source files match the review packet exactly. Native repacking was
byte-identical.

The archive includes the exact source/validation bundles, final source, drivers,
both original/candidate JUnit and logs, source inventories, original real-QC
packages and the new tests' actual job-control files. It preserves the observed
failures separately from the successful final comparison.

Preparation notes retain the transient ENOSPC and path-validation timeout, each
followed by absence/readback and one same-route retry. No cache was removed.
An exact-byte guard also rejected an older scope-document payload before either
paired source tree was created; the final composition uses the complete current
document. These preparation failures did not execute a stale candidate or alter
the frozen source/tests after qualification.

## Current finalizer composition — latest qualification

This section supersedes the initial source/gate status above without rewriting
the historical observation, comparator, or evidence archive.

The current receiving parent is **70f34e3b982523b544a9370d2316a1b69d79bd70**,
tree **1537621f793d5d5c9b331f3c4d37a79a4af824b7**. It includes PR46's
actual output-finalizer integration and the independently merged kinematics
correction. The current parent runner is blob
**70a27b677384dac61cb25bea86f80632c1bf328e**. The same early refusal and
literal false manifest flag are its only production changes. Removing those
two hunks restores that complete runner; its final-log inventory, lack of a
manifest self-checksum, retained failed attempts, cancellation/callback order
and prior-result replacement behavior are preserved.

The current candidate runner is **19,508 bytes**, Git blob
**ac08d68b636ce17530816118032e81e5d8f734b2**, SHA-256
**d0442eab9b03d4e4c2d5a9399e2d040350370e8661fe9e2511d817e8651f6e15**.
The 17-case new test, additive scope note and original archive retain the exact
identities listed above. All other current production/validation inputs used
by this receiver match the current parent.

The paired receiver adds the actual newly merged
`tests/analysis/test_job_output_provenance.py` controls. These exercise complete
real QC inventories, original and replacement job output paths, readable final
log bytes, late failures and the owner-defined absence of a manifest self-entry.

| Current-parent gate | Actual result |
| --- | --- |
| Same original-source 17-case negative comparator | 6 passed, 11 failed, exit 1 |
| Candidate new cases plus existing QC, destination, replacement, CLI and output-provenance cases | 66 passed, 1 Windows-only skip, exit 0 |
| Scoped Ruff under the repository's Python 3.12 rules | passed |
| Source bytes before and after execution | all 109 files in each variant unchanged |

These results use the same existing **Python 3.13.7** environment and remain
advisory native source execution. That interpreter does not have `mcap`;
the seven newly merged real numeric CLI/MCAP controls are retained as source
inputs and require the unchanged supported **Python 3.12/Windows** CI gate.
They were not run through a substitute decoder or a modified test. No package
or environment was installed or changed.

The earlier head `f5988261ba06d7ac9328b68295200cce0b49fb6e` passed both hosted
jobs in [run 37790266959](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37790266959):
Python 3.12.10/Windows recorded 404 passed and 6 skipped; CMake passed 30 tests,
and the actual native daemon/recovery receiver passed six cases. Its CI
synthetic checkout `9edbad00db237786fe169d96166e48e6413a7a8f` had the exact
original PR tree. Those results do **not** qualify this later finalizer
composition; the existing workflow must run this exact current source before
integration. The earlier native-CI receipt explicitly recorded
`source_worktree_dirty: true` and unchanged working bytes during execution.
The signed hosted artifact transfer returned HTTP 403, so hosted ZIP members
were not inspected; the actual job logs and their emitted receipts were read.
Both limitations remain retained rather than inferred away.

The [current-finalizer evidence archive](current-finalizer-evidence.tar.gz)
is **440,747 bytes**, SHA-256
**4daf89d3e87c7cf0d0630399676ab544c22d825779fde455380b61097a18654a**,
Git blob **b157de2f3644138a5349b23ec90d052cefebfd80**. Its 1,508 regular
members comprise a manifest and 1,507 independently hashed entries. Native
archive readback matched every frozen member. Qualification receipt SHA-256:
**fab2ec8d8a4c1ab72b1c4028dab07eed6b4258c1b98eafe514177f3b2cbb1775**.

The archive retains both 109-file source variants, the same new test, all
actual temporary job/control outputs, original/candidate JUnit and logs, source
inventories, the receiving driver and transport. Forty-eight test-created
symlinks and 1,413 directory names (including empty outputs) are recorded as
inert metadata only; no link was dereferenced and there are no active archive
symlinks. The first packaging recipe stopped at its no-symlink assertion before
creating an archive. The corrected recipe and original failure description
are retained; source and receiving results were unchanged.

Native paths are under
`/Users/me/capture-sync-request-bd1abdb2f886-20261008/current-finalizer/`.
The machine-readable [package summary](current-finalizer-package.json) pins
member counts, current source identities and test counts. This composition
does not implement or qualify timestamp alignment, raw MCAP decoding on Mac,
physical hardware, installed adoption or whole-application behavior.


## Current external-prediction composition — 58157fdc1b83

Main advanced again through PR65 after the prior exact-head review. This composition
preserves every current-parent leaf except the declared refusal, scope documentation
and this progress entry. In the shared runner, PR65 adds exactly
`prediction_path=params.extra.get("prediction_path")` to the existing eval dispatch.
That argument remains byte-for-byte intact. Removing the same accepted six-line
refusal and restoring the old manifest flag returns current-parent runner
`ad0a551e90e5d06ec38a9218277efa24b0030c75` exactly. Neither the new prediction
algorithm nor its tests, schema, CLI or upstream progress entry is changed.

The new bounded native receiving passes all **17 existing admission tests** and
**three actual eval groups**. A small, explicitly authored Parquet bundle exercises
the identity default and the external prediction API through the real job runner.
The known two-unit angle offset produces MAE/RMSE 2, while the unchanged velocity
produces zero error. Every declared output byte count and SHA-256 is checked,
including the preserved final log inventory. A requested alignment is refused before
an absent prediction file can be read, before progress and before replacing the
previous successful external job. Original source inputs and raw package files stay
unchanged. Scoped Ruff passes; all **115 receiving source files** remain unchanged.

This execution uses the already installed Python 3.13.7 stack and remains advisory:
the package declares Python >=3.12,<3.13. It neither decodes MCAP nor executes the
external owner's complete sensor pipeline. No dependency installation, shared
checkout change, model-training result or runtime adoption is implied. The new
supported Python 3.12/Windows hosted gates and exact-head independent review must
pass before integration. The earlier 66-pass/one-skip finalizer receiving and both
previous evidence archives retain their original source identities.

The complete additional source, unchanged test, authored inputs, actual eval jobs,
JUnit/logs and receiver are sealed in [current-predictions-evidence.tar.gz](current-predictions-evidence.tar.gz).
Its [package receipt](current-predictions-package.json) records 467,110
bytes, SHA-256 `00a696359054e4025356f7c8b7d75e24043cc7176720206c26429914e1a878cf`, Git blob
`0767d2388dadf9b0d3b3baf9750d335ab019b89c`, 414 hashed entries plus MANIFEST.
Six test-created symbolic links are retained only as inert metadata. The archive
was read back internally as regular files; this is native archive byte verification,
not a claim of remote binary-content retrieval. Qualification SHA-256 is
`49c11dd27ad0e262ea45db94d72efed29cfcab7dcba856e60be32ea01013ebc4`.


## Current publication parent — 9c44354cb101

The final source composition also preserves the subsequently merged checkpoint
section and camera work in current main `9c44354cb101c76beff79265de0040b6839d249f`.
The complete new checkpoint scope text remains intact, with only the same existing
sync-anchor availability clarification inserted under Sync anchors. The shared
runner is unchanged from the qualified 58157 composition; current `windows.py`,
checkpoint/UI tests, camera implementation/workflow/tests and all upstream evidence
remain exact. The progress entry is inserted before a stable existing heading so
future appended work is independent of this entry.

The native 17-test/three-eval-group packet remains pinned to its actual 58157 parent.
It is not relabeled as execution of the new checkpoint or camera source. The full
supported hosted test run receives this current tree, including the unchanged
17 admission tests. Both previous independent reviews retain their original heads;
final exact-head review and current hosted gates are required before integration.
