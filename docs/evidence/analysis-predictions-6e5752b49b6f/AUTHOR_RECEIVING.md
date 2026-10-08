# CaptureSuite #69 — native external-prediction workbench receiving

## Result and source identity

The native Analysis workbench exposes the existing external-prediction evaluator through an explicit mode, exact file choice, validation and the existing background-job path. It retains the identity-teacher simulation as the explicit default. The final scoped UI source is accepted by separate functional, geometry/cancellation and root source receivers. The supported Windows MainWindow case remains a hosted CI gate at the time this packet is frozen.

Final executed layout source: 983641cc270db34be0711d554cd2c82608cb0b8c, tree 4cceca0d9ce05a354584c7a2e3092e5e59e6c7c9. Publication source: 4987c99c49751461a6b53a90ce9c43e39062ad59, tree 2d418e2094fae2caa59b17be66e1e7524ace66f0, declared parent 3cbb5300bdc79c157370d1b3e599a6c82752d54a. The four executed runtime/test files and operator guide are byte-identical in publication. ANALYSIS and PROGRESS append to the actual current parent; no owner content is replaced.

| Final path | SHA-256 |
| --- | --- |
| desktop/capture_desktop/widgets_analysis_predictions.py | d865031e313b0c1aed23a2cb0beeb20441a96d380f0b3652458107ba4a6e2435 |
| desktop/capture_desktop/widgets_analysis_jobs.py | a012ac150e1301a630417cd78238c050093206f94f073e6e0ee4c90f22b81b62 |
| desktop/capture_desktop/screen_analysis.py | a62e7e9ae63c658205531ef51844f4a68a64c738ce1de6083f93a4e9a5ddbc94 |
| tests/ui/test_analysis_predictions.py | e87f63a19639d40785d922b3e78d27b8487feb51a3c3c46d89ea6184f7facbe2 |

## User and job behavior

Choose Eval report and an ML bundle, then External predictions file and Choose. The path remains literal, including significant whitespace and Unicode. Empty or unavailable external choices block normal Run; explicit empty external extra remains a fail-closed backstop in the existing evaluator. Cancellation preserves the current choice. New sessions clear it; same-session command/mode changes retain it. Revision checks retire modal results after changed context. Clear retains external mode and returns focus to Choose.

The worker copies the scalar request values before execution. Its captured bundle/mode/path survive later editable controls or package activity. File selection is a path, not a byte snapshot: the evaluator admits and retains the actual bytes at execution. Existing source binding, schema, scoring, raw/package protection and job publication remain the evaluator owner's implementation.

The controls column scrolls at constrained heights. A reserved thread now disables Run and the evaluation-input controls and enables Cancel immediately, while a second start is refused. The existing bundle selector remains editable; its later value does not alter the captured job. Worker lifecycle and cancellation handling are unchanged.

## Native author execution

All executions used the already installed Python 3.12.8 / PySide6 and Qt 6.11.2 runtime on Mac, with private temporary, Matplotlib and application-profile directories. QT_QPA_PLATFORM=offscreen used actual Qt widgets/dialogs/QThreads; no OS-native Cocoa dialog or operating-system focus claim is made. No dependencies were installed and no hardware or daemon was called.

| Record | Exact scope and outcome |
| --- | --- |
| baseline-native | Actual earlier PR65 f6ff65d AnalysisScreen has no prediction mode/path controls; screenshot and absence record preserved. |
| native-r1 / native-debug-r1 | Initial 300-second harness timeout and keyboard failure preserved. qWait polling starved the real worker's Matplotlib drawing; Return was the wrong QPushButton activation assumption. Debug execution nevertheless completed the actual external job. |
| native-r2 | Corrected native QEventLoop/Space harness: 28 passed, two existing protobuf warnings; scoped Ruff passed; all four source files unchanged. This includes 26 new cases and two unchanged workbench cases. |
| native-current | On exact d7459fa composition, three real workbench cases passed; external, identity and refusal/retry outputs and inventories preserved. |
| native-ui | Actual completed external job and dark/light 1280×960 images exposed clipped controls. Retained prediction bytes, report, raw/package and output inventories were checked. |
| native-layout-r2 | On 4e8075a: 28 passed, two geometry tests failed and one Windows-only skip. All essential size/height/help/keyboard assertions passed; the extra assertion incorrectly demanded scroll motion even when Run was already visible. Static import-order failure and correction are separately preserved. |
| native-layout-r3 | On 983641cc: unchanged runtime, corrected conditional scroll assertion. Both size cases passed and the Windows-only MainWindow case was explicitly skipped. Scoped Ruff passed; source unchanged. |

These are distinct original records, not a fabricated single 30-pass run. The final test file differs from the 4e8075a file only in the condition for demanding scroll movement. Deprecation warnings remain visible in original logs.

The archive contains the actual inputs/results, original logs/JUnit, exact failed and corrected source snapshots, source manifests and reproduction wrappers. Font caches and completed early temporary fixtures that were safely reproducible were removed only from this worker's directories; the cleanup record describes them. Failure logs and executed source remain retained. Pytest convenience symlinks, if present, are inert metadata rather than followed archive members.

## Independent receiving and demonstrated defects

The unchanged companion functional archive binds original source 424298e3: four independent groups, 12 actual Qt file dialogs and six real evaluator jobs. It verifies chooser cancellation/reselection/retirement, exact filenames, external/identity/refusal/retry provenance, queued inputs and execution-time file-byte binding. All imported project files and protected inputs were hash-admitted.

The unchanged counterexample archive preserves two real defects separately. New controls were compressed below native minimum heights, and requested 1100×700 became 1100×881. Separately, the inherited screen checked isRunning before thread.start and left Run enabled/Cancel disabled during a real held worker. Removing our initial input-disable hook reproduces the whole parent screen byte-for-byte, establishing that second defect's ancestry.

The successor archive binds exact 983641cc. Both 1100×700 and 1280×960 geometry cases pass with minimum heights, wrapped help and keyboard reachability. Actual Clear → file chooser → keyboard Run → held worker → keyboard Cancel → settled recovery passes; the real evaluator consumes cancellation before outputs. The receiver's forward-Tab assumptions were corrected to Shift+Tab after actual focus diagnostics; both failures and final success retain original provenance. It is not a second run of the six functional jobs.

The production author also read the final successor guide and inspected four actual final images: both viewport mode views, the held worker and recovery. Controls are readable and unclipped; the state assertions and real cancellation receipt substantiate behavior beyond screenshots.

Root's independent source-review.json is preserved unchanged (SHA-256 ab0487bd1695fb6d543d39b7cb0bb6fe7a77df98ccd517be86acdae9a5329fa9). It accepts the final source boundary and explicitly leaves current-parent admission and Windows CI to later gates.

## Current-parent and platform boundaries

Publication retains the stronger current checkpoint-window helper. Earlier six-job receiving used null start/end/checkpoint and full-session scope; the checkpoint-only delta is outside those executed branches, a source-based inference rather than a replay. Current PR66's runner refuses explicit apply_sync_anchors=True and records false for the ordinary branch; our UI and captured jobs use false. External prediction forwarding and evaluator source remain preserved. Current-parent inventories and independent admission record the exact comparison.

Unchanged app.py and daemon_link import Windows named-pipe modules before constructing MainWindow, including msvcrt and ctypes.WinDLL. Consequently auto_connect=False does not make the full application importable on Mac. No transport stub was introduced. The permanent Windows-only test instantiates actual MainWindow(auto_connect=False) at its declared minimum 1100×700. Existing windows-2022/Python3.12 CI must execute it; Mac AnalysisScreen proxy results do not replace that supported-platform gate.

The existing gallery does not directly tab eval/figures images. The guide directs users to the existing Export figures action or Windows Open job folder and preserves the gallery owner's scope. Real scientific validity, trained-model execution, hardware capture, OS-native dialog behavior and installed deployment are outside these synthetic fixture results.

## Packet verification and reproduction

MANIFEST.json lists every regular member except itself with its original byte count and SHA-256. The freezer reads the completed gzip tar back, requires the exact member set, rejects non-file members and hashes every byte. The archive is provided with a separate summary containing its SHA-256 and Git blob identity.

Use the project's declared Python 3.12 dependencies. Exact native commands and private environment settings are in the preserved wrappers and process records. Run against a checkout matching the recorded source; do not relabel older receipts to a newer source. Source snapshots, raw Git commit bodies and path inventories retain the local history without copying an entire repository. Reproduction writes only to fresh fixture/output directories.
