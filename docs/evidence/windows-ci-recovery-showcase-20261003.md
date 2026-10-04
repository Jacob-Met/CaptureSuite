# Windows CI recovery in CaptureSuite

**Published:** 2026-10-03  
**Project:** [CaptureSuite](https://github.com/Jacob-Met/CaptureSuite), independent research software.  
**Evidence:** [merged PR #7](https://github.com/Jacob-Met/CaptureSuite/pull/7) · [hosted Windows run #34415543635](https://github.com/Jacob-Met/CaptureSuite/actions/runs/34415543635)

## The problem

The Windows-first capture platform had failure modes that could make CI look healthier than the underlying build: generated-code drift, native build prerequisites, warning-boundary changes, cleanup failures, and daemon-recovery behavior all needed explicit checks. The goal was not to make the workflow green by skipping native work or weakening compiler/test gates.

## What changed

Merged PR #7 restored the hosted Windows CI path and added evidence-preserving gates. The native phase binds the built executables by SHA-256, isolates test session and local-data state, forces simulator-only source enumeration, and checks sealed segment bytes across a forced daemon exit and `session_doctor` recovery. Missing native build inputs are rejected instead of silently treated as a passing native test.

The pull request records the exact candidate head (`5aff494d1ef627689b63cf6d49e74078571e57cf`) and merge commit (`fcb731faa5f46df5a31215621365b039478283f8`). GitHub's current check readback for run #34415543635 shows both hosted jobs—`python` and `cmake`—completed successfully. The merged PR's published report records 198 Python passes, six explicit daemon-unavailable skips, zero Python failures/errors, CTest 22/22, and six dedicated simulator/core native integration tests passing with no skips or failures.

## Evidence limits

This is one hosted Windows CI run for one candidate. It demonstrates the recorded build/test path, not physical-device validation, clinical or research-result validity, performance, production deployment, customer value, or independent authorship/review. The implementation was AI-assisted. The PR also preserves a native receipt marked `source_worktree_dirty` because `run-vcpkg` created an untracked nested checkout; the report says its source-manifest comparison found no differing source-file hashes. That caveat remains visible rather than being rewritten away.

The project README documents a separate synthetic, offline QC demo; neither that demo nor this CI run should be read as evidence of a customer deployment or hardware study.
