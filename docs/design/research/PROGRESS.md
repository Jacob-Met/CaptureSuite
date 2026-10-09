## 2026-10-09 — Repeat a selected recorded-video interval

Issue #103 adds segment-local A/B repetition and explicit 0.25×, 0.5×, 1× and 2×
review speeds inside the existing Recorded video component. Configuration remains
passive while paused; explicit Play enters the half-open interval, and operator
pause/hide/collapse stops repeat intent. Selection, reload and failure retire
the interval and restore the requested rate. Raw media, shared Review/event-browser
source, timelines, analysis, schemas and dependencies are unchanged.

Windows CPython 3.12.10 / Qt 6.12.0 author receiving passes 21 model cases and all
12 native video cases across an eleven-case full-order pass and the one corrected
receiver-literal case. The first cross-test native abort, unchanged-source isolated
pass, explicit deferred-widget cleanup and test-only Unicode correction remain
separate evidence. No product repair was needed after its first source freeze.
The independently frozen native consumer passes seven original groups, four
original-rate calibrations and seven candidate groups, including measured rates,
real decoded frames, interior/end-of-media wraps and the player retirement fences.

Dark/light/compact QWidget captures use only read-only registration of existing
Windows fonts in the receiver application. Their GPU video surface is not captured;
actual decoded 160×120 pixels are qualified separately. The initial missing-font
captures and pre-Play frame expectation failure are retained. These results do
not claim physical foreground input, frame-exact extraction or universal decoder
rate support. Full installed/hardware and whole-application/C++ acceptance are
separate; GitHub Actions remains held. See [operator steps](../../operator/RECORDED_VIDEO_REVIEW.md)
and [source/receiving custody](../../evidence/review-video-interval-db371a37f4c8/AUTHOR.md).

## 2026-10-08 — Preserve nearest feature pairs across retained row orders

Contributor `chatgpt:/root/production_execution`, issue #86, repaired the
ML-bundle loader's assumption that retained feature timestamps were ordered.
A real private MCAP fixture with different log and embedded timestamp orders
passes through the radar extractor, native feature writer and public Job API;
the original bundle selects energy 4 where the nearest sample has energy 9.

Only feature ingestion adds an inversion check and stable in-memory ordering
of the timestamp and value arrays together. Ordered inputs, duplicate relative
order and the existing equal-distance choice retain their behavior. Stored
inputs, feature writers, kinematics/evaluation, validity, metadata, schema and
the unrelated internal self-digest convention remain unchanged.

The same 17 final native Python 3.12.10 receivers record 6 original passes and
11 failures, then 17 candidate passes without errors or skips. A separate 14
inherited metadata, pose, kinematics, bundle, CLI and actual evaluator cases
pass. Paired file readback verifies all 43 original inputs, six byte-identical
ordered output controls, eleven corrected unordered outputs and identical
non-energy columns. The initial receiver's four schema-invalid 2 ns windows
and their correction remain distinct from the final paired qualification.
[Source and receiving custody](../../evidence/ml-bundle-feature-order-713adaab/README.md)
retains exact files and limitations. Independent review and supported Windows
CI remain separate integration gates; no installed or hardware result is
claimed here.

## 2026-10-08 — Inspect and compare retained analysis parameters

Contributor `chatgpt-ac386303dce2/product_execution`, issue #70, implements
Workbench §6's saved parameter inspection and comparison through native
PySide6 controls in the existing Job inspector. Reviewers can read a loaded
completed job's parameters, choose another completed job from the same session,
and inspect typed, ordered differences and both records' explicit provenance.
The view checks original parameter bytes and canonical paramsDigest, preserves
missing/null and boolean/numeric distinctions, and clears stale or invalid
comparisons without changing any saved source or the main loaded result.

The source fence is two new helper/UI modules and the Job inspector's narrow
construction, clear and load hooks. The figure gallery, sync dashboard, result
history, source/time selection, backend writers, numerical code and schemas
remain owned by their existing contributors. A bounded metadata reader also
keeps malformed UTF-8 or linked manifests out of the legacy Qt callback while
preserving valid failed-job metadata and output labels.

Original native Qt absence and three legacy-wrapper failures are retained.
The first source passes 43 author cases, including a real QC pair from the
bundled synthetic mini-session. The bounded wrapper successor passes 46 cases
with zero skips; its one producer case is deliberately deselected locally,
then the unchanged retained actual pair is received through the final native
controls with all 23 package files preserved. The UI source stays byte-identical
between those passes. Separate independent native receiving passes 16 behavioral
cases and five final inspector-boundary cases, with zero skips, while retaining
three original wrapper failures and its own corrected driver expectations.
Actual current-head Windows CI remains the final integration gate; these local
results do not claim installed desktop or physical acquisition validation. See
[operator semantics](JOB_PARAMETER_COMPARISON.md) and
[exact receiving evidence](../../evidence/job-parameter-comparison-ac386303dce2/README.md).

The first actual Windows gate retained 565 passes, two retry/reload failures
and six existing missing-daemon skips. CPython's Windows path/handle ctime
semantics exposed a reader portability defect. The bounded successor compares
complete metadata within each API family and checks pathname identity after
handle close. The same four reader controls change from two failures and two
passes to four passes; all 46 unchanged local GUI/API controls also pass, with
the optional repeat of the actual QC producer still deselected locally. The
original hosted logs, source, tests and previous native capsules are preserved.
Independent Windows 3.13.15 helper receiving changes from four passes/two
failures to six passes, and unchanged Linux native Qt receiving passes 16+5
cases. These keep their distinct runtime/source pins; the complete successor
Windows 3.12 gate remains required. No retry expectation, backend, workflow or
dependency is changed.

## 2026-10-08 — Describe actual ML-bundle values and configured cadence

Contributor `chatgpt:/root/production_execution`, issue #72, prepared a distinct
metadata repair after PR46 integration. The ML producer previously declared
z-score inputs, linear target interpolation and a requested rate that its
actual Parquet values and center spacing did not implement.

Only the producer's manifest dictionary changes. It now records unnormalized
inputs/targets, nearest features and inclusive-window median targets. Effective
integer-hop timing and integer half-width stay separate from original requests.
The single median-center fallback is explicit, and the rate identifies the
configured hop rather than claiming an observed or native sensor cadence.
[The producer contract](../ML_BUNDLE_METADATA.md) documents these fields.

Eight identical final regressions retain eight original failures and pass on
the candidate under native Python3.12.8. Five existing pose/kinematics/ML/eval/CLI
cases also pass at the same producer source. Three actual original-input Parquet
witnesses remain byte-identical after the change, and all twelve original
fixture files remain intact. Existing output receipts and the public job's
original parameters agree with their final bytes. Scoped Ruff passes.

Every source byte before and after the metadata dictionary remains unchanged.
The evaluator, kinematics, sync/checkpoint/UI owners, numerical algorithms,
schemas and unrelated internal self-digest convention retain their scopes.
[Source and receiving evidence](../../evidence/ml-bundle-metadata-713adaab/README.md)
keeps the original failures and the proposed-source results distinct.
Independent source review and the existing supported Windows CI are separate
integration gates; no installed or hardware outcome is claimed here.

## 2026-10-08 — Preserve missing pose evidence in kinematic labels

Worker `estate-406d0fb04c43 / production`, issue #56: non-simulated pose tables
previously fell back to synthetic angles when required body landmarks were
absent. The real Parquet-to-kinematics CLI could therefore complete with invented
values and valid flags. A missing landmark on one side also invalidated usable
geometry on the other, and finite central differences or rolling ranges could
hide an invalid center frame.

The bounded computation repair selects synthetic values only for explicit sim
model IDs. It checks each required landmark's confidence and finite coordinates,
keeps independent elbow/shoulder validity, and masks undefined angle, velocity
and AFR values at missing frames. Existing valid-input calculations, sim behavior,
model identity, schemas, pose backends and job publication are preserved.

On native macOS arm64 with the declared Python 3.12 science dependencies, the
same 13 focused tests retain 11 original failures and two passing controls;
the repair passes all 13 plus eight original pose/kinematics/ML consumers, with
zero skips. The real CLI writes masked Parquet and truthful detection rates
while preserving every original package and input-pose byte. All selected source
bytes remain unchanged during execution, and scoped Ruff passes. Independent
receiving and the existing supported Windows CI remain separate integration gates.
No inference service, physical capture, smoothing or calibration result is claimed.

## 2026-10-08 — Windows atomic writer reserves owned temporary files

Contributor `estate-6267db2cfc6e` prepared the repair for issue51/PR52. Windows
now reserves a unique sibling with `CreateFileW(CREATE_NEW)`, retains the original
writable handle through writes and `FlushFileBuffers`, checks close, and keeps
the existing write-through publication boundary. Failure cleanup addresses only
the file created by that invocation; retained legacy `.tmp` paths are preserved.

The original-source checkpoint is `c1bc438ea07492a303f89cea5deb242efeb6f8e9`.
Its CI run37770868596 is retained separately from the repair's receiving run.
Both use the unchanged four real Windows tests (SHA-256
`485af6482c6b14fc7c187b45cc366af547bf0a1fe2c0651c8b68c8d25e854cfb`).
Native acceptance requires actual original-source preservation failures and
candidate passes under the existing complete Windows workflow. The final PR52
receiving review records the actual outcomes and their exact source identities.
The POSIX implementation and the current workflow remain unchanged.

## 2026-10-08 — Windows atomic temporary-file preservation controls

Contributor `estate-6267db2cfc6e` prepared four Windows-only real-file tests for
the existing atomic writer: a raw-file hardlink at `manifest.json.tmp`,
a hardlink to the prior manifest while a live handle blocks publication, an
ordinary retained file at that name, and a raw-file symlink. The tests compare
actual bytes, Win32 file identities, alias retention and final directory contents.
They use exclusively reserved fixture directories and the linked production API.

Native Windows compilation and execution are pending. This first publication
keeps production unchanged so the supported Windows workflow can retain the
original failure before the separately prepared repair is received. The same
test bytes must qualify the repair. Only a missing Windows symlink privilege
may skip that case; the other three cases remain required. The current CI
workflow, POSIX implementation and separately owned storage fixture are unchanged.
Source bindings and the planned receiving boundary are recorded in
`docs/evidence/windows-atomic-temp-preservation-6267db2cfc6e/README.md`.

## 2026-10-08 — Receive fixture ownership repair onto accepted main (estate-87eaaf0fdf63)

The original Linux port #36 and the separately owned POSIX alias repair #44
are now accepted on main `ac52c3ca7164a6ab457d11a8a1448957093eb592`.
The fixture companion from #42 is composed onto that source. It retains the
reviewed unique-directory fixture and adds only its CTest registration to the
current test build. All accepted production, durability and alias-receiver
bytes remain unchanged. The complete current upstream progress log follows
unchanged after this lane's two blocks.

The historical receiving results below remain pinned to their recorded source.
Current mainline qualification, composition hashes and hosted gate results are
recorded in `docs/evidence/storage-fixture-isolation-87eaaf0fdf63/MAINLINE.md`
and the PR. No claim of hardware or power-cut qualification is added.

## 2026-10-08 — Preserve concurrent storage-test evidence (estate-87eaaf0fdf63)

Independent receiving of Linux-port PR #36 found that its new atomic-storage
test deleted an unrelated invocation's receipt under the shared temporary
directory while reporting all six assertions passed. The counterexample ran
against the exact published source with real Catch2 and disposable private
temporary data on the ThinkPad; no existing worktree or capture was changed.

The test now atomically reserves a unique directory and cleans up only that
owned path through a scoped fixture. A CMake receiving case runs the actual
test with a retained sibling receipt and checks its bytes and fixture cleanup.
The unchanged original fails this receiving case; the corrected candidate
passes it plus the two native storage tests (11 assertions) under strict GCC
warnings. The production atomic-file and disk-watchdog sources are unchanged.

The independent review also passed ten actual POSIX atomic-write boundary
cases, including open/close errors, binary and relative paths, real rename
refusal and interrupted directory sync. These qualify the stated local
storage boundary; they do not constitute a full native build, Windows or
hardware acceptance. Source pins and raw failures are retained in
`docs/evidence/storage-fixture-isolation-87eaaf0fdf63/`. This companion is
prepared for the existing PR #36 owner; it has not been merged or deployed.

Current receiving also preserves the producer's writer-close revision
`05a6b6bd02f05efd2c7380ea4ee8f92942609d4b`. The independent ten-case
receiver above remains bound to retained original `16eb17f` atomic source; it
does not claim qualification of the revised writer. See the packet CURRENT.md
for the exact companion composition and current fixture replay.

## 2026-10-08 — Analyze the section closed by a captured checkpoint

Contributor `18a24bf0c281 / estate_product`, issue #54: selecting a captured
checkpoint now resolves the preceding effective checkpoint (or session time
zero) through the selected checkpoint. The final marker no longer selects the
tail. Existing timestamp aliases, exact integers, stable ties, inclusive point
sections and gap helpers are preserved. A persisted negative first marker
reports invalid inverted bounds without clamping or rewriting the recording.

The same frozen native Python 3.12.8 test file changes from **25 failed / 5
passed** on the original implementation to **30 passed** on source `4fcd0aa`.
Ten real CLI cases per implementation check synthetic protobuf MCAP through
Parquet/CSV output; all eight raw files in every invocation remain exact. The
candidate also passes **19 existing QC/features/stream-gap checks**, scoped
Ruff and the existing license checker. Two upstream protobuf deprecation
warnings remain recorded. Independent future-marker/data invariance and
inside-section sensitivity receiving passes **26 checks** on the same
production blob, with its original failures retained separately.

`ANALYSIS.md` records the explicit decision reconciling the captured-checkpoint
session contract with an older research tagged-start example. Scope UI #53 and
history #55 keep their owned files. Actual native figures contain the correct
selected samples; their existing elapsed-axis label discrepancy was retained
and handed to the current plot/scope owners without editing plot source.

Exact source pins, complete native logs/fixtures/artifacts, actual PNGs and
byte-preservation receipts are in
[`docs/evidence/checkpoint-sections-18a24bf0c281/README.md`](../../evidence/checkpoint-sections-18a24bf0c281/README.md).
The distinct independent review is in
[`checkpoint-future-isolation-18a24bf0c281`](../../evidence/checkpoint-future-isolation-18a24bf0c281/README.md).
This is bounded native offline receiving; supported Windows CI, desktop
composition and physical acquisition retain their separate acceptance gates.

## 2026-10-08 — Preserve prior analysis jobs on failed replacement

Worker `estate-6267db2cfc6e`, issue #39: portable job IDs and direct output
directories are checked before writes. An overwrite builds in a unique hidden
attempt, preserves the prior result through analysis/cancellation failures, and
restores it after a failed publication rename. Failed attempts retain their own
manifest identity, original overwrite intent, and actionable diagnostic path.
CLI and desktop consumers preserve exception notes; desktop cancellation stays
quiet while logging the retained path.

Fresh original-source controls reproduce 21 destination failures and seven
replacement failures. The candidate composed with main `52203f5c` passes 50
tests, including real CLI subprocesses and the current stream-gap regressions;
Ruff passes. The two explicit local skips require native Windows junctions and
PySide6. Full supported Windows CI remains the publication acceptance gate.
Exact sources, fresh raw logs, independent agent receiving and the earlier
scratch-loss disclosure are recorded in
[`docs/evidence/analysis-job-preservation-6267db2cfc6e/README.md`](../../evidence/analysis-job-preservation-6267db2cfc6e/README.md).

Composition update: main `ac52c3ca` adds the separately received POSIX sealed-recording
repair. The job-preservation production, tests, and initial receiving evidence remain
byte-identical; hosted CI qualifies this new combined repository tree.

## 2026-10-08 — Receive final output provenance on preserved analysis jobs

Receive the landed PR48 replacement contract before completing PR46. The only
production delta now finalizes the successful diagnostic log before serializing
the manifest, and removes the impossible self-manifest checksum. The stored
inventory agrees with the returned result and final artifact bytes. PR48's
portable destination guards, unique attempts, failed-record handling, previous
result restoration and CLI/UI recovery notes remain unchanged.

The original seven provenance receivers on landed main gave two passes, four
remaining successful-inventory failures and one obsolete completion-callback
expectation. The updated receiver preserves the previous completed revision and
checks both its inventory and the separately retained failed attempt. With the
same updated tests, native Python 3.12.8 receiving improves from **19 passed,
5 failed** to **24 passed, 0 skipped**. This includes the owner's nine replacement
fault controls, two actual CLI failure controls and six existing QC controls.

After receiving PR50's QC collector/HTML changes and PR42's fixture isolation,
the unchanged finalization source passes all **49** focused controls, including
the landed QC gap cases, with no skips. Both owners' source and documentation
remain intact.

Receiving the later PR49 numeric pipeline gave **48 passed and one diagnostic
StopIteration** across seven provenance and 42 numeric controls. Its new CLI
receiver assumed the old self-manifest row existed only to record that row's
known checksum mismatch. Make this diagnostic optional, retain a null comparison
when absent, and record the actual manifest file's external SHA. All existing
assertions and all numeric runtime source remain unchanged. The affected actual
CLI case then passed **1/1**, with retained output bytes and source hashes; the
other 48 cases were not replayed. Independent review verified the diagnostic
delta and all 87 unchanged assertion/call expressions.

The previously qualified PR46 head and all negative evidence remain in custody;
its Windows CI does not qualify this new composition. Exact-head supported
Windows CI remains pending. The separately prepared job-ID candidate was
superseded by the landed owner and is not included. See
`docs/evidence/analysis-output-provenance-current-receiving-20261008.json`.

## 2026-10-08 — Scope recorded analysis gaps to their stream (estate-e82707f2bc62)

A targeted gap from one stream previously invalidated every sibling stream from
that source. The receiving fixture now preserves healthy samples, feature values,
and fail-policy behavior by matching both source and stream in `build_gap_mask`.
Empty stream IDs retain source-wide scope; fully unspecified IDs retain global
scope. Existing time boundaries, open gaps and raw package bytes are preserved.

The same eight native unittest methods ran through normal public imports,
recorded-package discovery and EMG feature extraction. Original source: four
passing and four failing methods (six failed and two errored subtests). Candidate:
eight passing methods on Python 3.12.14, NumPy 2.3.5 and pandas 2.2.3. This is a
focused analysis result; existing hosted Python/Windows C++ gates and independent
receiving are pending at this publication checkpoint. No hardware result is claimed.
Exact source pins, unchanged test hash and raw outputs are retained in
`docs/evidence/stream-gap-scope-20261008-e827/`. Project ownership: issue #40.
The current framing receiver from main `c43b2819` is preserved.

## 2026-10-08 — Generic numeric analysis is usable through the native pipeline (estate-e82707f2bc62)

Issue #43 receives actual generic.numeric_batch/1 recordings through the existing
analysis CLI. The loader now recognizes the native protobuf MCAP type name,
returns the public channels-by-time result, anchors native timestamp differences
to the recorded first-datum session time, and checks actual cumulative buffers.
Missing rate, malformed frames/times/layouts, nonfinite samples and timestamp
overflow produce explicit refusals. Unknown-duration packages retain bounded
materialization without interpreting the open-window sentinel as recorded time.

Schema-specific dispatch now selects a dedicated numeric handler even for LSL
EMG/EEG descriptive modalities. Numeric mean/RMS use scaled finite reductions;
stream identities, units, provisional status and per-stream validity are retained
with real Parquet/CSV outputs and case-safe exact-identity paths. Numeric figures
state their elapsed-time axis and exact first-retained session origin. Existing
plot callers retain their default; the independently merged stream-gap source,
raw capture, acquisition/protocol schemas and job orchestration are preserved.

At this publication checkpoint, the same 26 author tests changed from 2 pass,
5 failures/19 errors on original source to 26 pass. The unchanged independent nine-case
MCAP/numerical receiver changed from 1 pass/3 failures/5 errors to 9 pass. Seven actual
CLI workflow methods passed against the five-file source snapshot, followed by
one affected actual all/figure receiving on the final six-file composition.
Original failed tests, exact source identities and real final PNGs are retained.
Existing full hosted CI and its real schema validator are still required for
integration; local missing-validator behavior is explicit, and no hardware or
deployment result is claimed. See docs/NUMERIC_ANALYSIS.md and the three
numeric-analysis/numeric-mcap/numeric-cli evidence directories dated 20261008-e827.
The source packet stayed frozen during GitHub secondary-write cooldown; final
integration receipts belong to the pull request linked from issue #43.

## 2026-10-08 — Independent sealed-source alias preservation (estate-39c2b591d7e5)

Composed the independently reviewed exclusive POSIX temporary-file supplement
onto PR36 head 05a6b6bd while preserving the author's complete R2 writer-close
repair, evidence and Linux build entrypoint. The initial composition retained
four failing R2 test results. Final composition preserves the existing
zero-progress diagnostic and counts attempted closes of the writer descriptor
separately from the newly opened directory descriptor.

The complete isolated native Linux build passes all **18 CTest targets**,
including the original R2 durability suite (**10/10 cases**) and the added
exclusive-file identity suite (**15/15 cases**). The rebuilt actual
session_doctor preserves a freshly generated, valid sealed MCAP through both
symlink and hardlink manifest.json.tmp aliases; both repeated recoveries are
byte-for-byte no-ops. The exact published R2 executable fails both sealed-byte
preservation controls while reporting success. These are disposable synthetic
fixtures on native ext4, not physical hardware or Windows qualification.

See docs/evidence/posix-alias-receiving-39c2b591d7e5.json for exact source,
binary and retained native evidence. The Windows implementation remains
byte-identical to the published R2 branch. Revised Windows CI remains a separate
integration gate; this local receiving result does not claim a merge.

## 2026-10-08 — Writer-close review repair and user receiving (estate-68e476e98b77)

Independent review of PR36 found an additional actual-process durability
blocker: an injected error from the original `ofstream` writer's close was
ignored, so `session_doctor` returned success and replaced the manifest. The
POSIX path now retains one writable descriptor through short/interrupted-safe
writes, `fsync`, and checked close; zero-progress writes fail, close is not
retried, and all writer failures preserve the old target. Windows source
behavior and the separately owned recovery scanner remain unchanged.

The revised native entrypoint passes all **17 CTest tests** and its strict
standalone durability executable passes **10/10 cases**. The unchanged
independent process regression now returns exit 2 for writer-close EIO,
preserves the recording manifest exactly, leaves no temp file and prints no
false success. Normal success and parent-fsync EIO after rename also pass;
both frozen MCAP files remain byte-identical in all three cases. Original
failed receiver and reviewer reproducers are preserved with hashes.

An ordinary-user receiving copy is retained at
`/home/jacob/capturesuite-receiver-68e476e98b77-r2/bin/session_doctor` (UID1000,
mode0755), SHA-256 `8104af6502590eceff5daf6c57d3f768bb431463104c40a958942d94927cbcf4`.
This resolves access through the original protected estate archive without
changing its ancestor permissions or any service/default. A later compiler
scratch quota failure is retained; assigning compiler TMPDIR to this lane's
own evidence directory allowed the bounded build to finish without cleanup.
Original-head Windows and Python CI passed; revised-head CI remains a separate
integration gate. See `docs/evidence/linux-port-68e476e98b77-r2.json`.

## 2026-10-08 — Linux portable build receiving (estate-68e476e98b77)

Received the retained Linux C++/CMake donor `e3270d84` onto current public main
`742dd7dc`, with the donor patch hash and missing bundle prerequisite recorded.
The isolated native build now produces core/protocol/storage libraries and
`session_doctor`. The documented entrypoint and all **17 CTest tests pass** on
the ThinkPad Linux toolchain, including actual process checks on disposable
synthetic finalized/recovery fixtures. This remains portable-library
qualification; existing macOS A–H, daemon/desktop and hardware work is separate.

A native real-file regression found three donor durability failures: temporary
and directory `fsync` errors were reported as success, and `EINTR` was ignored.
The same four-case executable now passes after propagating failures, preserving
the old target before rename, and reporting post-rename durability uncertainty.
It also passes a standalone `-Wall -Wextra -Wpedantic -Werror` build. Python and
existing MCAP recovery scanner/CRC candidates were left untouched.

Retained limitations/failures: the whole-tree GCC WERROR probe still exposes a
pre-existing logging format-truncation warning; the portable preset uses the
project default WERROR=OFF. A root-filesystem ENOSPC interrupted archiving and
two source writes. Only this lane's reproducible outputs moved to tmpfs; the
two zero-length files were restored from exact inputs before the successful
build. No estate-wide cleanup or service change was performed by this lane.

See `docs/BUILDING-LINUX.md` and `docs/evidence/linux-port-68e476e98b77.json` for
source, dependency, test and receiving boundaries. This source receipt does not
claim a Windows CI, macOS, full-product or hardware pass.

## 2026-10-08 — independent framing-view receiving accepted

Integration receiver `integration-72ac1419` preserved the separate `capture_peer` decision
and exact native outputs under `docs/evidence/framing-view-lifetime-72ac1419/peer/`.
Peer accepted source commit `4359c21f3da93ed863de617331edfc853cf8385d`; its own 27-test
replay and 20-case view/diagnostic matrix pass, and both predecessor active-handler
failures independently reproduce. Product framing and tests are unchanged. The companion
Windows gates and GitHub publication remain pending because content creation is still
secondary-rate-limited; no failed registration was represented as a published claim.

## 2026-10-08 — Newer-schema registry receiving (estate-234cae4aee53)

Receives original Shinogi PR #23 at `c5854a8c5b8a33da8d9f20dd5970f6c14ad597f6`.
Its registry implementation and existing regression remain byte-identical. Future
schema detection uses a real read-only SQLite connection before mutating PRAGMAs;
supported registries retain creation, migration and ordinary writes.

Independent real SQLite receiving covers URI-sensitive filenames, public readers
and write guards, a committed WAL tail held by another connection, and migration
of an existing empty database. On main `c43b281`, three new cases fail and five
controls pass; the composed donor and receiving tests pass all nine cases on
Python 3.12.14. Ruff and source whitespace checks pass. The complete database
bytes (and live WAL bytes in the WAL case) remain unchanged by accepted reads.
No operator database or saved application state is used. Original prior reviews
remain attributed; current Windows CI and source integration are separate gates.
See `docs/evidence/registry-readonly-234cae4aee53/README.md` for exact source and replay.

# Agent progress log

Agents: **read at session start, update at session end.**  
Plan: [AUTONOMOUS_EXECUTION_PLAN.md](AUTONOMOUS_EXECUTION_PLAN.md)

---

## 2026-10-08 — Selective export receiving

Independent receiving of T68 / PR #30 at `69e6cb7` uses the real protobuf MCAP
reader/writer, CPython 3.12 and PySide6, including a native export wizard. Twelve
new behavioral cases retain **seven failures and five passing controls** on the
original candidate. They reproduce omitted later IMU streams under neutral
source IDs and mixed old/new output when a destination is reused.

The qualified successor scans the actual message schemas, creates EMG/IMU
outputs only after matching decoded messages, and rejects nonempty destinations
before writes. Existing empty destinations, timestamps, source bytes and
requested-versus-actual provenance are covered. **31 export tests and all 59
analysis tests pass**, with no skips. The whole configured Ruff and license
checks pass; protobuf/session-schema regeneration has no byte drift.

Independent lead review rejected initial source `a00e0df` / `6866ebd`: moving
lazy output creation into the tolerated input-read handler could hide a write
failure. A real 3890-character destination reproduced success with a missing
selected stream; untouched PR #30 failed as expected. Correction `f81ce45`
keeps input reads in a streaming generator and makes output creation, writing
and close failures actionable and fatal before a success manifest is written.
Six portable cases retain four initial failures and two unchanged input-read
controls. Lead reran the real path-limit case: exit 1, no manifest and unchanged
raw hashes. The final clean/unchanged source passes all 59 analysis cases.

Successor PR #45 preserves the qualified tree on current main. Its first
Windows Python run (`37758185607`) reached all 255 cases: 246 passed, six
daemon-build skips, and three failures from Unicode paths printed through
cp1252 stdout after successful export writes. A real child process under
`PYTHONIOENCODING=cp1252:strict` reproduces this failure locally. The CLI now
escapes only status text that its output encoding cannot represent; filesystem
paths and manifest contents remain unchanged. All 60 analysis tests pass with
the added regression. The failed Windows receipt is retained and the next
Windows run remains required before platform acceptance.

The forward update also receives main `52203f5`, preserving its landed Linux
storage/recovery and stream-gap changes through a clean normal merge. All 68
analysis tests pass on the unchanged composed source; the accepted exporter
bytes are unchanged. Independent lead receiving confirmed both selected
streams, the actual Unicode destination and unchanged raw hashes under a
legacy output pipe. The next hosted Windows run remains the final platform gate.

The full repository suite on Linux still fails during collection with the same
four pre-existing `msvcrt` import errors on current main and the successor.
Windows CI/native daemon qualification remains a separate acceptance gate; no
hardware, installed app, release or native Linux-port acceptance is claimed.
The original T68 and Linux portability owners retain their respective scopes.
Exact source pins, negative evidence and replay commands are retained under
[`docs/evidence/export-selection-20261008/`](../../evidence/export-selection-20261008/).

## 2026-10-08 — Retained framing exception recovery (integration-72ac1419)

Independent receiving of PR #35 found that an active or saved FrameError retained
an exported memoryview and made the documented decoder reset raise BufferError.
The isolated successor releases only the parser-owned view on every decode exit;
wire fields, payload ownership, caller-owned views and error diagnostics remain intact.
Exact predecessor 65b76c9 plus 11 new controls: 9 failed / 18 passed. Same actual package,
Mac Python 3.12.8 / protobuf 4.25.9 and candidate: 27 passed; strict Ruff/diff-check passed.
Source bytes, raw failures and replay are in
`docs/evidence/framing-view-lifetime-72ac1419/README.md`.
This is an isolated qualified companion pending independent receiving and its own
supported Windows CI. GitHub comment creation remains temporarily rate-limited;
no review publication, source integration, named-pipe or hardware pass is claimed.

## 2026-10-08 — Incremental protocol error propagation

`FrameDecoder.feed` now propagates `FrameError` for complete bad-magic and
oversized headers instead of treating these errors as incomplete reads. Valid
fragmented frames, event/reply correlation, incomplete payload buffering and
explicit reset behavior retain their existing semantics. The wire format and
C++/daemon implementations are unchanged.

On macOS 26.6.2 arm64 with Python 3.12.8, the retained two-case regression failed
against main `742dd7d` (2 failed, 6 passed with existing framing tests) and the
complete focused framing set passed after the repair (16 passed). A paired run
of all collectible protocol tests changed from 7 failures/139 passes to 146
passes. Four pre-existing Windows-only `msvcrt` collection errors remain visible
in both runs; this is not a full Windows, native daemon or hardware pass.
The runs selected the declared grpcio-tools 1.62.3 compiler instead of the host's
incompatible newer protoc and left generated source bytes unchanged. Initial
compiler-selection failures and the original red result are retained.
See `docs/evidence/framing-rejection-20261008.json` for exact source hashes,
commands, environment and the remaining acceptance boundary.

## 2026-09-29 — Newer registry schema read-only enforcement

`AppRegistry.open()` now detects existing schema versions through a read-only
SQLite connection before applying WAL/configuration PRAGMAs. Newer-schema
registries retain that read-only connection; focused Windows tests verify direct
SQL writes fail and opening/closing leaves the database bytes unchanged.

## 2026-09-09 — Compiler boundary and reliable test evidence

The second hosted Python job passed **151 tests with six explicit daemon skips**.
Its exact JUnit artifact was downloaded independently and its bytes/case counts
verified. The second C++ run successfully resolved the registry and configured,
then reached compilation and exposed C4267 inside unmodified generated protobuf
map-accessor headers. Only that generated include directory is now `SYSTEM`;
a real MSVC negative-build probe proves the same warning in owned source remains
fatal. Its successful control/generated builds and expected failed owned build
are retained rather than disabling application warnings.

Added a reusable exit-aware Python test runner. It rejects progress-only success,
native nonzero exit, inconsistent/missing JUnit, zero executed tests, and source
changes during a run. Receipts distinguish a dirty working tree from its HEAD
commit and bind the exact working-source bytes. The original pytest scope is not
reduced. New negative cases include the observed native heap-corruption exit.

The new cleanup regressions were also run against the original source: three
failures were detected; the same eight cases all passed against the repair.
Those fake-client results do not represent actual hardware qualification.
Hosted compiler and native macOS analysis follow-up remain in progress until
recorded otherwise; these notes are not a whole-product acceptance.

## 2026-09-09 — Follow-on CI recovery

The first hosted candidate (`47fc348`, run `34402331931`) passed its Python job.
Its C++ setup advanced past the repaired SHA pin but exposed a second blocker:
the old registry predates the required MCAP port. The explicit new baseline is
`4334d8b4c8916018600212ab4dd4bbdc343065d1` / `2025.09.17`, the first stable
release after official MCAP inclusion. Direct ports and requested features were
verified upstream; a new checker catches this class of omission before CMake.
Windows CI is explicitly on the documented VS 2022 runner family.

Two initial isolated-venv full test runs ended with native heap corruption at
shutdown. Retained those failures rather than treating completed progress as a
pass. UI tests now share one session-lifetime QApplication, clean up their widgets
before application teardown, and use isolated application state. Three complete
repeated native runs exited normally: **150 passed and six daemon-only skips in
each**. This is a tested candidate improvement, not proof all native crash causes
are ruled out. All existing UI assertions remain.

CI also separates native commands into individual fail-fast steps and retains
scoped test/configure diagnostics. The registry/platform follow-up still needs
hosted C++ verification. See `docs/evidence/ci-recovery-20260909-round2.json`.

## 2026-09-09 — Current CI recovery qualification

The September 1–3 milestone notes below are historical. The published main
checkpoint `99b002a` still has failing whole-repository CI; its twelve offline-demo
tests were not full application qualification.

Current candidate: `presence/ci-recovery-20260909`, [issue #6](https://github.com/Jacob-Met/CaptureSuite/issues/6).
Reproduced 60 lint findings and a Windows JSON-schema byte-regeneration failure.
Fixed producer line endings without weakening the byte comparator; completed the
existing lint scope, pinned the original intended vcpkg version by full SHA, and
made the full Python dependency set explicit. Fixed cleanup that could suppress
capture errors or leave a started session running when arrays metadata was absent.
New fixtures cover these defects without contacting a daemon or physical device.

Existing local CPython 3.12: **143 passed, six daemon-dependent skips**; lint,
protobuf regeneration/drift, license checks and static CI contract passed.
An isolated environment installed successfully and passed dependency/import checks,
but its full pytest process exited with Windows heap corruption (0xc0000374) after
reaching 100%. That failed run is retained and is not counted as a pass. Native
cleanup diagnosis and hosted Windows C++ qualification remain in progress;
no hosted/C++/hardware pass is claimed by the earlier local result. No release tag, DOI,
publication deposit or physical capture is authorized or performed in this pass.

See `docs/evidence/ci-recovery-20260909.json` for input pins and qualification scope.

## Current phase

| Field | Value |
|-------|-------|
| **Active phase** | **Public release prep** (plugin registry + SDK shipped); Phases 0→6 still green on sim |
| **Next implementation** | Cut `v0.1.0` on GitHub + Zenodo DOI; Phase 8 hardware validation when devices available |
| **Parallel workstream** | None required for 0–6 gate |

---

## Operator directives

| Date | Directive |
|------|-----------|
| 2026-09-01 | **Hardware last** — sim/replay/fixtures only until Phase 8 |
| 2026-09-01 | **Industry-quality bar** — cross-cutting every phase |
| 2026-09-01 | **No hand tracker** / overlay salvage until re-enabled here |

---

## Phase status

| Phase | Status | Gate evidence |
|-------|--------|---------------|
| Research (Tracks A–H) | **Done** | [README.md](README.md) |
| 0 Foundation | **Done** | Theme, SessionTimeline, Preferences, honesty banners |
| 1 Review + export | **Done** | Export wizard + provenance sidecar; Review stream inventory |
| 2 Analysis plugins | **Done** | Manifest registry; dummy plugin; pipeline dispatch |
| 3 Analysis workbench | **Done** | In-app PyQtGraph; no plot `startfile` |
| 4 Modality depth | **Done** (sim) | Scorecards ≥4/5 on sim-applicable dims; HW setup/preflight → Phase 8 |
| 5 Pose + kinematics | **Done** (sim) | `pose` + `kinematics` + mappings panel; registry-valid parquet |
| 6 ML bundle + eval | **Done** (sim) | Schema-valid `ml_bundle`; radar→teacher test; Analysis UI commands |

---

## Blockers (product / legal only)

| Blocker | Workstream | Mitigation |
|---------|------------|------------|
| Kobayashi license | Tier B metrics | Tier A only |
| Hand tracker bake-off | UrologyMoCap | **Deferred by operator** |

---

## Last verified (update each session)

| Check | Date | Result |
|-------|------|--------|
| `pytest tests/protocol` + `tests/analysis` | 2026-09-03 | green (incl. Python SDK + LSL unit tests) |
| `tools/check_licenses.py --enforce-spdx` | 2026-09-03 | OK |
| Protocol minor | 2026-09-03 | **1.5** (`ListPlugins`) |

---

## Session log (newest first)

### 2026-09-03 — Public release plan (Phases A–E)

**Shipped:**
- Standalone product tree (lab sidecar dirs relocated out of CaptureSuite)
- GPL/Apache split + community health files + SPDX
- `PluginRegistry` + `plugin.json` discovery + `ListPlugins`
- Core cleanup: `generic.numeric_batch/1`, neutral sim aliases
- Python worker SDK, example sine + LSL bridge plugins
- Docs: `docs/spec/`, `docs/plugins/`, `docs/operator/`, README rewrite
- CI (`ci.yml`) + release workflow; `tools/run-demo.ps1`

**Remaining for human operator:** create GitHub repo, push, enable Zenodo, tag `v0.1.0`, paste DOI into `CITATION.cff` / README.

### 2026-09-01 — Phase 4 scorecards + Phase 6 Analysis UI (goal closure)

**Shipped:**
- Analysis workbench: pose / kinematics / ml_bundle / eval commands + dependency pickers (`widgets_analysis_jobs.py`)
- Anatomical/spatial mappings panel (`widgets_mappings.py`)
- Review stream inventory (schema, rate, dims, units, segments)
- Deeper Focus modality strips (EMG channel grid, IMU segments, radar/camera slots)
- Radar→teacher `ml_bundle` fixture test + schema validation
- Modality scorecards updated for sim/replay ≥4/5 (HW-deferred dims noted)

**Gate:** Phases 0→6 automated gates green on sim/fixtures. Phase 8 HW remains last.

### 2026-09-01 — Phase 5 kinematics + Phase 6 ML bundle/eval (sim)

**Shipped:**
- `capture_analysis/kinematics/` — Tier A from pose landmarks; registry column validation
- `capture_analysis/ml_bundle/` — aligned windows + `capture.ml_bundle/1` manifest
- `capture_analysis/eval/` — identity baseline eval report
- `tools/run_analysis.py` — `kinematics`, `ml_bundle`, `eval` subcommands

### 2026-09-01 — Phase 4 modality depth + Phase 5 pose sim teacher

**Shipped:** Expanded Focus cards, preset library, radar array preset, vendor replay, sim pose teacher.


## 2026-09-09 - Public evaluation entry point

Added an offline synthetic QC demonstration in `tools/demo_qc.py` and regression
tests. It reuses the existing analysis engine, copies the shipped mini-session,
checks source immutability, and rejects output overwrite. Public maintainer name
is Jacob Metoyer. No daemon, protocol, schema, hardware, patient-data or existing
private research workflow was changed. Qualification receipts are recorded in
`docs/evidence/offline-demo-20260909.json` after execution.


## 2026-09-09 — MSVC environment portability preflight

Hosted run `34406178247` advanced through vcpkg/configure and exposed an owned
`C4996` under `/WX`: direct `getenv` in `radar_worker_bridge.cpp`. The same
pattern existed in later daemon/test/camera paths, so the repair uses one
header-only `capture::env` helper rather than waiting for serial hosted failures.
A source preflight now rejects direct `getenv` in owned C/C++ while preserving a
portable fallback in the helper itself. The MSVC warning-boundary probe compiles
the helper, keeps generated headers external, and still proves an owned C4267
warning fails. Python contract tests cover changed inputs.

Evidence: `docs/evidence/msvc-environment-portability-20260909.json`. This is
same-author portability qualification, not hardware or whole-product validation.
The exact candidate still requires hosted Windows rebuild before acceptance.


## 2026-09-09 ? Native integration acceptance gate

Prepared the next CI gate after the portable MSVC environment repair. Native
Python fixtures now resolve the explicit hosted build, isolate app/session/log
state, and only stop child processes they started. Crash recovery compares the
SHA-256 of already sealed bytes before and after `session_doctor`. A dedicated
native receipt runner rejects missing binaries, nonzero exit, invalid JUnit, any
skipped native test, or source changes during the run. The CMake job builds
`session_doctor` and runs this phase after ordinary CTest.

Local contract/evaluator tests: **46 passed**. The complete ordinary Python phase
passed **197** with the expected **six native-daemon skips**; a deliberately
missing native build was rejected before daemon launch. Native state also sets
`CAPTURE_TEST_SIM_ONLY=1`; the daemon checks it before Media Foundation camera
enumeration, so this gate is designed not to touch physical webcams. This is not
positive native execution. Hosted Windows execution of the exact published candidate is
the remaining acceptance gate. See
`docs/evidence/native-integration-gate-20260909.json`.


## 2026-10-08 — Camera plugin runtime packaging (#34)

ChatGPT worker `dd846795-production` added the existing five camera runtime DLLs
to the plugin-manifest executable directory as well as the legacy worker directory.
This fixes the asymmetric post-build copy rule without changing the dependency list,
worker launch logic, schemas, protocol, or radar packaging.

The same final CMake regression harness executes the actual production staging
commands against native C++ fixtures. Baseline `742dd7d` fails for a missing
plugin-local DLL; the repaired source passes Unix Makefiles and Ninja Multi-Config.
Both layouts retain exact executable/DLL/manifest bytes. Changed-input controls
reject a plugin-only omission, restore it on rebuild, and reject a missing source
DLL during the actual build. The test requires only CMake 3.28+ and a C++ compiler:

```sh
cmake -DWORK_DIR=/absolute/new/scratch/path -P tests/cmake/camera_runtime_packaging.cmake
```

The DLLs are synthetic text fixtures: these results qualify packaging commands,
not Windows loader behavior, GStreamer, physical capture or full-product readiness.
Exact source hashes and retained logs: `docs/evidence/camera-runtime-closure-20261008.json`.
Owner receiving remains a draft-PR step; no main merge, deployment, release or tag
is represented by this source qualification.


### 2026-10-08 — Receive the parallel linked-library packaging fixture

After the initial coordination comments were temporarily throttled, receiving
discovered candidate 8167c9ad8b44433409e8f3d66f66c4254f879db3 from
estate-afe225d6c6be/product_execution (original author: HAMON Product Worker).
Its production command bytes match this fix; only the explanatory CMake COMMENT
wording differs. The receiver kept the existing production CMake bytes and imported
the four linked-library fixture files and three original evidence files unchanged.
Both package manifests and the original source archive remain retained.

Independent receiving on the ThinkPad passed all 17 checks against this PR source:
both packaged native executables reached main, and removing only plugin-local
libprotobuf prevented main. Native ELF libraries use an origin-only runtime path.
This strengthens native fixture evidence; actual Windows camera/vcpkg/GStreamer
packaging and physical capture remain outside the observed results. One PR (#38)
carries both source lineages. Original parent authorship/coordination and existing
T68 ownership are retained. See docs/evidence/camera-packaging-20261008/receiving-8167c9a.json.


### 2026-10-08 — Reconcile final peer evidence and collect the native fixture

The original contributor explicitly accepted the one-PR receiving plan in PR #38
comment 6056803042. Its published b14a0d4 commit is retained as Git ancestry;
the four maintained fixture files are unchanged, and eleven final qualification
files preserve the independent 17-check and six-group Linux evidence. Original
8167c9a attribution, patch/archive custody and receiving reports remain retained.

The additive pytest wrapper now collects the native linked-library fixture in the
existing Python CI job, with explicit Visual Studio 2022/x64 selection on Windows
and retained build/evidence output. It suppresses expected missing-DLL error dialogs
while preserving and restoring the process error mode. Current main a1b3c966 was
merged without changing the camera source or either fixture. The final combined
Linux collection passed 1/1 tests and 17/17 native checks. New-head hosted Windows
qualification is pending; actual camera/vcpkg/GStreamer receiving remains open.
See docs/evidence/camera-packaging-20261008/receiving-final-integration.json.


## 2026-10-08 — Offline QC gap attribution (ultra-20b27c2e)

QC now retains a versioned per-record gap inventory in `capture.analysis_qc/2`
and displays source, stream, cause, closure, native session times, duration and
reported loss count in the existing HTML report. Existing count/inventory fields
remain available. Decimal strings and integer-only formatting preserve native
nanoseconds; open, missing-end and reversed intervals have explicit unknown
durations. Every listed gap makes its reported source at least `warn`, while an
existing `fail` remains dominant. This asks for coverage review and does not
invent a new device-failure or planned-pause classification.

An actual CLI control on the copied mini-session reproduced a closed 2.5-second
DISCONNECT whose source was still `ok` and whose QC had no warning or interval
details. The paired candidate CLI now warns that source, displays the exact
interval and loss estimate, and leaves all raw input hashes unchanged. The
healthy no-gap control remains `ok`; with `--strict-warnings` it exits 0, while
the gap case exits 2. Both use the project's Python 3.12 package and existing
installed libraries; no substitute implementation, dependency installation,
C++ build, recording or hardware access is involved.

The frozen 25-case regression suite changes from **24 failed / 1 passed** to
**25 passed**. The entire existing `tests/analysis` directory plus those cases
changes from **26 failed / 15 passed / 3 skipped** to **2 failed / 39 passed /
3 skipped**. Both remaining failures require absent PySide6 or Parquet support;
the three pre-existing module skips require absent MCAP. These are retained
qualification limits, not a whole-analysis or hosted-Windows pass. Scoped Ruff,
license checks and `git diff --check` pass. Independent receiving adds **7 passed**
with the current protocol framing dependency; the original gap CLI challenge
still fails while its no-gap control passes. All 98 unowned receiving files and
all 12 raw package hashes per CLI run are preserved. Exact-head hosted gates
remain pending. Raw results, source pins, CLI input/output hashes and receiving
source equivalence are in
`../../evidence/qc-gap-details-ultra-20b27c2e-20261008/`.


### 2026-10-08 — Add actual GStreamer camera qualification

The additive Native camera worker workflow enables the real Windows camera
target with the pinned official GStreamer 1.24.13 MSVC SDK. A test-only absolute
executable selector reuses the existing three camera cases for the original,
plugin and legacy layouts. The receiving runner requires all three cases in
each layout, exact worker/DLL identity, an actual missing plugin-local protobuf
loader refusal, exact restoration, and unchanged source/SDK/binaries.

The SDK is administratively extracted into a fresh hosted-runner directory;
there is no product installation or machine/user environment change. Existing
CI, CMake test registration, worker production source and runtime resolver
ownership are preserved. Portable acceptance controls and independent source
review precede hosted Windows execution; they do not establish a native camera
pass. Physical devices and automatic manifest resolution remain outside this
gate. Scope, reproduction and retained-evidence rules are in
`../../qualification/camera-native-dd84679589d8/README.md`.


### 2026-10-08 — Receive the first actual Windows camera build

The first dedicated camera run (37782737763, actual checkout
`ea99de704be6f9fe5b272be3ff0043680cd89d88`) verified the SDK, passed the 13
portable controls and configured the real camera target. Compilation then
rejected an integer `gboolean` comparison with C++ `TRUE` under MSVC /W4 /WX
(C4805 promoted to C2220). The one-line repair interprets the existing
`gst_element_link_many` result by its zero/nonzero value; the encoder probe
flow and strict warning gate remain intact. Native camera cases did not run.

The standard C++ gate passed 26 CTest and six native daemon/recovery cases.
Standard Python exited zero with 383 passed and six skipped, but its JUnit
declared 448 tests for 389 case entries: 59 successful subtests inflated the
aggregate. The new camera controls now use the same variant loops and assertions
as ordinary unittest cases. A focused pytest 9.1.1 replay reproduces the original
72-versus-13 mismatch and receives the successor's 13-versus-13 report with the
unchanged shared checker. The next hosted run must qualify both narrow repairs.

## 2026-10-08 — Desktop analysis time scope (estate-234cae4aee53)

Issue #53 adds the missing operator path from the sealed-session header to the
existing analysis time-window API: Full session, Checkpoint section, or an exact
decimal-seconds Time range. Checkpoint IDs distinguish repeated names; requested
and resolved bounds remain in the existing job provenance. Cursor mark controls
and a scope outline preserve the visible gap bands. Each threaded job snapshots
the selected scope, and package identity prevents a different session's selection
from applying. Invalid ranges stay blocked across header refresh/navigation.

The UI exposes time scopes only for existing consuming commands and identifies
package-wide QC. Source composition includes current main `72c15d6b`, retaining
the exporter, camera, registry and analysis replacement-preservation owners' code.
Backend jobs, loaders, pipelines and storage are unchanged by this contribution.

Initial real Qt/QThread/MCAP receiving passes 11 cases with one explicit Windows
shell skip; both range and checkpoint jobs preserve exact bounds, derived sample
times and raw bytes. Twelve focused UI admission/refresh cases also pass after
tightening exact decimal parsing and invalid-selection persistence. An earlier
shared-scratch ENOSPC attempt is retained as invalid qualification. Independent
receiving, the frozen final suite and supported Windows CI remain pending.

Independent receiving rejected the initial picker for a real ID/name collision:
an earlier checkpoint name could shadow a later stable ID and select the wrong
interval. The UI now identifies that ambiguous section as unavailable and explains
the Time range fallback, preserving the existing backend resolver. Two focused
controls retain the failure with both checkpoint record orders. The corrected
Qt fixture lifetime also preserves a 30-second timeout/cancellation crash; the
same production source passed 21 focused cases with one Windows skip after the
harness waited for actual worker completion (one plotting job took 36.83 seconds).

Final local qualification on the clean, unchanged `951e3c9` composition with
current QC main `fae29ddc` passes **23 focused UI cases**, with one explicit
Windows MainWindow skip. All 724 tracked source hashes remain unchanged. Lead
independently accepts the repaired checkpoint picker at `3625449`; the original
identity failure and corrected rerun are retained. The supported Windows job
remains required. Source pins, raw control/qualification logs and native custody
are recorded in `docs/evidence/analysis-scope-234cae4aee53/`.


## 2026-10-08 — Selected analysis figures with original provenance (#59)

The native gallery now offers **Export figures…** for the loaded completed job.
Researchers can preview/check an explicit PNG subset, choose a ZIP destination,
and retain the exact original images, job manifest and parameters together.
The versioned bundle index distinguishes actual exported-input digests from
historical hashes recorded inside the original job metadata. Recorded source
identity, gaps, units, warnings and tooling remain intact; export does not
recompute results or make a new scientific/hardware claim.

Source reads, validation, PNG decoding, selection and failed/cancelled export
leave job/session bytes unchanged. The writer stages beside the destination and
preserves an existing export until successful publication; replacement requires
an explicit native confirmation. Clear/reload invalidates the old selection and
cancels its worker. The gallery's public lifecycle composes with #55 saved-job
history without editing its screen/package hooks, and all sync/inspector behavior
remains in its existing implementation.

Local receiving uses the project's Python 3.12 source, actual PySide6/Qt 6.11.2
controls/event loop, and an actual synthetic MCAP analysis job. The original
native gallery has no export action; the candidate produces exact selected PNG
members plus the two original source JSON files and a versioned bundle index.
Tests include selected/empty/invalid/stale jobs, output failure and retry,
replacement refusal/acceptance, native keyboard operation, and clear during an
active worker. Supported-platform CI and independent receiving are recorded
separately in the accompanying feature evidence; local Linux Qt is not Windows,
hardware or installed-app qualification. See [figure export](FIGURE_EXPORT.md)
for the operator workflow, bundle fields and explicit resource/failure bounds.



## 2026-10-08 — Refuse unsupported sync-anchor requests (#63)

The offline job API now rejects `apply_sync_anchors=True` with an explicit
`NotImplementedError` before progress callbacks, review/QC reads, output creation
or replacement of a saved job. Default/false requests retain existing behavior and
truthfully record that anchor offsets were not applied. The scope design keeps its
future alignment contract and now distinguishes that contract from current
availability; recorded anchors remain available to package review and QC.

An actual copied synthetic session exposed the original false provenance: two QC
jobs recognized the same anchor at 250,000,000 ns, but the requested flag alone
changed the saved manifest to `applied:true` with no applied-anchor record. The
paired 17-case suite changes from 6 passed / 11 failed to 17 passed. The candidate
also passes 42 existing QC, destination, replacement and CLI cases; one existing
Windows junction case is explicitly skipped on macOS. Scoped Ruff passes, and the
107 paired source files plus original 97 inputs remain unchanged during execution.

This native comparison uses the already installed Python 3.13.7 scientific stack
and is advisory source execution: the package requires Python >=3.12,<3.13. The
existing hosted Python 3.12/Windows gates and independent exact-source review remain
separate integration requirements. This change does not implement or qualify
feature timestamp alignment, MCAP decoding, desktop controls or hardware capture.

The isolated preparation retained a transient storage failure and a rejected stale
scope-document packet. The final document preserves the complete newly landed
time-picker text. PR46 retains inventory/finalization ownership; its existing
replacement, callback and failure-publication paths are unchanged. Source pins,
original failures, real-job artifacts and receipts are retained in
[the receiving record](../../evidence/sync-anchor-request-bd1abdb2f886-20261008/README.md).

Current finalizer composition: the same two-hunk refusal now receives actual
main `70f34e3b982523b544a9370d2316a1b69d79bd70`, retaining PR46's corrected
final log/manifest inventory and failed-attempt publication. The unchanged
17-case negative comparator still has 6 passes and 11 failures. The composed
candidate passes 66 tests with one native Windows-only skip, including all
seven newly merged output-provenance controls; scoped Ruff passes and all
109 files in each isolated source variant remain unchanged. These are advisory
Python 3.13.7 source results. The existing supported Python 3.12/Windows workflow,
including the real numeric CLI/MCAP cases, and exact-source independent review
remain separate integration gates. The earlier source, failures and evidence
archive remain intact; the current-finalizer archive records all actual artifacts
and records test-created links only as inert metadata.

Current external-prediction composition: the same refusal now receives actual main
`58157fdc1b83a12bb4856ef14b0498cf524a1087`. The newly merged optional
`prediction_path` eval dispatch is preserved exactly. All 17 existing admission
controls pass, as do three bounded real eval groups: the unchanged identity default,
an authored source-bound external prediction input with known errors and verified
output inventory, and refusal before an absent prediction input or saved-job
replacement. Scoped Ruff passes and all 115 receiving source files remain unchanged.
This is still advisory Python 3.13 source execution. It does not decode MCAP or
replace the upstream owner's full pipeline qualification; supported hosted gates
must accept the current composition before integration. The previous finalizer
receiving and both earlier archives remain untouched.

The published source additionally preserves checkpoint and camera integration from
main `9c44354cb101c76beff79265de0040b6839d249f`. The shared job runner remains
byte-identical to the qualified external-prediction composition; the newer
checkpoint resolver and its expanded scope documentation are retained in full.
The native 115-file packet remains pinned to its actual 58157 parent. The complete
current composition requires its own supported hosted qualification before merge.


## 2026-10-08 — External prediction evaluation (chatgpt-566d51f04b31-mac)

Issue #57 owns the optional source-bound prediction input on the existing eval
job. Base e43da3b8 has an intentional identity-teacher simulation. The retained
five Phase 5/6 tests pass on that base; the new actual-pipeline receiver has
26 expected feature/refusal failures and one unchanged simulation control pass.
Native Python 3.12.8 uses the existing analysis dependencies without installation.

Implementation is limited to eval input/scoring/figures, optional CLI dispatch,
the versioned input contract and tests/docs. #46 retains job publication and
inventory; #49 and #53–56 retain their numerical/UI/kinematics scopes. Source
qualification is complete: 158 analysis tests pass and the single native Windows
junction test is skipped on macOS. Scoped Ruff and the license check pass. PNG
and Poppler-rendered PDF outputs are readable; a literal model-label rendering
failure was retained and corrected. The original 26-failure baseline, first
candidate, line-wrap-only AST checks and final native logs are preserved.
Independent receiving, source review and supported hosted gates remain pending;
no model training, held-out design, hardware or clinical result is claimed.


Receiving correction: root source review found a half-ULP Pearson centering
error for two nearly equal reversed samples. The exact native examples at 1.0
and 180.0 both reproduced correlation 0 instead of -1; an ordinary two-point
control passed. Translating each normalized series before mean subtraction
preserves the small offsets without losing overflow resistance. The same two
regressions now pass, as does a finite +/-1e308 identity control. The corrected
full analysis suite passes **161 tests**, with the same native Windows junction
skip and two retained protobuf deprecation warnings. Source matching, masks,
MAE/RMSE, units and default identity simulation are unchanged. Independent
receiving and supported hosted gates still remain separate pending gates.


## 2026-10-08 — Canonical Mac session-doctor receiver (5f566b5ec8ef)

Built and received the already-merged portable C++ session doctor from exact
`d43bdea867d6198a707a5f55e29216c76054517e` on macOS 26.6.2 arm64. Configure,
Release build and all 17 available native CTest cases passed. The 96 qualified
inputs remain unchanged on receiving base `70f34e3b982523b544a9370d2316a1b69d79bd70`.
No product, preset, bootstrap, worker, daemon or schema implementation changes
were needed; the historical Mac port and Linux R3 receiver retain their scopes.

The received package keeps its executable and 86 local libraries together.
Actual relocation traced all 87 non-system images to the copied directory;
CLI controls preserve sealed/finalized data, exercise authored tail recovery,
and retain the original helper filename failure plus its focused loader replay.
Independent review verified all 87 original/copied files and 1,245 local load
edges. The final 2,393,685-byte archive includes exact source inputs and project/
dependency notices; all 246 extracted files match, and the extracted tool runs.
The first archive and its source-notice correction are both retained.

Six pinned files in the older Mac receiver remain byte-identical. No real
recordings or hardware were accessed. Mac evidence does not include the Linux
GNU linker-wrapped cases, Windows, complete Mac UI/daemon, x86_64 or notarization.
Native artifact paths, exact hashes, recipient usage, raw qualification and
independent review are in
[the receiving packet](../../receiving/macos-session-doctor-5f566b5ec8ef/README.md).


## 2026-10-08 — Desktop analysis source selection (estate-234cae4aee53)

Issue #62 adds All recorded sources / Selected sources to the Analysis workbench,
using exact discovered descriptor IDs and the existing JobParams.sources path.
The native chooser preserves explicit choices across refreshes, blocks empty or
vanished subsets, and keeps package-wide QC visible. Each worker snapshots the
source IDs before starting; the separate time scope composes unchanged. Source
selection is available only to the existing consuming commands.

The original clean 2f4dcf3 parent fails the actual Qt missing-control gate while
the same fixture verifies the review-folder / analysis-descriptor identity
difference. An earlier standalone baseline produced a completed numeric job but
did not return from its Qt lifetime; that incomplete attempt is retained without
a UI or raw-preservation pass. The candidate's focused actual-chooser/thread/MCAP
gate passed at 7b2c999 (10 passed, one explicit Linux MainWindow skip), with all
886 source files and all raw package hashes unchanged. The same real QEventLoop
receiver completes on the untouched parent and candidate; only the test wait
mechanism changed.

Frozen Windows diagnostic 37809372315 passed 490 tests with six explicit daemon
skips in 194.36 seconds, including all 11 source-selection cases and MainWindow.
It changes observation only, retains the 300-second deadline, and skips CMake
only on its diagnostic branch; it is not the ordinary full PR gate. The prior
300-second timeout and its raw evidence remain distinct. Independent actual Qt
receiving also reproduced and accepted a test-only early-timer chooser repair;
one explicit early-delivery regression now guards that helper. Current main's
checkpoint, sync-request refusal and camera changes compose without changing
either accepted source-selection production blob. The ordinary Windows gate
on the complete union remains pending. The offscreen Windows screenshot has
missing glyphs; readable Windows presentation is not claimed.

Shared-screen edits stay within control construction, existing package_loaded
signal wiring, source admission, and worker parameter handoff. Package lifecycle,
history/selection/completion, backend jobs/pipeline, galleries and raw storage
remain with their current owners. The ownership fence is coordinated in #55 and
HAMON #140. Details: ANALYSIS_SOURCE_SELECTION.md and
docs/evidence/analysis-sources-234cae4aee53/.

## 2026-10-08 — Native external-prediction evaluation (#69; HAMON 6e5752b49b6f)

The native Analysis workbench now exposes the existing #57/PR65 evaluator with
an explicit **Evaluation input** choice. **Identity teacher (simulation)**
retains the original default. **External predictions file** offers a native
file chooser, literal read-only path, Clear and actionable missing-file errors.
It sends the ordinary prediction_path job extra without replacing evaluator
admission, source binding, scoring, schema or publication. Source and raw files
remain read-only. See [the operator guide](EXTERNAL_EVALUATION_WORKBENCH.md).

Chooser cancellation preserves the current choice. A new session clears the
file; command/mode changes preserve it within the same session. Revision checks
retire file dialogs whose context changed while they were open. The worker
captures scalar request values, while the evaluator admits and retains the
actual input bytes when it runs. No file-byte snapshot or trained-model
execution is implied by a selection.

Native receiving exposed two separate workbench findings. The first candidate
clipped its new controls under vertical pressure, so the unchanged control
column now lives in a native scroll area. Keyboard controls, wrapped text and
Run/Cancel remain reachable without forcing a taller Analysis window. An
independent held-worker check also proved the parent's Run/Cancel state used
isRunning before thread.start and never resynchronized. The shared screen hunk
now treats a reserved worker as busy and rejects any duplicate start while it
is reserved; the existing worker/cancellation/job lifecycle is unchanged.

The original absence capture, functional source, clipped images, inherited busy
counterexample and receiver-only corrections remain distinct in qualification.
Local Python 3.12.8 / PySide6 6.11.2 receiving uses actual Qt dialogs and QThreads,
real external/identity/refused jobs, retained-file and output-inventory checks,
and keyboard reachability at 1100×700 and 1280×960. The actual MainWindow imports
Windows named-pipe APIs before its auto_connect=False guard, so its minimum-size
case is a supported Windows CI gate, explicitly skipped on Mac. No Windows
hardware, OS-native dialog, model authorship or scientific efficacy claim is
made from the local fixture evidence. Independent receiving and hosted results
are recorded separately with their exact source identities.


### PR84 Windows chooser receiving correction (2026-10-08)

The first ordinary Windows gate timed out before JUnit. An isolated unchanged-source full-order diagnostic identified the actual Qt test helper stripping a significant leading filename space, then waiting inside a file-not-found QMessageBox. Production chooser behavior is unchanged. The helper now uses verified literal filename entry and independent bounded modal cleanup, with an actual missing-file unwind regression. The normal 300-second runner and selection remain exact; a read-only post-Pytest step prints and checks the actual named MainWindow and chooser JUnit cases. Original failure and diagnostic evidence are preserved in `docs/evidence/analysis-predictions-windows-correction-6e5752b49b6f/`; supported Windows acceptance remains pending until that actual successor gate completes.


### PR84 exact Windows diagnosis and current picker composition (2026-10-08)

The second unchanged-source diagnostic separates three actual failures and a later inherited receiving stall: inline CI observation violated the one-command contract; even quoted filename entry lost significant leading space through Qt's model; MainWindow's global checkpoint Space shortcut consumed native Clear activation; the existing scope-test QTest.qWait loop stalled a real plotting worker. Original ordinary and diagnostic failures are retained, not relabeled. The next candidate uses the independently received actual file-view selection approach, retains bounded modal cleanup, protects only unmodified Space on a focused descendant Analysis QPushButton, and preserves global shortcut behavior in a real countercontrol. JUnit observation moves to one explicit Python command. The scope wait correction is independently owned and preserves its original receiving assertions/bound. The full current source picker and current progress text are preserved in this composition. The unchanged ordinary300-second Windows gate must qualify the resulting exact checkout before adoption.


### PR84 exact file-model boundary and owned scope receiving (2026-10-08)

The unchanged-source Windows probe directly distinguished the literal OS filename from Qt6.12 widget-model normalization. Successful real chooser receiving now uses a representable Unicode/internal-space filename; the original leading-space fixture separately requires exact identity or bounded refusal with prior path unchanged, recording the actual branch in JUnit. No product path normalization or native Windows-dialog claim is introduced. The exact owner-authored PR79 scope wait blob817412fe is adopted with estate-7879c2abc07f credit, preserving every existing bound/assertion and excluding its unrelated QC source. The current picker, narrow focused-button Space correction, one-command read-only JUnit gate, original failures and native receiving packets are preserved. Ordinary full-suite Windows acceptance is still pending for this exact composition.


## 2026-10-08 — Native recorded-video segment review (chatgpt-0378a7b6b7c2/mac_product)

Issue #89 adds explicit retained-video selection, play/pause and seeking to Review.
Source/stream/package-relative identities distinguish equal segment filenames.
The media clock is segment-local; there is no inferred camera/checkpoint alignment,
gap interpolation or audio playback. Native asynchronous signals are guarded by
player identity and selection generation. Missing/invalid media, changed/failed
package loads and hidden views retire or pause the old media with actionable state.

The original actual Review screen loaded a two-stream, four-file synthetic package
and had no playback controls. The candidate's real Qt decoder received red/blue/green
frames, explicit pause and 1500/2000 ms seek. All 15 focused model/UI cases passed;
the complete inherited UI suite plus new model cases passed 151 tests in 256.11 s.
Independent MSI review accepted the exact three production hashes and a distinct
six-group native oracle: rapid A→B→A, 14 retired-player signal emissions, independent
identity/generation challenges, fractional seek despite a large checkpoint clock,
error/reload and failed-package retirement. First receiver/setup failures remain
retained separately from successful observations. Original source leaves outside
the seven-line Review hook and every original raw fixture byte were preserved.

Readable dark/light/compact control captures and actual decoded QVideoSink pixels
are qualified separately: offscreen QWidget captures omit the GPU video surface,
and a Windows-platform HWND grab returned an entirely black image. Onscreen GPU
presentation is not claimed. The standard native QVideoWidget renderer remains
unchanged. Existing supported hosted Windows Python and C++/native gates and final
current-main receiving remain required before integration. See
[operator steps](../../operator/RECORDED_VIDEO_REVIEW.md) and
[full evidence and limits](../../evidence/review-video-0378a7b6/README.md).

Follow-up actual MainWindow receiving found the existing global checkpoint Space
shortcut consuming the new focused Play button. The original failure is retained.
A narrow viewer-local unmodified-Space override on its three buttons now passes
24 native model/video/desktop cases, including actual application toggle/play/
pause/reload, C and Ctrl+Space countercontrols, outside-viewer checkpoint routing
and unchanged raw fixtures. The original 151-case and independent lifecycle receipts
remain at their historical source pins. App shortcut source and PR84 ownership
remain untouched; final hosted gates are required on this corrected successor.


## 2026-10-09 — Two retained recorded frames (#112; estate-db371a37f4c8)

Scoped native extension on accepted #103 source custody 9befdad4, preserving all
repeat/rate behavior and current main3960c0c7 ownership. The public pre-code contract
and panel-placement clarification are in #112. The existing read-only Windows
Python3.12.10/Qt6.12 runtime was re-admitted across18,539 exact files;132 original
source/fixture files match their canonical Git tree.

Original native receiving establishes real decoded frame copies and presentation
transforms before candidate code. An initial environment-variable identity guard,
wrapper syntax error, literal source-ID assumption and wrong fixture-color
assumption are retained with the corrected original observations. No product
repair is inferred from those author-observer failures.

Candidate implementation is private and independent receiving is pending.
Author model/actual-Qt gates and exact source proofs are recorded separately as
they complete. No source ref, PR, main/tag/dispatch, shared runtime installation or
GitHub Actions is part of this work. Original package bytes remain read-only.


### 2026-10-09 08:50 UTC — Author native qualification

The private Windows / Qt 6.12 candidate passed 19 maintained checks: native image
orientation/copy/budget cases and actual decoder, pair-retention, playback, lifecycle
and shortcut journeys. All 140 selected source files were byte-identical before
and after the gate; all four recorded native PIDs were absent at delayed closure.
Dark and light 720×620 comparison captures were read directly and show both images,
literal identities and separate frame/player clocks without clipping. These are
author results; independent original-first receiving remains pending. Earlier
observer/transport negatives and the unchanged #103 bodies remain in custody.
