# CaptureSuite69: independent native layout and cancellation receiving

## Acceptance

The corrected author source at **983641cc270db34be0711d554cd2c82608cb0b8c**, tree **4cceca0d9ce05a354584c7a2e3092e5e59e6c7c9**, is accepted for the scoped native AnalysisScreen layout and cancellation contract. Its three runtime files remained unchanged throughout this receiving.

The final receiver is `r6/receive-analysis-viewport-r6.py`, SHA-256 **8c2a8f172f7089440b10f17f386cae30f5966e65004129e1f830dc367fd3b2f9**. Its actual native process exited **0** after **12.57 seconds**. Both receiving groups pass, comprising the two viewport sizes and one real held-worker cancellation. The actual final receipt is `r6/receiving.json`; complete unedited tool launch/completion output is in `native-successor-execution.json`.

This supplements the earlier six-job functional acceptance at source 424298e3. Those results retain their original source provenance. No evaluator case was rerun to manufacture successor provenance.

## Exact source and the bounded change

The corrected source descends from 424298e30d6e0f08fe4124fa282328575c40d203 through 4e8075a38cd31529534fe6199a7fa6a0b616d035. The new screen source wraps the existing controls column in a native QScrollArea, reuses the reserved-thread presence as the busy value, and refuses another start while that reservation exists. The prediction widget and extras module are byte-identical to the accepted functional source:

| Source | SHA-256 |
| --- | --- |
| desktop/capture_desktop/widgets_analysis_predictions.py | d865031e313b0c1aed23a2cb0beeb20441a96d380f0b3652458107ba4a6e2435 |
| desktop/capture_desktop/widgets_analysis_jobs.py | a012ac150e1301a630417cd78238c050093206f94f073e6e0ee4c90f22b81b62 |
| desktop/capture_desktop/screen_analysis.py | a62e7e9ae63c658205531ef51844f4a68a64c738ce1de6083f93a4e9a5ddbc94 |
| tests/ui/test_analysis_predictions.py | e87f63a19639d40785d922b3e78d27b8487feb51a3c3c46d89ea6184f7facbe2 |

`source/` preserves these four files, the added `docs/design/research/EXTERNAL_EVALUATION_WORKBENCH.md` usage guide, and the unchanged application-shell and Windows transport modules. `source-manifest.json`, the complete Git tree inventory, raw Git commit bodies, and `source-delta-from-424.patch` bind the files and ancestry. The receiver admitted all **62 actually imported project files** against the exact source tree after execution and verified a clean source worktree. No peer checkout, application configuration outside the receiver lane, or production source was modified.

## What actually ran

The native environment was Python **3.12.8**, PySide6 / Qt **6.11.2**, on the connected Mac. Each receiver used private application, temporary and Matplotlib directories and the existing installed runtime. No package installation or hardware/daemon call occurred.

At requested **1280 × 960** and **1100 × 700**, the actual AnalysisScreen retained exactly those dimensions. The native keyboard walk reached the mode selector, read-only file path, Choose, Clear and Run. At each reached control, the oracle intersected its rectangle with every ancestor viewport and required its native minimum height; Cancel beside Run was visible, and all wrapped help lines had their required height. All these checks passed. Both size images and the final held/recovered images were visually inspected.

The final user-action sequence was:

1. Shift+Tab from Run to Clear, then Space. The exact external path cleared while external mode remained selected, and focus returned to Choose.
2. Open the actual Qt QFileDialog, select the receiver's real prediction file through its file view, and accept it. The significant spaces and Unicode in its path were preserved.
3. Tab to Run, then Space. The real worker entered an explicitly held pass-through observer on a background thread.
4. Observe Run disabled, Cancel enabled and the evaluation input disabled. The native scroll viewport kept Run and Cancel visible.
5. Shift+Tab from the job log to Cancel, then Space. The real worker's existing cancel event changed from false to true.
6. Release the scheduling hold. The unchanged evaluator consumed cancellation before creating job outputs; the worker settled, Run and evaluation input re-enabled, and Cancel disabled. Source bundles and the original package remained unchanged.

Only the scheduling hold and an observer forwarding to the real evaluator were installed. No worker, scorer, dialog, result or error was replaced. The two pre-existing fixture bundle directories remained the complete job-directory inventory after cancellation. The actual fixture inputs and protected bundle/package bytes are preserved under `r6/`.

## Receiver corrections are preserved separately

The original product failures are in the unchanged companion counterexample archive listed below. This packet also retains the following successor receiver corrections without calling them production defects:

- **R3** used the unchanged corrected geometry oracle and passed both size cases, then stopped before a chooser or job because its return-to-Clear helper assumed that repeated forward Tab would wrap through every widget.
- A separate **zero-job focus diagnostic** confirmed actual focus behavior: forward Tab from Run eventually enters the existing editable mappings QTextEdit, whose `tabChangesFocus` is false; subsequent Tab inserts text. One Shift+Tab from Run reaches visible Clear directly.
- **R5** used that backward Clear navigation and successfully selected the real file and started the real held worker. It stopped at its analogous forward-navigation assumption for Cancel: disabling Run transfers focus to the read-only job log, and continuing forward eventually enters the mappings editor. Its worker was cancelled by receiver cleanup; that is not labeled as a user Cancel action.
- **R6** changes that one navigation direction to Shift+Tab from the job log to Cancel. The recorded native focus transitions show the target was reached. The geometry assertions remain the same, and the receiver adds explicit post-cancellation assertions for Run, Cancel and evaluation-input recovery.

The first packaging check also stopped on its strict expected-path assertion: the successor includes the added usage guide as a fifth path beyond the four-file runtime/test manifest. The corrected freezer requires exactly those five paths, includes the guide bytes and preserves the original packaging assertion and readback. That was an inventory correction, with no execution or production change.

All four original receipts, receiver sources and raw execution outputs are retained. R3 and R5 exit 1 are preserved; the diagnostic and R6 exit 0 are preserved. There was no production-source correction during these receiver changes. Actual Qt explicit-window activation emits a recorded deprecated-API warning; it establishes the offscreen keyboard precondition and is not presented as operating-system focus behavior.

## Platform and current-main limits

This is actual **AnalysisScreen** receiving at the requested viewport sizes on Mac, not an execution of the full Windows MainWindow. The unchanged application shell imports Windows named-pipe APIs before construction, so it cannot be imported unmodified on this Mac. No transport stub was introduced. The author's real MainWindow(auto_connect=False) test is explicitly Windows-only; the existing CI runs all normal tests on Windows 2022 and must provide the separate supported-platform result.

The final functional source remains pinned to 983641cc. The separately preserved current-main admission concerns **9c44354cb101c76beff79265de0040b6839d249f**, tree **50cd83ef270467490b15f74639413d238aaa15c6**. Of 66 unowned project modules in the earlier functional receipt, 65 retain their exact Git blobs. The only changed module is windows.py, confined to checkpoint_section_window's preceding-section behavior; both exact source versions are retained in `current-main-windows-source.json`. All six earlier jobs used full-session scope, with null start/end/checkpoint fields. The conclusion that this changed checkpoint helper was outside those executed branches is a source-based inference, not a replay on the newer main. Preserve the current helper when composing publication.

## Companion evidence, unchanged

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| capturesuite69-functional-receiving.tar.gz | 743543 | 8efa28046febd1fbadadefaf0cb35229e9cc4cefa6b621bd9c2d35f979c7737f |
| capturesuite69-original-counterexamples.tar.gz | 552335 | c3050c15d7552d63ce5281e483e22b72d37bbdabd41a955135dbab4dd15b8a31 |

The first archive contains the six real evaluator jobs, 12 actual file dialogs, exact retained bytes, independent scoring/provenance checks and all original receiver corrections. The second contains the original clipped geometry, inherited Run/Cancel counterexample and source-ancestry proof. This packet verifies their hashes without repacking or relabeling them.

## Reproduction and artifact verification

Use a source checkout matching the exact source tree and the existing project Python dependencies. The public base is d7459fa62dd7a57d5565214e10638e055ad5877c; replacing the four owned runtime/test paths and adding the usage guide with this packet's source yields the recorded successor tree. Raw ancestor commit bodies and the preceding companion source packet preserve the local receiving history. The receiver intentionally rejects another Git HEAD/tree.

The exact native command is retained in the execution record. In another equivalent checkout, set its source path, a fresh output directory, and the recorded expected commit/tree when running the receiver. It creates its own fixtures and private application state. It never starts the Windows transport. Do not point it at a shared writable output directory.

`MANIFEST.json` enumerates every packet member except itself. The freezer reopens the completed gzip tar, checks the exact member set, rejects non-file entries, and hashes every extracted byte against the manifest. Archive identity and manifest/receipt hashes are in the adjacent packet summary. Receivers and source files carry the project GPL-3.0-only notice where applicable.
