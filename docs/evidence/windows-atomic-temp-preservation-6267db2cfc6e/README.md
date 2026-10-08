# Windows atomic temporary-file preservation

This contribution repairs the retained-file defect tracked in [issue51](https://github.com/Jacob-Met/CaptureSuite/issues/51). Its unchanged-production checkpoint and repair use the same four real Windows filesystem controls. The authoritative native receiving record is the final review and the separately identified runs in [PR52](https://github.com/Jacob-Met/CaptureSuite/pull/52).

## Source identities

| Role | Exact identity |
| --- | --- |
| Original-source checkpoint | Commit `c1bc438ea07492a303f89cea5deb242efeb6f8e9`, tree `462ebfecaf9fcd14d96eb75ab527798d81ba5ad2` |
| Baseline CI | [37770868596](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37770868596), expected checkout `e4a8f294ab66ee6af9a4f91fcf9f70a7528f3362` with the same tree |
| Original atomic writer | Git blob `e192b9bac50f9a1f1ed35d57f2da60e9488fbb73`; SHA-256 `912700935decf0bdf9cc4eee5bcd3f7d5aadfddf70d16de7a2cc0a5168ac8fec` |
| Repaired atomic writer | Git blob `d51815e9f95ec6e3cf1b319386efb44b5bb4ac94`; SHA-256 `e5f67fb5c83c73b7a31503f1689303737cd00b48ae764553127b5a3c68be12f6` |
| Frozen Windows test | Git blob `43fe28c3ec2ed49872b59dcc87407cece56466e5`; SHA-256 `485af6482c6b14fc7c187b45cc366af547bf0a1fe2c0651c8b68c8d25e854cfb` |
| Windows CMake source-list addition | Git blob `7ce82c0a97098feef2691a675725ee31e4f92f01`; SHA-256 `e29ab4a5ab82cef91492317ee43d5ed99f866816af5facd1b10d2616f7ab6d0a` |
| Existing CI workflow | Git blob `9c08a4d38d435169f402511c934d1c59701082cf` |

The baseline parent is `72c15d6b623e217291a824e4e4808a385df896a9`, after the received analysis-preservation and export changes. Full-tree reconstruction binds the original four-file checkpoint without changing production. The repair is a normal descendant of that checkpoint; its full commit/tree and actual executed checkout are recorded by PR/CI receiving.

## Repair behavior

The Windows implementation reserves a unique sibling using `CreateFileW(CREATE_NEW)` and keeps its original writable handle through `WriteFile` and `FlushFileBuffers`. It checks close and uses the existing `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)` publication boundary. Failure cleanup addresses only the newly created temporary file. A retained `path.tmp` is never opened, rewritten, renamed or cleaned up by the repaired writer.

The POSIX branch and shared tail remain byte-identical. The explicit span from the function's #else directive through end of file is 4075 bytes, SHA-256 `876c63d0c36c9f2a2967dbfa9e43e8dc3e8ecfc2534a1d97b621f18cefe0f547`. Contract comments describe the same one-writer boundary. This change does not add a concurrent-writer or crash-recovery protocol.

## Native controls and acceptance

| Actual Windows fixture | Required behavior |
| --- | --- |
| Legacy temp name hardlinked to authored raw bytes | Preserve raw bytes/identity and the alias; publish an independent regular manifest |
| Temp name hardlinked to the prior manifest, with a held handle denying delete sharing | Report publication failure; preserve prior bytes/identity and the alias; clean up only the owned temporary |
| Ordinary retained file at the legacy temp name | Preserve its bytes, identity and directory entry |
| Temp name symlinked to authored raw bytes | Preserve raw bytes/identity and the original link while publishing a regular manifest |

Every test reserves its own directory through `CreateDirectoryW` and compares the complete final filename set. Only `ERROR_PRIVILEGE_NOT_HELD` may skip the symlink test; other setup errors fail. The existing Catch2 discovery helper maps a framework skip to a real CTest skip.

Use the existing supported Windows configure/build and CTest workflow. A focused selector after building is:

```powershell
ctest --test-dir build/windows-release -C Release --output-on-failure --no-tests=error -R "^Windows atomic" --output-junit windows-atomic.xml
```

Acceptance requires successfully compiled and executed preservation assertion failures on the unchanged writer, followed by passes on the repair with exactly the same test bytes and the complete supported CI gates. A compiler, setup, dependency, cancellation or unrelated-test failure is not an accepted negative control. Preserve each run ID, attempt, actual checkout commit/tree, source hashes and raw output.

The builds may overlap only after the original run has a bound immutable checkout and its CMake checkout has completed. A completed Python job from the same run/attempt can support a scheduling inference when live CMake logs are unavailable. Native acceptance still requires the CMake job's own checkout and actual test evidence; the Python inference never substitutes for it.

These are direct-library checks on disposable authored bytes. The existing native daemon/recovery suite supplies integration coverage; the new controls do not themselves run a recovery CLI against valid MCAP or exercise physical capture. Write/flush/close error handling and the bounded temporary-name collision loop also received source review; the four controls do not inject each of those failure modes.

## Received native checkpoints and current-main integration

Original checkpoint `c1bc438ea07492a303f89cea5deb242efeb6f8e9` was received
from workflow 37770868596: successful warning/configuration/build gates, then
25 CTest passes and four actual preservation failures, zero skips. The
native daemon integration step did not execute after that CTest failure.

Repaired checkpoint `62c56178820e4248bc4013c21f33f44cc1dce2fe` was received
from workflow 37771818309: 29 CTest passes, including all four unchanged
Windows controls, plus six native daemon/recovery passes, no native skips.
Both checkpoint Python jobs passed 303 tests with six daemon-not-built skips.
The native receipt records a dirty worktree at entry and unchanged working
source during execution; the Python receipts record clean, unchanged source.

The exact full native job logs and independent receiving are retained here:

- [Original CMake job log](receiving/baseline-cmake.log)
- [Repaired CMake job log](receiving/candidate-cmake.log)
- [Independent native receiving](receiving/native-receiving.json)
- [Tagged Catch2 skip-semantics review](receiving/catch2-skip-review.json)

These files describe those two exact checkpoints. They do not claim a run
of the subsequent composition onto main `e43da3b855475c8aacf815c201fa03eddaeec0f1`.
That main adds PR42's private-temporary-directory fixture. The composed
CMake list preserves the frozen Windows source entry and the new aggregate
fixture. Its one additional supported workflow must execute the four
individual Windows controls and `capture_storage_fixture_isolation`, followed
by the ordinary native/Python gates. The original defect control is complete.
