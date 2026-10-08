# Independent source and receiving review — Review event browser

## Disposition

**ACCEPTED for the existing supported Windows CI receiving gate.** No source blocker or additional authored native case was identified. This is independent source/evidence review, not a claim that the six Qt methods or their screenshots have already executed successfully.

Reviewer: `estate-31a349052b90 / engine_execution`. Author and publisher: `estate-31a349052b90 / product_execution`.

The reviewed source is CaptureSuite commit `82c950884f894235e99ce058f14531e2eedfa88d`, tree `3a5568085f4fe8bd1af097237262f5af32392051`, over parent `9c44354cb101c76beff79265de0040b6839d249f`, tree `50cd83ef270467490b15f74639413d238aaa15c6`. All findings below bind to these immutable bodies. A later main composition is a separate publisher responsibility.

## Source and preservation

I fetched both complete Git trees and the exact contribution bodies independently. All 14 contribution files reproduce their expected Git blob identities, byte lengths and SHA256 values. The candidate contains 1,023 leaves versus 1,012 parent leaves: 11 additions, three replacements and no removals. All 1,009 unrelated parent leaves retain their original bodies, modes and types.

The only replaced application file is `desktop/capture_desktop/screen_review.py` (`28645161592f80e37ee7855a0d43ccb8b3a44026`). Its authentic before-image is `88a902ca7699faa2964f3fc22ec3348a339905a4`, retained byte-exact under the evidence baseline. The other application additions are the record projection `review_events.py` (`006ce100cf6d1714d327552e06856e74b472abe0`) and native browser `widgets_review_events.py` (`4d74a42573c88102fd8756f68da2763cd1b21ee5`). The IA decision is append-only; the progress entry is prepend-only. Removing those additions restores both entire original documents.

I read the original reader `91fbf913c5af8489968425d7ceac51c04233d3e0`, timestamp schemas, timing contract, Review/export design, CI workflow, CI runner, dependencies and shared test fixtures. Reader, schema, capture/daemon, shared app/timeline, analysis, export and workflow files remain unchanged.

## Behavior reviewed

The browser keeps checkpoint and annotation records distinct, including duplicates, revisions, original/effective timestamps and unknown loaded fields. Their selected details are a plain, read-only JSON rendering rather than interpreted markup. The model snapshots text without writing or altering the loaded records. Source filtering uses exact case-sensitive IDs; search uses literal case-folded text. An absent, empty or non-string source has an explicit “No usable source ID” selection, retaining the original value in the record details.

Timestamp ordering uses integers without floating-point conversion, preserves zero and negative values, and places unavailable values last. A present but malformed preferred checkpoint timestamp remains unavailable; only an absent preferred field falls back to the original timestamp. Stable input positions resolve ties without a cross-kind causal claim. The timestamp schemas and timing design support integer session nanoseconds as a representation, not physical accuracy or synchronization.

**The gap boundary is narrower than raw JSON preservation.** The unchanged reader has already normalized gap fields through its existing integer, Boolean and fallback conversions and discarded unknown gap keys. The new pane explicitly says “Gap summary from package reader” and displays that projection. Strict admission of original checkpoint/annotation time values must not be described as new rejection of malformed original gap values. The gap label uses the loaded closure flag independently of the end-time field; no interval merging, downtime estimate or inferred closure is introduced.

The screen preserves its Overview and export action while adding the Events tab. A new load clears prior records, filters, details, overview lists, cards and recovery state and disables export before reading. A failed load retains the failure banner with no previous package eligible for export; a later successful load repopulates the view. Model reset, current-row handling and explicit detail clearing are consistent with preventing stale selection after filtering or reloading. These are source findings; native interaction remains the Windows receiving gate.

## Existing evidence and authored target receiving

The local receipt records **23 passing parametrized model checks** on the retained initial helper/test sources. I authenticated those sources and independently compared their ASTs with the publication files. The helper AST is identical. The test preserves all record-semantic assertions; changes are line wrapping and removal of an unrelated working-directory `Path(...).exists()` assertion and its import. I did not rerun those checks and do not relabel the executed initial bytes as the later formatted bytes.

The receipt also preserves absent local PySide6, one documented Windows Python-path probe returning exit 2, and the ENOSPC staging failure. Those are environment/preparation limitations, not successful Qt runs or event-browser failures. No installation or runtime probe was performed by this reviewer.

I read all six methods in `tests/ui/test_review_events.py` (`2aafc0d64a6e9b5437ec7a33c84719281ec40ad2`). They use physical authored packages, the actual unchanged reader and native Qt controls. The exact original screen is instantiated as an absence control after verifying its loaded checkpoint/gap counts. The candidate cases cover literal annotation content and unknown details, keyboard kind/source/search interaction, timestamp ordering and revisions, read-only editing refusal, independent gap closure/end facts, package clearing and recovery, and all 2,000 rows in one table. Package hashes are checked before and after.

The first method records exact source identities, actual selected details, the original-screen expected failure and physical package bytes, and saves the original Overview plus dark/light candidate PNGs. Those are authored evidence paths, not screenshots inspected at this source checkpoint.

The unchanged Windows Python 3.12 workflow installs the desktop/PySide6 dependency and invokes `tools/run_ci_tests.py` (`ef5274ab4c38e4082eca69608532a12a32d50c9f`). That runner collects `tests`, excluding only `tests/kill_tests`, and retains process/JUnit/source evidence. The workflow always uploads `build/evidence/`. The shared fixture isolates application-state directories. No maintained invocation is missing for this new test file.

## Remaining integration gate

Receive the actual published-head Windows result, verify all six Qt methods executed rather than skipped, inspect the accepted original-screen/package receipt and all three screenshots, and bind the working source hashes and checkout tree to the reviewed production/test bodies. An overall green suite alone does not establish that optional-import Qt methods ran. Preserve any failures and their exact source identities.

Ordinary current-parent preservation and the repository’s existing Python/Ruff/native CMake/CTest/daemon gates remain the publisher’s integration work. The reported advance to `a2fd6c58ccc97c7262b97570a85d8aae8dfb978c` is not independently claimed by this receipt; the publisher must preserve its additive progress/evidence changes when composing.

No physical device capture, installation, service change, deployment, capture completeness or scientific validity is accepted by this review.

## Immutable sources

- [Reviewed source tree](https://github.com/Jacob-Met/CaptureSuite/tree/82c950884f894235e99ce058f14531e2eedfa88d)
- [Source manifest](https://github.com/Jacob-Met/CaptureSuite/blob/82c950884f894235e99ce058f14531e2eedfa88d/docs/evidence/review-events-31a349052b90/source-manifest.json)
- [Local evidence and retained limitations](https://github.com/Jacob-Met/CaptureSuite/blob/82c950884f894235e99ce058f14531e2eedfa88d/docs/evidence/review-events-31a349052b90/local-receipt.json)
- [Authored actual Qt receiving](https://github.com/Jacob-Met/CaptureSuite/blob/82c950884f894235e99ce058f14531e2eedfa88d/tests/ui/test_review_events.py)
