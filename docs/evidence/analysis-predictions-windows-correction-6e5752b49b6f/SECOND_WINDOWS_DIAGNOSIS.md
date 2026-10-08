# Second Windows failure and exact-source diagnosis

The previous Windows correction remains immutable at 2db743a2cc16bb4c3e996235b4ee7b5f1c94b38b (tree f4543bbb648b74f81ded4f9c0454b171b9a371a6). No passing ordinary gate is claimed for it.

Ordinary run37826850947 / Python job113481790199 tested exact merge e548c4fc1d86e5762deb27fe1e82d6fd494ddf7b. The unchanged300-second process limit expired again before JUnit. Source stayed clean/unchanged,1,092 files, source-map digest e2f0bbe99361474d2092122e0e3d233ac14277c3c664d7cf75a542041490a011. The C++ job113481790851 passed. Quiet progress was not used to assign passing/failing node names.

ordinary-job-113481790199.log.gz preserves the full actual raw job log:
- raw57,081 bytes / SHA256 594d939ca33088a7870c8e41781ddbaef37abae9efab5821ad143040f21bb70b
- gzip13,120 bytes / SHA256 6b71fd5e1aae759c4c60428c0598f53484a5a8dad7726f020dbe8c714916461f

A single follow-up diagnostic at unchanged e548 used the same full selection/order and stricter150-second limit. Diagnostic branch commit ec6d25b0b29dce785687fe2dc89a1aebf9e3b17f, actual run37828302060 / job113486762104, adds immediate read-only failure reports and extends modal observation to the existing UI tests. diagnostic-workflow-r2.yml is preserved only as evidence, not installed as an ordinary workflow.

Its actual emitted node/phase evidence establishes:
1. test_each_native_ci_check_fails_its_own_step rejects the new inline observation block:41 commands violate the existing one-command-per-step contract.
2. test_actual_qt_file_choice_cancel_and_reselection fails at its first file. Even quoted text routes through a model path lookup that drops the significant leading space. The new exact selectedFiles guard reports this failure promptly.
3. The actual missing-file cleanup case passes, as do all three real evaluator-job tests and both standalone geometry cases. These are diagnostic call outcomes, not a passing ordinary run or standalone requalification.
4. The real MainWindow reaches1100×700 with valid layout but its Clear Space action leaves the path unchanged. The existing ApplicationShortcut Space handler captures that key before the button. The keyboard assertion is retained.
5. The later pre-existing test_selected_scope_reaches_real_thread_job_and_mcap_outputs[range] stalls. Its main thread is at QTest.qWait line129 while the real worker renders Matplotlib glyphs; read-only Qt observations show no active modal. Its cleanup also contains an unbounded polling loop. This receiving code belongs to the scope owner and is coordinated separately.

diagnostic-job-113486762104.log.gz preserves the entire failed diagnostic:
- raw1,002,243 bytes / SHA256 38a8dbb2c584d7ffe182b18dc1c0c797f9c3d2c0af9971c15da598c19ccec235
- gzip100,265 bytes / SHA256 59abf053d89d0f866d1ee9f1f90402e2a8925efd3e7df59c0688ca68148d756e

Both gzip files use standard concatenated members; Python gzip.decompress/gzip.open or gunzip reads the complete original stream.

The next candidate preserves the complete current source-picker parent6ef303bb and root's verified screen composition. Existing files are selected through literal model-row enumeration, viewport clicks and the actual dialog accept button, adapted from the unchanged independently qualified receiver786fae0f. A separate watchdog remains responsible for visible failure and modal cleanup. The product change is restricted to accepting ShortcutOverride for unmodified Space on the actual focused descendant Analysis QPushButton; native key events activate it. Real countercontrols verify other focus and keys still reach application shortcuts. No global app.py policy is changed.

The JUnit reader is moved without weakening to tools/verify_prediction_workbench_ci.py and one executable workflow command. Its standalone synthetic admission checks accept a valid named report and refuse skipped MainWindow, duplicate MainWindow and hash-mismatched XML; those checks are explicitly synthetic, not hosted results. The original ordinary runner,300-second limit and all original consumer assertions remain.

The full corrected composition must pass the actual ordinary Windows gate with named non-skipped MainWindow and chooser outcomes before adoption. Historical native packets and both failed ordinary/diagnostic identities remain distinct.
