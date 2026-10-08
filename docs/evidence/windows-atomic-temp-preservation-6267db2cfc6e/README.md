# Windows atomic temporary-file preservation — initial regression control

**Status: prepared; native Windows compilation and execution are pending.**

This initial draft adds four real-file Windows C++ tests against the existing
linked `capture::storage::atomic_write_text` implementation. It carries no
production repair and makes no Windows runtime pass/fail claim.

## Source binding

- Publication parent: `72c15d6b623e217291a824e4e4808a385df896a9`,
  tree `221cf5c7bb3c3392a7c4186ba0bcf5a8664135d1`.
  This parent contains PR48's received analysis-preservation merge and PR30's
  later export merge. The bounded Windows defect is tracked as issue #51.
- Unchanged atomic writer: Git blob `e192b9bac50f9a1f1ed35d57f2da60e9488fbb73`,
  SHA-256 `912700935decf0bdf9cc4eee5bcd3f7d5aadfddf70d16de7a2cc0a5168ac8fec`.
- Its original Windows branch is 642 bytes, SHA-256
  `3863dbcb449eec9ca9b59386ab360565989a8a7d368d5078cbf512d125717e8a`.
- New regression SHA-256:
  `485af6482c6b14fc7c187b45cc366af547bf0a1fe2c0651c8b68c8d25e854cfb`.
- CMake adds this file only to the existing WIN32 source list. The original
  CMake blob is `21d82500d89550d9aa8fc2f395a13daaefe58a95`;
  candidate SHA-256 is
  `e29ab4a5ab82cef91492317ee43d5ed99f866816af5facd1b10d2616f7ab6d0a`.

## Receiving checks

| Fixture | Required result |
|---|---|
| `manifest.json.tmp` hardlinked to authored raw bytes | Publish a regular new manifest while retaining raw bytes, Win32 identity and the existing alias |
| Temp name hardlinked to the prior manifest; a live handle omits `FILE_SHARE_DELETE` | Report publication failure while retaining prior bytes, identity and alias |
| Ordinary existing file at the temp name | Publish the manifest without consuming or rewriting that file |
| Temp name symlinked to authored raw bytes | Preserve raw bytes, identity and the original symlink while publishing a regular new manifest |

Each case reserves its own directory through `CreateDirectoryW` and checks the
complete resulting filename set. The symlink case skips only
`ERROR_PRIVILEGE_NOT_HELD`; all other setup errors fail. The existing Catch2
discovery helper maps the framework's skip exit code to a CTest skip.

## Planned native qualification

Run the existing supported Windows configure/build and CTest workflow without
changing its gates. The focused selector is:

```powershell
ctest --test-dir build/windows-release --output-on-failure -R "^Windows atomic" --output-junit windows-atomic-baseline.xml
```

The baseline is expected to expose corruption because the current writer opens
the predictable temp name with truncation. This remains a source prediction
until the actual compiled test reports the preservation assertion failures.
A compiler, fixture-creation or unrelated workflow failure is not that evidence.

Retain the actual tested commit/tree, source/test hashes, raw CTest output and
available JUnit evidence from the original-source run. The separately reviewed
repair must pass these exact test bytes and the existing full Windows/native
suite. Native acceptance requires actual preservation assertion failures on
the original source and passing execution on the repair.

The two CI builds may overlap only after the baseline run has an independently
bound immutable checkout and its CMake checkout is complete. A completed Python
job from the same run and attempt can establish the expected source for
scheduling when the live CMake log is unavailable; this remains an explicit
inference until CMake's own checkout log is received. Preserve both commits,
run IDs, attempts and checkout trees. A candidate update never substitutes for
the original run's actual native result. The existing workflow is unchanged.

These are direct-library checks on disposable authored bytes, not an execution
of the real recovery CLI against valid MCAP, an installed release, or physical
capture. POSIX implementation and the separately owned storage-fixture repair
remain outside this regression-only contribution.
