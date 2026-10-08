# Portable saved-job file reads

## Actual Windows negative

PR82's original head `1980c6920001a57f9cdbc496d9f1e3c4f54134ae`, tree
`740ecde94a150708efb24e5f85bb7fe2fb0b1881`, was tested by the existing full
[Windows run 37810614471](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37810614471).
Its actual checkout `029a53642c351c44659be1bdca8f2a79c7d60de6` has that
same tree and parents `a2fd6c58ccc97c7262b97570a85d8aae8dfb978c` and
the published head.

The Python 3.12.10 job `113426182230` completed with **565 passed, two
failed, zero errors and six pre-existing missing-daemon skips**. The process
returned 1; its test wrapper correctly refused acceptance. The actual pytest
process completed in 287.63 seconds, so this was not a timeout. The unchanged
tests exposed two consequences of the same saved-file reader defect:

- Restoring the exact original `params.json` bytes did not permit an explicit
  reload because the reader reported that the file changed while being opened.
- The native comparison dialog's explicit Reload action consequently left its
  table empty after those original bytes had been restored.

All other cases, including the existing real QC producer, completed without a
failure. The JUnit digest is
`e74d3b829b7318e7085a4dea2718837c71b03897edc566c5c70682c3de629b3c`.
The complete source was unchanged during the test. The separate CMake job
`113426182991` passed 30 CTests and six real daemon/recovery integration cases.
That native job's receipt records its build-time dirty worktree and unchanged
source during receiving; it is not relabelled as a clean checkout receipt.
These successes do not override the failed Python gate.

## Receiving boundary and correction

The old reader compared a complete `Path.lstat()` metadata tuple with a
complete `os.fstat()` tuple. Official CPython 3.12.10 Windows code gives their
`st_ctime_ns` fields different meanings: path stat copies creation time into
ctime for compatibility, while descriptor stat returns the file's change time.
A rewritten, stable regular file can therefore fail that cross-API equality.
The exact primary source is
[win32_xstat](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c#L2138-L2150)
and the descriptor conversion in
[fileutils.c](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c#L1107-L1131),
called by
[_Py_fstat_noraise](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c#L1232-L1291).
[CPython issue 157671](https://github.com/python/cpython/issues/157671) reports
the same API distinction on official Windows 3.14 builds. Those reported
versions remain distinct from this PR's actual 3.12.10 hosted result.

Only `_read_regular` changes in the production successor. It matches device and
file IDs across path and handle APIs. It compares all five existing metadata
fields—including size, modification time and change time—between the handle's
before/after snapshots and separately between the pathname's before/final
snapshots. The final pathname snapshot is taken after closing the handle, so a
replacement at that boundary is refused even when its bytes are identical.
Regular-file admission, bounded reads, no-follow/nonblocking flags where
available, byte-count validation and explicit failures remain in place. There
is no sleep, automatic retry, suppressed error or weaker test expectation.

| Successor input | Git blob | SHA-256 |
| --- | --- | --- |
| `analysis_job_comparison.py` | `a8496ac1e07ef649ba5d8b750ea72db45214d408` | `3fcc013cedffba87cdfdf105f80502b60bcfdca8c298e6b8feb20da2348d0966` |
| New `test_analysis_job_file_reads.py` | `518fb9f79ab3a3ea3817b8a36a6b9450ef1198af` | `2f862646186213e4f9ad4ec1427011fc009887be86bd112b4181776f2d159372` |

The dialog, shared JobInspector module and original 45-case comparison test
module retain their exact `bd0adca4`, `3d9e2a58` and `81e931c5` identities.
Both original retry assertions remain unchanged.

## Paired author qualification

The same frozen four-case reader probe first ran on published helper
`db744e87`: **two failures and two passing preservation controls**. A stable
file with the documented distinct path/handle ctime values was rejected, and
a real pathname replacement after handle close was incorrectly accepted.
The controls confirmed rejection when the handle metadata changed during the
read or another file was opened after path inspection. The corrected helper
passes all four cases with zero skips.

The existing GUI/API module and two existing Workbench controls then pass
**46 cases with zero skips** on the successor. Its one real QC producer case
is deliberately deselected in this bounded local replay; the complete original
test module remains selected by the unchanged full hosted workflow. No extra
producer execution is represented by this replay. These local results use
Linux Python 3.12.14 with native PySide6/Qt 6.11.2 and preserve all five frozen
source/test files before and after execution. The clock distinction is an
explicit simulation in the portable test; pathname replacement uses real files.

## Independent successor receiving

Root's separately authored six-case standard-library probe ran on the primary
Windows machine with its existing **Python 3.13.15**. It reproduced two failures
on exact original helper `db744e87`: restored original bytes were still rejected,
and an identical-byte different file substituted after handle close was accepted.
Four preservation controls passed. The same frozen probe passes **all six cases
with zero skips** on exact successor `3fcc013c`, including actual before-open
replacement and actual same-size in-read mutation with the original mtime restored.
Both source and probe hashes stayed unchanged during native execution.

The original native receipt is SHA-256
`53d296ad73aff18dd3c01235bf75f206cacca89c8f4d6c683ecdda2cbf8897c2`;
the successor receipt is
`8b2234ceb4d48a996867cc28359eea6ab14b82146689864019c32a6bf19a318d`.
This is a standard-library receiving diagnostic, not installation of CaptureSuite
under Python 3.13 or a substitute for its supported hosted Python 3.12 gate.

The root receiver then replayed its unchanged Linux native Qt probes on the
exact `3fcc013c` / `bd0adca4` / `3d9e2a58` components. The keyboard/API probe
passes **16/16** and the legacy-wrapper probe **5/5**, with zero failures, errors
or skips, on Python 3.12.14 and PySide6/Qt 6.11.2. Source remained unchanged.
Their distinct receipt digests are
`b28df3cd0bb638ea2350d9edd0febc2679e0b66db3dd521cbc9897df6f753a84`
and `2742a2322a6952b90c007ca3fd95d891fb7a8928a8fdee50b8397a9368943e46`.
Root accepted the corrected source for normal publication; full current-composition
Windows CI remains the integration gate.

The separate [root qualification](root/windows-successor-QUALIFICATION.md) is
an exact readable copy of its capsule member. The unchanged
[root successor capsule](root/windows-successor-independent.json.gz) is 53,062
bytes, SHA-256
`29f4f93cc78992d6d5ffe8ccb173dd6a868664e37be69e0fa59a50aa49ae753b`.
Its [manifest](root/windows-successor-independent.manifest.json) records all 21
members and 140,451 original bytes. Each member's `data_base64` was decoded and
verified against its exact length, SHA-256 and Git blob identity after adoption.

## Exact evidence and integration boundary

[windows-reader-author.json.gz](windows-reader-author.json.gz) contains 33
losslessly retained members: both complete original hosted job logs, actual
runner receipts and artifact metadata, exact original/successor source,
paired reader logs and JUnit, the unchanged GUI/API replay, official source
snippets, and the current-parent intake. Decode each member's base64 `content`
and check its size, SHA-256 and Git blob identity against
[the index](windows-reader-author-index.json).

| Object | Bytes | SHA-256 |
| --- | ---: | --- |
| Compressed author capsule | 352,393 | `17acfea120f5ab31fed7204cd5b582043cdd0448a77c02e7fc7d4a206a28c1e1` |
| Decoded capsule JSON | 1,580,143 | `6902a0a508cc0f906da773f4350a14b0ab78a308b610f9992c0278fc745f3368` |

The existing original author and independent native capsules remain unchanged.
The original Python artifact is `11564593989`, 1,612,762 bytes, digest
`669aab1d3818a8f28c1b3f47df527c7b4d1de50482925affe381c15f081e00ae`;
the C++ artifact is `11565513221`, 287,020 bytes, digest
`e97b64e03abc9c3e6c00b2aeb363c1a62bc68c775896fa13ea6d331d15ae8e60`.
Those are API metadata and upload-log facts. Artifact ZIP contents were not
downloaded or inspected; the prior normal-download 403 restriction was
respected without alternate authentication or download routes. Full decoded
job logs are retained independently of those archives.

Current source intake `11cc78297d8d214407aea693548af4de855d61da`, tree
`2704707993e09393fa6b7d8f319ff0b58d6a2dfc`, carries the independently
owned sync-anchor admission and truthful ML-bundle metadata integrations.
Their full source, tests, evidence and progress text are preserved. Neither
changes the saved parameter serializer/digest, desktop modules or CI workflow.
The earlier local and hosted results retain their actual producer/source pins.
The independent successor receiving above accepts the bounded source change.
The actual published-head Windows workflow remains required before integration.
