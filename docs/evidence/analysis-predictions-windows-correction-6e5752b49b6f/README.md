# Windows Qt chooser receiving correction

The original product/source qualification remains in ../analysis-predictions-6e5752b49b6f. This successor changes only the actual-Qt test helper, one regression case, the read-only hosted JUnit observation, and scoped documentation/evidence. Production widgets, screen, evaluator and job lifecycle are unchanged.

## Original ordinary gate

PR84 head 1f0d19c17e760d4dd5c1146ce46075cc3f3ce45d, tree 66ef9a19ffc8ab920e1be9c1d278ae0741d09af2 was tested at generated merge c185ea19d48d38e3fdbd2c7e6c53df3c5910f0f8.

Windows run 37816542567, job 113446512304 reached the unchanged 300-second subprocess timeout. It produced no JUnit, so no MainWindow pass was claimed. The quiet log contained 522 completed markers; they did not alone establish the stopped node. The unchanged independent first-failure packet is retained as first-windows-failure.tar.gz (38,509 bytes, SHA256 0ba5ec79f69649889c146a2287adebf73e3213a9097c25e3350a7fd3f6721030). Its README distinguishes the original observation, then-unconfirmed chooser hypothesis and unavailable artifact bytes. Both supported download paths returned 403; no ZIP/member contents were received.

## Unchanged-source diagnosis

Diagnostic branch diagnostic/capture84-windows-6e5752b49b6f, commit 0fdcf87805b5afa2b662facdaba8e3165e1dc8e0, checks out the exact c185 source and repeats the full ordinary test order with -vv/-s, read-only observer and a stricter 150-second diagnostic bound. The workflow is preserved here as diagnostic-workflow.yml, not installed as a production workflow.

Actual run 37820661674 / job 113460546664 collected 582 items and localized the stall to tests/ui/test_analysis_predictions.py::test_actual_qt_file_choice_cancel_and_reselection. The finish callback ran with AA_DontUseNativeDialogs true. QFileDialog's filename field and selectedFiles had dropped the fixture's leading space: "first prediction .json" instead of " first prediction .json". A nested QMessageBox titled "Choose external predictions JSON" remained active. The actual 20-second faulthandler stack points to dialog.accept() at test line 73, beneath the unchanged production getOpenFileName call. The observer and source receipt confirm the original test/production bytes stayed unchanged. Qt timers and the non-native flag worked; this is a receiver input/cleanup defect, not evidence of a production dialog defect.

diagnostic-job-113460546664.log.gz preserves the complete raw connector log, without filtering, as concatenated gzip members:
- uncompressed: 485,096 UTF-8 bytes, SHA256 aaf93fba152b71b34a97f3e4601ede8255fcab858916f389d46ea543e8bf9658
- compressed: 60,527 bytes, SHA256 a00458f7e581ca56f1574b1ed5e15b0e10d8ffc8f632c960515e6c9de0ddbc06

Python gzip.decompress or gzip.open reads every member. The raw diagnostic is a failed localization run, never a successful ordinary gate.

## Bounded correction and required execution

The helper still opens the real Qt file dialog. It enters the filename using Qt's quoted literal-name field syntax and asserts the exact selected path before accepting, retaining the original significant-space fixture. A separate watchdog timer rejects unexpected nested QMessageBox dialogs before rejecting the file chooser; timeout or selection failures become test assertions. An actual nonexistent-file regression challenges that cleanup and verifies the previous path survives.

The ordinary 300-second runner, test selection, source snapshot and evidence upload remain unchanged. A read-only post-Pytest step verifies the ordinary receipt/XML identity, emits every prediction-module testcase with its full XML element and complete XML hash, and requires one passing non-skipped MainWindow, literal-file selection and bounded error-unwind case. It does not rerun any test or transform test results.

The corrected module and embedded observer pass Python syntax admission. The previously used Mac was offline during this correction, and cloud Python has no PySide6; no new local native pass is claimed. Supported Windows execution remains required on the actual new checkout. The earlier Mac functional/layout/cancellation packets retain their original pins and remain unchanged.
