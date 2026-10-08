# Sync-anchor request admission — source and receiving record

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
