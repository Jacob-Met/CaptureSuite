# CaptureSuite keyboard-observer correction proposal

Status at 2026-10-09 11:21:30 UTC: **UNEXECUTED; awaiting root review and explicit serialized Mac interval release.** No continuation source has been materialized on the Mac and no additional browser, CLI, renderer or product invocation has occurred.

The original completed custody has 100 leaves, bound by b4a4f33f218135a43d8b40b957416423ba5eb0a9. Linux C1–C3 passed. The original one-browser Mac C4 attempt remains INCOMPLETE: native Enter reopen observation timed out, and sync/gap navigation plus two later screenshots were unexecuted. Its complete failure/closure and 2,792-byte Chrome OS stderr remain immutable.

## Concrete scope

The proposed continuation reads the **same physical** original recorded-events.html, Git fac1f8c93b74160f1ee2b2675de8232bd120e0ce, from the original Mac directory. It reads the original AUTHORITY.json and verifies every one of the original 15 nonprofile files before and after. It writes only a new exclusive continuation directory. No report regeneration, candidate/source alteration, Linux CLI replay or default browser profile is involved.

The original CDP Enter messages supplied key identity without character text. The proposed messages use Puppeteer's canonical ordinary Enter carriage-return text and unmodifiedText on keyDown, then its usual keyUp shape. Passive listeners record the actual trusted keydown/keypress/keyup and disclosure state. The continuation requires a trusted keypress with charCode 13 and actual reopening; it does not substitute a DOM state assignment or another activation. No key retry is included.

If reopening succeeds, the receiver completes the outstanding annotation screenshot, Sync and Gaps navigation/full text, gap screenshot and final literal-script/network/exception observations. It retains the original overview and checkpoint navigation without repeating those settled observations. New C4_continuation/C5_continuation fields cannot change the original C4 outcome. Visual inspection of the two newly produced images remains a separate necessary step after any actual run.

## Exact proposed files

| File | Git blob | Bytes |
| --- | --- | ---: |
| CORRECTION-CONTRACT.md | a5174cddc11001e2d214ce74382eca3009d9281d | 10919 |
| receiver.mjs | 567f3e3ea10402f4e88a431cc0fa0b49952bf2aa | 26043 |
| REVISION.json | 6ee58ee3029f7f133bc47f2b9fe31008b1bb80d0 | 5880 |
| mac-outer-continuation.py | 24bed9f37bd9ec1daf6db579055667691274ff68 | 75189 |
| EXACT-OBSERVER-DELTAS.json | ff5103a9b8253f3f299005399170a7f783f6cad1 | 13624 |
| PRIMARY-SOURCE-REVIEW.json | bafc52cacacbfa20648850b1db80dba0de3cb7ab | 8975 |

The exact-delta file reconstructs the final receiver from original source 356784a70e46e532bb3a3f938475fd6331aa0924 through 20 ordered exact string replacements. That pure string reconstruction was checked in orchestration; no native program execution is claimed.

The first unexecuted draft 0e1b2065cae0ed3f2bb45af94fb21ed8eeaab795 and its first delta 3336d0d5f005254dd95e75ba8326ad263541c004 are preserved under drafts/. Review found the initial continuation accounting excluded only the new profile path while traversing the old root; the final helper excludes the browser directory belonging to whichever root is being traversed. This prevents the retained profile from being wrongly counted as static evidence. It does not remove that profile from its separate cap.

## Primary evidence

The source review binds the full retrieved official source bodies and exact upstream Git file identities:

- Chromium at the **original browser's reported revision 45889d77830582727fe00dbfd614bcb7aac35caa**, [html_summary_element.cc](https://github.com/chromium/chromium/blob/45889d77830582727fe00dbfd614bcb7aac35caa/third_party/blink/renderer/core/html/html_summary_element.cc), blob 21cbaac433dbc66e3ec8631945ca3c39eb5a5f32: summary keyboard activation delegates to the shared element handler.
- Same revision, [html_element.cc](https://github.com/chromium/chromium/blob/45889d77830582727fe00dbfd614bcb7aac35caa/third_party/blink/renderer/core/html/html_element.cc), blob 7c715baded59196c67f30f1520ef6291bd2b2e94: HandleKeyboardActivation activates Enter on carriage-return keypress. The currently retrieved shared handler, blob 8b94d89e491ccf54155bdf396b83c44d77693462, retains that rule.
- Puppeteer [CDP Input.ts](https://github.com/puppeteer/puppeteer/blob/main/packages/puppeteer-core/src/cdp/Input.ts), blob 48d64f1574a587d91735a8b1713d6b19be9390c3, plus [USKeyboardLayout.ts](https://github.com/puppeteer/puppeteer/blob/main/packages/puppeteer-core/src/common/USKeyboardLayout.ts), blob 0a6d2f2e18ab84d801fc89d07849477346189d8e: ordinary Enter supplies carriage-return text, and down dispatch forwards text/unmodifiedText.
- DevTools [Input.pdl](https://github.com/ChromeDevTools/devtools-protocol/blob/master/pdl/domains/Input.pdl), blob 815bf7c4147c4dd89ea6e9c7a0440517cb5a4937: the protocol defines key identity and generated character text separately.

The exact reported-revision source is evidence about the browser's reported lineage, not a independently reproduced Chrome binary. Missing text is a concrete observer difference from the canonical sequence and a plausible mechanism for the original timeout. The failed attempt did not record DOM keyboard events, so no unmeasured original event absence is asserted.

## Guards and closure

New owned root: /Users/me/Developer/capturesuite-recorded-report-continuation-c945953fdeb7. The exclusive outer refuses an existing target without writing to it. Before materialization and before the Node child, it checks pinned runtimes, complete original identities, 256 MiB free disk and 2 GiB conservative available memory. The 2 MiB static/evidence cap and 96 MiB profile cap apply cumulatively across old and new directories, using both logical and allocated sizes. This introduces no new allowance or lower floor.

The one Chrome activity remains capped at 180 seconds; outer Node closure remains 195 seconds plus two seconds of owned termination grace. Source/evidence writes are exclusive, flushed, fsynced and bounded. Only owned child groups may be terminated. The actual wait/poll, streams, capacities, protected-file comparisons and any refusal must be retained. No Mac execution has yet exercised this proposal.

## Custody and publication limits

Every proposal file in PROPOSAL-CUSTODY.json is an actual uploaded and exact-read-back Git object. Neither these unreferenced objects nor the original unreferenced map by themselves anchor retention. Root owns integration/ref publication under the standing workflow hold. This packet does not authorize a push, workflow change or run.

The final admission requested from root is narrowly the exact reviewed outer/receiver/contract and one additional bounded observer interval after SQL closure. Until that message is received, all native work remains pending.
