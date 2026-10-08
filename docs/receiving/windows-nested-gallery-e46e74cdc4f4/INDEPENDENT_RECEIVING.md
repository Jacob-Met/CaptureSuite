# Independent receiving: CaptureSuite PR80 Windows link assertion

## Result

Accept the narrow test correction at candidate Git blob `746084780e126b103489902f119b8e46c2fd8c98` for integration through the existing PR80 owner's branch. The candidate establishes that the newly created link refers to the intended fixture file, captures the filesystem's actual stored target, then requires that target to remain exactly unchanged after the gallery call.

This receiving does not mark the whole PR green. The required updated-head hosted suite remains pending. No Qt/gallery invocation or Python 3.12 execution was performed in this native receiver.

## Actual hosted baseline

- Repository: `Jacob-Met/CaptureSuite`
- PR: [80](https://github.com/Jacob-Met/CaptureSuite/pull/80)
- Head: `bd390a9d497e567cd868ba4029b74bbd509b4a78`
- Hosted merge checkout: `e0a45debe5e2a331ba5aee242ac985c9f604b31b`
- Run: [37811945519](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37811945519)
- Python job: [113430762650](https://github.com/Jacob-Met/CaptureSuite/actions/runs/37811945519/job/113430762650)
- Python 3.12.10 / Windows: **545 passed, 6 skipped, 1 failed**, 252.87 seconds.
- The six skips explicitly concern the unbuilt `capture_daemon.exe` in that Python leg.
- Ruff and license checks passed. The distinct CMake check `113430763041` completed successfully.
- The only Python failure was `tests/ui/test_analysis_nested_gallery.py::test_png_discovery_refuses_external_file_links_and_directories`, at `assert foreign.readlink() == outside`. Its preceding gallery title, pixel, and relative-path assertions had passed.
- The unchanged link's returned spelling has Windows' extended-length prefix (`\\?\\`), whereas the authored `Path` does not. Comparing these lexical representations is not a valid unchanged-link assertion.
- Complete fetched job-log content is retained at `github-job-113430762650.log`: **57,921 bytes**, SHA256 `e9bbc99cb596b4016de2cfa7ab0729d8daff846e6e97459a8f2dec11af93a074`. Original CRLF bytes were preserved.

## Exact source identities

| Source | Git blob | Bytes | SHA256 |
| --- | --- | ---: | --- |
| Original test | `0874d6b51b22cbbeaa8b1e309ed92418efcec2c6` | 7,142 | `727340556a0d8e4178b62157ba9680a59d1c43158abb1bf979b21be8c98c591f` |
| Root's candidate test | `746084780e126b103489902f119b8e46c2fd8c98` | 7,291 | `566ff56a05014d47ffd887976751c06f259957a908ec34528725a039269b434f` |
| Unchanged gallery | `28e907de7c7c9a7945249796b61b325853f6de88` | 10,821 | `002327b8e6303412269c0ca8c4a105d9e8eeb96491eec0836e39ce199e2c18fd` |

The receiver hashes the full original and candidate test bytes to both their Git blob identities and SHA256 before invoking any extracted statement. It uses the exact AST statements for the original assertion, candidate identity/capture guard, and candidate preservation assertion. All other AST nodes in the affected test function compare equal. Full original/candidate source bytes remain unchanged after receiving.

## Native receiving

The actual authorized LA7 Windows surface executed the receiver with existing Python **3.11.9**, platform **Windows-10-10.0.19045-SP0**, on **2026-10-08 at 17:16:44 UTC**. Process **50068** completed with exit **0** in **0.32 seconds**.

The native fixture creates only owned disposable files. There is no substituted gallery, stub Qt result, installed-service call, or change to another worker's workspace.

| Case | Actual result |
| --- | --- |
| Original assertion on a real absolute Windows link | Fails with `AssertionError`; `samefile(outside)` is true and the returned target has the extended-length prefix. |
| Candidate statements on the unchanged absolute link | Identity guard and exact stored-target assertion pass. |
| Candidate statements on an unchanged relative link | Identity guard and exact stored-target assertion pass; original relative spelling remains retained. |
| Link retargeted to a different file with identical bytes | Candidate preservation assertion rejects the changed target. |
| Link replaced by a regular file with identical bytes | Candidate preservation assertion rejects with Windows error 4390. |
| Initially wrong link target with identical bytes | Candidate identity guard rejects before the notional gallery boundary. |

Healthy fixture target bytes and exact original/candidate source bytes were checked unchanged.

## Retained native evidence

Native workspace:

`C:\Users\minec\hamon-cs80-receiving-e46e74cdc4f4`

The completed run remains under `native-20261008T171644Z` there, alongside exact source copies and the original authored fixtures. It is an isolated receiving workspace; no shared cleanup was performed.

- `native/receipt.json`: **2,981 bytes**, SHA256 `a47567302f0e0b5b3cf2b205527856aaa1d1a5d48e87ba4d2c22d20027afab48`.
- `native/receive_windows_links.py`: **6,850 bytes**, SHA256 `314a5b53ec2ac56a05a57f0ff6ba7e29a7f49a048ec5ab65adf1c160e5cfba9b`.
- `native/process-start.json` and `native/process-completion.json` retain the tool-reported output and successful exit.
- Exact native receipt and receiver bytes were copied back through base64 and independently checked against their native byte counts and hashes.

One initial source-payload write failed because the new receiving directory did not yet exist. The directory was then created normally and the write succeeded; no fixture or test had run at the time of that setup error.

## Ownership and remaining gate

Original product owner remains `estate-401c5d17da79`, claim CaptureSuite #64, PR80 branch `fix/nested-figure-gallery-401c5d17da79`. This packet qualifies only the narrow portability correction in that contribution's test. It does not take ownership of the gallery implementation, history/export behavior, native deployment, or final integration.

The owner route must preserve its current source and evidence, apply the exact correction, and receive the unchanged hosted platform gates on the resulting proposed head. The successful native fixture result cannot substitute for that full updated-head hosted gate.
