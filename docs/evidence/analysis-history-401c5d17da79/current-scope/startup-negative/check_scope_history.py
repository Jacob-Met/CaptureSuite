# SPDX-License-Identifier: GPL-3.0-only
"""One real native scope/history journey on the received current source."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import traceback


def hashes(root, raw_only=False):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and (not raw_only or "processing" not in p.relative_to(root).parts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    assert source != output and source not in output.parents and not output.exists()
    inputs = json.loads(args.inputs.read_bytes())
    expected = {row["path"]: row["sha256"] for row in inputs["files"]}
    assert hashes(source) == expected
    output.mkdir(parents=True)
    for key, name in [("LOCALAPPDATA", "local"), ("APPDATA", "roaming"),
                      ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                      ("XDG_CACHE_HOME", "cache"), ("MPLCONFIGDIR", "mpl"),
                      ("TMPDIR", "tmp"), ("XDG_RUNTIME_DIR", "runtime")]:
        directory = output / "state" / name
        directory.mkdir(parents=True, mode=0o700)
        os.environ[key] = str(directory)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    sys.dont_write_bytecode = True
    for rel in reversed(["desktop", "libs/python/capture_analysis", "libs/python/capture_session",
                         "libs/python/capture_protocol", "libs/python/capture_protocol/capture_protocol/generated",
                         "libs/python/capture_worker"]):
        sys.path.insert(0, str(source / rel))
    report = {"canonical_parent": inputs["canonical_parent"], "runtime_tree": inputs["composition_tree"],
              "screen_git_blob": inputs["composed_screen_git_blob"], "checks": [], "errors": [],
              "method": "QApplication.exec/QTimer; actual SessionHeader and AnalysisScreen, two real QThread/MCAP feature jobs",
              "method_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_inputs_sha256": hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
              "scope": "One changed scope/history boundary. No Windows MainWindow, full-suite, nested-image repair or installed-release claim."}

    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
        assert condition, name

    try:
        import PySide6
        from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget
        from capture_desktop import theme
        from capture_desktop.screen_analysis import AnalysisScreen
        from capture_desktop.state import CaptureState
        from capture_desktop.widgets_session_header import SessionHeader
        helper_path = source / "tests/analysis/test_numeric_batch_pipeline.py"
        spec = importlib.util.spec_from_file_location("current_numeric_fixture", helper_path)
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)

        def package(name):
            root = output / (name + ".mmsession")
            root.mkdir()
            (root / "manifest.json").write_text(json.dumps({"sessionId": name, "state": "sealed"}) + "\n")
            stream = root / "sources/lsl/streams/numeric"
            stream.mkdir(parents=True)
            fixture._write_mcap(stream / "segments/000000.mcap", [(1_000_000_000, fixture._batch())])
            (stream / "stream.json").write_text(json.dumps({"sourceId": "lsl", "streamId": "numeric.stream", "modality": "eeg", "dataSchemaId": "generic.numeric_batch/1", "nominalRateHz": 2.0, "units": "V", "dimensions": [2]}) + "\n")
            return root

        first, second = package("scope history A"), package("scope history B")
        raw_before = {str(p): hashes(p, raw_only=True) for p in [first, second]}
        app = QApplication([])
        theme.apply_theme(app, setting="dark")
        shell = QWidget()
        layout = QVBoxLayout(shell)
        header, screen = SessionHeader(), AnalysisScreen(CaptureState())
        layout.addWidget(header)
        layout.addWidget(screen, 1)
        header.scope_changed.connect(screen.set_scope)

        def package_loaded(summary):
            if summary is None:
                header.clear()
            else:
                header.refresh_sealed(summary, selection=screen.scope)

        screen.package_loaded.connect(package_loaded)
        shell.resize(1280, 1050)
        shell.show()
        picker = header._scope_picker
        state = {"phase": "start", "deadline": time.monotonic() + 50, "dialogs": [], "cancelled": False}
        ranges = [(1_500_000_001, 2_500_000_001), (1_000_000_001, 2_000_000_001)]

        def choose(bounds):
            picker._mode.setCurrentIndex(picker._mode.findData("range"))
            picker._start.setText(f"{bounds[0] // 10**9}.{bounds[0] % 10**9:09d}")
            picker._end.setText(f"{bounds[1] // 10**9}.{bounds[1] % 10**9:09d}")

        def jobs(root):
            directory = root / "processing/jobs"
            return set(directory.iterdir()) if directory.exists() else set()

        def assert_job(job, bounds):
            params = json.loads((job / "params.json").read_bytes())
            manifest = json.loads((job / "job_manifest.json").read_bytes())
            check("real saved job retains its exact selected nanosecond parameters",
                  (params["startSessionNs"], params["endSessionNs"]) == bounds and params["checkpointSection"] is None)
            check("completed current numeric job reports that selected interval",
                  (manifest["timeRange"]["startSessionNs"], manifest["timeRange"]["endSessionNs"]) == bounds
                  and manifest["status"] == "completed")
            return params, manifest

        def finish():
            timer.stop()
            shell.close()
            app.quit()

        def tick():
            try:
                modal = QApplication.activeModalWidget()
                if isinstance(modal, QMessageBox):
                    state["dialogs"].append(modal.text())
                    modal.accept()
                if state["cancelled"]:
                    if screen._thread is None:
                        finish()
                    return
                if time.monotonic() > state["deadline"]:
                    raise TimeoutError("The bounded native scope/history journey did not finish.")
                phase = state["phase"]
                if phase == "start":
                    screen.set_package(str(first) + "/.")
                    check("screen, header and history use one normalized package identity",
                          screen.package_path == header.package_path == screen._history.package == str(first))
                    screen._command.setCurrentIndex(screen._command.findData("features"))
                    choose(ranges[0])
                    check("real header selection enables the composed Analysis screen with exact bounds",
                          screen._btn_run.isEnabled() and screen.scope is picker.selection
                          and (screen.scope.start_ns, screen.scope.end_ns) == ranges[0])
                    QTest.mouseClick(screen._btn_run, Qt.MouseButton.LeftButton)
                    check("real feature worker disables saved-history actions while running",
                          screen._thread is not None and not screen._history._open.isEnabled()
                          and not screen._history._refresh.isEnabled())
                    state["phase"] = "first-job"
                elif phase == "first-job" and screen._thread is None:
                    check("the first real worker completes without a modal failure", not state["dialogs"])
                    check("completed scoped job reaches the saved-history viewer",
                          len(jobs(first)) == 1 and bool(screen._last_job_dir)
                          and screen._history.loaded_job_id == Path(screen._last_job_dir).name)
                    job = Path(screen._last_job_dir)
                    assert_job(job, ranges[0])
                    state["first_job"] = job
                    state["saved_bytes"] = hashes(job)
                    choose(ranges[1])
                    selected = screen.scope
                    QTest.mouseClick(screen._history._refresh, Qt.MouseButton.LeftButton)
                    QTest.mouseClick(screen._history._open, Qt.MouseButton.LeftButton)
                    check("explicitly reopening the old job preserves the next selected scope",
                          screen.scope == picker.selection == selected
                          and (selected.start_ns, selected.end_ns) == ranges[1])
                    check("reopen is read-only and starts no additional worker",
                          hashes(job) == state["saved_bytes"] and jobs(first) == {job}
                          and screen._thread is None)
                    QTest.mouseClick(screen._history._details, Qt.MouseButton.LeftButton)
                    dialog = screen._history._dialog
                    params_editor = dialog.findChild(QPlainTextEdit, "analysisHistoryParameters")
                    saved_params = json.loads(params_editor.toPlainText())
                    check("native read-only details show the saved scope, distinct from the next selection",
                          params_editor.isReadOnly()
                          and (saved_params["startSessionNs"], saved_params["endSessionNs"]) == ranges[0]
                          and screen.scope == selected)
                    dialog.close()
                    screen.set_package(str(first) + "/.")
                    check("same-package refresh preserves both scope and loaded saved result",
                          screen.scope == picker.selection == selected
                          and screen._history.loaded_job_id == job.name)
                    state["phase"] = "capture-and-second-job"
                elif phase == "capture-and-second-job":
                    check("combined native frame is captured", shell.grab().save(str(output / "scope-history-reopened.png")))
                    state["jobs_before_second"] = jobs(first)
                    QTest.mouseClick(screen._btn_run, Qt.MouseButton.LeftButton)
                    check("a second real worker starts from the next selection", screen._thread is not None)
                    # The current application may change package context while a
                    # worker is pending. Its real queued completion must stay A.
                    screen.set_package(str(second))
                    check("changing package resets scope and clears history as one transition",
                          screen.package_path == header.package_path == screen._history.package == str(second)
                          and screen.scope.mode == picker.selection.mode == "full"
                          and not screen._last_job_dir and not screen._history.loaded_job_id)
                    state["phase"] = "second-job"
                elif phase == "second-job" and screen._thread is None:
                    completed = jobs(first) - state["jobs_before_second"]
                    check("late real completion is retained under its originating package only",
                          len(completed) == 1 and not jobs(second) and not state["dialogs"])
                    second_job = next(iter(completed))
                    assert_job(second_job, ranges[1])
                    check("late foreign completion cannot repaint current history or scope",
                          screen.package_path == str(second) and screen.scope.mode == picker.selection.mode == "full"
                          and not screen._last_job_dir and not screen._history.loaded_job_id
                          and "Result saved for the previous package" in screen._log.toPlainText())
                    check("the prior reopened job remains byte-identical after the second job",
                          hashes(state["first_job"]) == state["saved_bytes"])
                    check("both real package raw inputs remain byte-identical",
                          all(hashes(p, raw_only=True) == raw_before[str(p)] for p in [first, second]))
                    report["real_jobs"] = [str(state["first_job"]), str(second_job)]
                    report["raw_package_hashes"] = raw_before
                    report["last_native_log"] = screen._log.toPlainText()
                    report["dialogs"] = state["dialogs"]
                    finish()
            except BaseException:
                report["errors"].append(traceback.format_exc())
                state["cancelled"] = True
                if screen._thread is not None:
                    screen._cancel_job()
                else:
                    finish()

        timer = QTimer()
        timer.timeout.connect(tick)
        timer.start(15)
        report["event_loop_exit"] = app.exec()
        shell.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        report["pyside6"] = PySide6.__version__
        report["python"] = sys.version
    except BaseException:
        report["errors"].append(traceback.format_exc())
    report["source_unchanged"] = hashes(source) == expected
    report["passed"] = sum(row["passed"] for row in report["checks"])
    report["failed"] = sum(not row["passed"] for row in report["checks"])
    report["exit_code"] = 0 if not report["errors"] and not report["failed"] and report["source_unchanged"] else 1
    (output / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["passed", "failed", "source_unchanged", "exit_code"]}))
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
