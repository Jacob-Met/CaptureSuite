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

# Agent progress log

Agents: **read at session start, update at session end.**  
Plan: [AUTONOMOUS_EXECUTION_PLAN.md](AUTONOMOUS_EXECUTION_PLAN.md)

---

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
