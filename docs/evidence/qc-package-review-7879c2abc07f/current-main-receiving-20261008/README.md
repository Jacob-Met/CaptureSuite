# QC package review: current-source receiving and custody

This directory preserves the QC package review contribution for [issue 74](https://github.com/Jacob-Met/CaptureSuite/issues/74) and [PR 79](https://github.com/Jacob-Met/CaptureSuite/pull/79), including its exact historical Windows gates and the later native component receiving against a current-main composition.

The composed product is implemented and its scoped native receiving is accepted. **PR 79 is not merged, its source branch has not been updated, and current-source full Windows acceptance is not claimed.** The active [no-GitHub-Actions direction](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6067592767) holds those triggering steps while preserving the required gates.

## Product and source

The explicit `python tools/review_qc_packages.py --output NEW_DIR PACKAGE...` command reviews one to 32 selected finalized or recovered session packages. It produces an external ordered index and exact native QC reports, preserves duplicate session IDs and argument positions, and does not modify the inputs or launch analysis jobs.

The frozen source composition is `f8f090861326acf7546a822569dd369362fb0f65`, tree `4aa2ade8b77170ae94d653aadfdf513e746777e3`. Its ordered parents are main snapshot `e48825b1b37544f4c31912e3c29a3918704f5456` and accepted PR head `7f5548fb12e040f45d7e1f5867d511dc33a618ac`.

Independent full-tree review found 1,182 leaves, the 13 intended paths, nine additions, no deletions, and 1,169 unrelated current leaves with their modes preserved. Twelve owned blobs are exactly the previously accepted contribution. The only composition conflict was the progress record: its complete current prefix and the exact original contribution were both preserved. The current source picker, job comparison, ML feature ordering and diagnostic runner changes remain intact.

The evidence successor adds this directory while retaining every leaf of that frozen source. This keeps the tested source distinct from subsequent custody records.

## What the evidence qualifies

| Source and receiving method | Actual result | Qualification |
| --- | --- | --- |
| Historical accepted tree `94f79e2f1f873507572045bfd1727df636076350`; ordinary Windows run `37821319011` | 559 Python tests passed, six daemon-not-built skips; 30 CTest cases and six native daemon/recovery cases passed | Exact historical source only; original receipts, deadlines and logs retained |
| Same historical tree; dedicated run `37821318986` | Eight receiving groups, 15 real CLI commands, three actual browser groups and four inspected screenshots | Native QC, CLI/browser behavior and conservation on that source |
| Current composition `f8f09086`; first native launcher attempt | 50 passed, 27 failed, two declared Windows-only skips; process 1 | Rejected receiver setup: omitted repository root prevented fixture helper imports |
| Same current composition; corrected native launcher | 77 passed, two declared Windows-only skips, zero failures/errors; process 0 in 19.6558578 seconds | Current Linux component compatibility across the frozen five test files |

The native run used the existing Python 3.12.15 and PySide6/Qt 6.12.0 environment on hamon-thinkpad. It materialized a selected 319-file source closure with exact Git blobs and modes, not a complete checkout. All 319 files were conserved before and after execution, and all 76 recorded project import origins belonged to the selected source. There were no dependency installations or production/test source edits.

The second launcher restored repository-root import semantics, expanded the import-origin guard and used fresh state/output paths. It preserved the original 300-second outer deadline, the exact five test files, their assertions and their platform markers. The first attempt, original launcher bytes, raw logs, JUnit, receipts and launcher delta remain in the sealed paired packet.

The two skipped cases are `test_application_sources_survive_timer_and_review_navigation` and `test_application_scope_survives_timer_and_review_navigation`. Both declare Windows-only MainWindow named-pipe transport requirements. They remain unqualified by this Linux run. This receiving does not establish current Windows full-suite acceptance, merge acceptance, deployment, hardware capture, or camera qualification.

Main advanced during custody preparation to `9e9204f76b105426b0affaa74733175c052f27ba`, tree `a1b37ec1ab291a90cb2a383aa8f50b797ac09932`, adding the separately owned external-prediction workbench contribution. The frozen `f8f09086` composition and its receiving remain bound to the preceding `e48825b1` snapshot. This checkpoint does not claim qualification or integration of the later main. The later complete workflow set was also read before custody publication; its events still exclude the distinct custody branch.

## Recovering the evidence

| File | Contents |
| --- | --- |
| `manifest.json` | Source pins, exact owned paths, receiving outcomes, custody constraints, and file hashes |
| `final-native-browser-receiving-packet.json` | Original historical 36-member packet, including actual browser screenshots |
| `final-ordinary-windows-gate-logs.json` | Exact original Python and CMake job log strings |
| `independent-final-gates-and-current-source-review.json` | Independent historical gate and complete source composition review |
| `current-native-paired-receiving.json` | UTF-8 envelope containing the exact sealed native archive, manifest and summary |
| `independent-current-native-reviews.json` | Exact independent native receipt/harness review, read-only audit source, paired-packet review and branch workflow audit |

The current native archive is `paired-receiving-f8f09086.tar.gz`, 290,157 bytes, SHA-256 `e5a4b2235299dc9655beba3cc2dae4e7fc7d676b050fe27406bf9e49fe0da1b1`. Its 25 files total 1,173,767 uncompressed bytes. Decode its base64 from the UTF-8 envelope, verify the recorded size and SHA-256, and inspect the members against the exact embedded `MANIFEST.json`. The independent addenda were produced after sealing; they are preserved separately and do not rewrite the original packet.

Historical statements that current receiving was still pending describe their original checkpoint. The paired native packet and the independent current-native reviews provide the subsequent result. Historical failures and exact-source limits remain valid.

## Custody and continuation

The distinct branch `receiving/qc-package-review-7879c2abc07f-current-main-20261008` provides reachability for the source and evidence objects. It has no pull request and is neither main/master nor a release tag. The complete reviewed workflow set admits branch pushes only on main/master and release tags only on `v*`; no create, issue/comment, schedule, repository-dispatch or workflow-run event is declared. The evidence successor preserves all four exact workflow blobs.

Do not update PR 79's source ref or merge main while those actions would trigger GitHub Actions. Do not treat an unrun gate as passed, disable a gate, or replace it with this component result. When the authorized integration path can proceed without violating current instructions, recheck the live main and required gates, start from the exact composition and retained evidence here, and qualify only source that actually ran. Reuse the settled QC/browser and scheduling evidence unless a concrete dependency change makes new receiving necessary.
