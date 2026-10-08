# Analysis job preservation receiving evidence

Issue: [#39](https://github.com/Jacob-Met/CaptureSuite/issues/39)  
Worker: `estate-6267db2cfc6e`

## Problem and resulting behavior

An explicit overwrite ID could escape the analysis namespace or follow a linked
output directory into recorded or unrelated files. Replacing an existing job also
deleted the prior result when analysis failed, and could delete it before a
failing promotion rename. These controls use copied, authored session fixtures.

The change validates portable, visible job IDs and existing output path components
before output creation. Replacements are prepared in uniquely owned, hidden
attempt directories. Cancellation and progress callbacks finish before publication.
Publication retains the prior directory in an owned backup and restores it if
promotion fails. If restoration is also blocked, the error identifies the backup
containing the prior result. Failed attempts keep matching directory/manifest
identities, failure records, and their original overwrite intent. Cleanup after a
successful publication cannot change the new job to failed.

The CLI includes standard exception notes after its existing failure diagnostic.
The actual desktop worker carries the notes to the log and ordinary failure
dialog. Cancellation retains its quiet behavior and logs any retained path.
Hidden replacement attempts remain outside the desktop dependency selectors.

## Exact inputs

The original negative-control source is `c43b2819b149e1e87d7f957d8b3583881c29ffb4`
(tree `befabb7f507780a2e4d720ac0ae841327c352df8`).
The publication incorporates main
`52203f5ceedfa0da8f1813e700a41ec8c364263e`
(tree `48a04593f0415a92e0176377da93bbebda68d63d`), including the newly merged
stream-scoped gap implementation and its eight tests. The jobs and consumer
baseline files are unchanged between those two revisions.

The core source checkpoint was published as
`a3356bfec97a2e2aa7ba804ea6306c564c3b7466`.
[receipt.json](receipt.json) binds the exact production, test and analysis-document
bytes by Git blob and SHA-256. The enclosing Git commit binds this receipt,
the progress update and raw logs to the complete composed repository tree.

## Fresh execution results

| Check | Source | Result | Raw output |
| --- | --- | --- | --- |
| Nine replacement fault/success controls | Original | 7 failed, 2 passed | [baseline-replacement.log](baseline-replacement.log) |
| Portable IDs and output destinations | Original | 21 failed, 4 passed, 1 native Windows skip | [baseline-destinations.log](baseline-destinations.log) |
| Phase A, destinations, replacement, actual CLI and current stream-gap tests | Composed candidate | 50 passed, 2 skips | [composed-candidate.log](composed-candidate.log) |
| Seven changed Python files | Composed candidate | Ruff passed | [ruff.log](ruff.log) |

The two candidate skips are explicit: the Windows junction case and the real Qt
module, because PySide6 is unavailable in the local runtime. The CLI tests launch
the real command in subprocesses; the desktop tests use actual Qt signals,
widgets and dialogs when the supported dependency is installed. They do not
replace Qt with a fake implementation.

The replacement cases check whole prior-result trees and raw-source bytes across
partial output failure, cancellation after a real report write, manifest and final
progress callbacks, promotion failure, failed restoration, successful replacement,
post-commit cleanup failure, and a newly created failed job. The failed attempt's
manifest, parameters, logs and output hashes are inspected.

The destination cases cover traversal, absolute paths, alternate stream/device
names, hidden/internal IDs, links through each output component, dangling links,
ordinary generated/named/Unicode jobs, and a linked package root. A native Windows
junction case remains in the same required test file.

## Receiving and acceptance boundary

Separate agents authored the destination guard and replacement fault controls,
and reviewed the combined source and consumer behavior. These are independent
agent checks under one authenticated GitHub account; they are not an external
maintainer approval.

The consumer receiver also ran the original CLI against the repaired backend:
one test failed specifically because stderr omitted the retained attempt path,
while the plain-failure control passed. The repaired CLI passed both cases.
See the fresh [consumer receipt](consumer/receipt.json),
[negative control](consumer/baseline-cli.txt), and
[candidate output](consumer/candidate-cli-and-ui-collection.txt).

Full supported Windows CI on the actual published composition remains the
acceptance gate at the time of this receipt. Its result and the final integration
readback belong in the PR conversation. No hardware, crash-recovery or
simultaneous-writer guarantee follows from these fixture checks.

A scratch relocation error removed earlier local copies. Source was restored
from retained tool records and its exact pre-loss core hash was verified. Every
raw log listed here is a fresh execution after restoration. Earlier lost logs
and receiving archives are not represented as recovered.
