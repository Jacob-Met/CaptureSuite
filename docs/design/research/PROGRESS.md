# Agent progress log

Agents: **read at session start, update at session end.**  
Plan: [AUTONOMOUS_EXECUTION_PLAN.md](AUTONOMOUS_EXECUTION_PLAN.md)

---

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
