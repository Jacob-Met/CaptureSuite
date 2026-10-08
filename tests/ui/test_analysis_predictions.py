# SPDX-License-Identifier: GPL-3.0-only
"""Native evaluation input controls and the actual workbench consumer."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QEventLoop, Qt, QThread, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


@pytest.fixture
def extras(qapp, tmp_path):
    from capture_desktop.widgets_analysis_jobs import AnalysisJobExtras

    widget = AnalysisJobExtras()
    widget.set_package(str(tmp_path))
    widget.set_command("eval")
    widget._bundle_job.setEditText("bundle")
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    qapp.processEvents()


def _external(extras):
    control = extras._evaluation
    control._mode.setCurrentIndex(control._mode.findData("external"))
    return control


def _chosen(control, monkeypatch, filename):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_a, **_k: (str(filename), ""))
    control._choose_button.click()


def _real_choose(control, filename: Path | None):
    """Drive the actual Qt file dialog with literal names and bounded cleanup."""
    from PySide6.QtWidgets import QAbstractItemView, QDialogButtonBox, QLineEdit

    previous = QApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    selected = []
    failures = []
    started = time.monotonic()
    attempted = False
    prepared = False
    row_clicked = False
    selection_ticks = 0
    driver = QTimer()
    watchdog = QTimer()

    def unwind(reason):
        if not failures:
            failures.append(reason)
        # A failed accept can enter a second modal loop. Close that message
        # before the file dialog, so both nested loops return to the assertion.
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                widget.reject()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QFileDialog) and widget.isVisible():
                widget.reject()

    def check_deadline():
        active = QApplication.activeModalWidget()
        if isinstance(active, QMessageBox):
            unwind(f"Unexpected file-dialog message: {active.text()}")
        elif time.monotonic() - started >= 5:
            unwind("The actual Qt file dialog did not complete within five seconds.")

    def finish():
        nonlocal attempted, prepared, row_clicked, selection_ticks
        try:
            active = QApplication.activeModalWidget()
            if failures or attempted or not isinstance(active, QFileDialog):
                return
            if filename is None:
                attempted = True
                driver.stop()
                selected.append(None)
                active.reject()
                return
            if not prepared:
                active.selectNameFilter("All files (*)")
                active.setDirectory(str(filename.parent))
                prepared = True
                return

            # Existing fixtures are selected through the actual file view.
            # Match the model's literal filename; never accept a normalized
            # substitute. Some Qt widget models cannot represent every OS name.
            if filename.is_file() and not row_clicked:
                for view in active.findChildren(QAbstractItemView):
                    if not view.isVisible() or view.objectName() not in ("listView", "treeView"):
                        continue
                    model = view.model()
                    for row in range(model.rowCount(view.rootIndex())):
                        index = model.index(row, 0, view.rootIndex())
                        if index.data() != filename.name:
                            continue
                        view.scrollTo(index)
                        rectangle = view.visualRect(index)
                        if not rectangle.isValid():
                            continue
                        QTest.mouseClick(
                            view.viewport(), Qt.MouseButton.LeftButton, pos=rectangle.center()
                        )
                        row_clicked = True
                        return
                return
            if not filename.is_file():
                # The deliberate missing-file regression exercises Qt's error
                # dialog and the independent watchdog, rather than a mock.
                edit = active.findChild(QLineEdit, "fileNameEdit")
                assert edit is not None
                edit.setFocus()
                edit.setText(f'"{filename.name}"')
            else:
                selection_ticks += 1
                if selection_ticks < 3:
                    return

            actual = active.selectedFiles()
            assert len(actual) == 1 and Path(actual[0]) == filename, (
                f"Qt selected {actual!r}, expected literal path {str(filename)!r}"
            )
            if filename.is_file():
                assert Path(actual[0]).samefile(filename)
                assert Path(actual[0]).name == filename.name
            selected.extend(actual)
            attempted = True
            driver.stop()
            if filename.is_file():
                box = active.findChild(QDialogButtonBox)
                assert box is not None
                button = next(
                    button for button in box.buttons()
                    if box.buttonRole(button) == QDialogButtonBox.ButtonRole.AcceptRole
                )
                assert button.isEnabled()
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
            else:
                active.accept()
        except Exception as exc:
            unwind(f"Actual Qt file choice failed: {exc!r}")

    driver.timeout.connect(finish)
    watchdog.timeout.connect(check_deadline)
    driver.start(40)
    watchdog.start(25)
    try:
        control._choose_button.click()
    finally:
        driver.stop()
        watchdog.stop()
        QApplication.setAttribute(
            Qt.ApplicationAttribute.AA_DontUseNativeDialogs, previous
        )
    assert not failures, failures
    assert attempted and len(selected) == 1
    return selected[0]


def test_default_identity_and_roundtrip_omit_the_retained_external_path(
    extras, monkeypatch, tmp_path
):
    assert extras.build_extra("eval") == {"ml_bundle_job_id": "bundle"}
    assert extras.validate_for("eval") is None
    control = _external(extras)
    path = tmp_path / " predictions café .json"
    path.write_text("{}", encoding="utf-8")
    _chosen(control, monkeypatch, path)
    control._mode.setCurrentIndex(control._mode.findData("identity"))
    assert extras.build_extra("eval") == {"ml_bundle_job_id": "bundle"}
    assert extras.validate_for("eval") is None
    control._mode.setCurrentIndex(control._mode.findData("external"))
    assert extras.build_extra("eval")["prediction_path"] == str(path)


def test_empty_external_choice_is_explicit_and_actionable(extras):
    _external(extras)
    assert extras.build_extra("eval") == {"ml_bundle_job_id": "bundle", "prediction_path": ""}
    assert "Choose a predictions JSON file" in extras.validate_for("eval")


def test_actual_qt_file_choice_cancel_and_reselection(extras, tmp_path):
    control = _external(extras)
    first = tmp_path / "first prediction café .json"
    second = tmp_path / "second prediction.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")
    actual = _real_choose(control, first)
    assert Path(actual).samefile(first)
    assert control._path.text() == actual
    assert extras.validate_for("eval") is None
    _real_choose(control, None)
    assert control._path.text() == actual
    newer = _real_choose(control, second)
    assert Path(newer).samefile(second)
    assert extras.build_extra("eval")["prediction_path"] == newer


def test_actual_qt_leading_space_is_exact_or_refuses_without_replacing_path(
    extras, tmp_path, record_property
):
    control = _external(extras)
    kept = tmp_path / "kept prediction.json"
    literal = tmp_path / " first prediction .json"
    kept.write_text("{}", encoding="utf-8")
    literal.write_text("{}", encoding="utf-8")
    previous = _real_choose(control, kept)
    assert control._path.text() == previous
    started = time.monotonic()
    try:
        selected = _real_choose(control, literal)
    except AssertionError as exc:
        # Qt 6.12's Windows widget model was observed dropping this leading
        # space despite the literal OS file existing. Refusal must be bounded
        # and leave the previously admitted path untouched.
        assert time.monotonic() - started < 6
        assert "file dialog" in str(exc) or "file choice" in str(exc)
        assert QApplication.activeModalWidget() is None
        assert control._path.text() == previous
        assert extras.build_extra("eval")["prediction_path"] == previous
        branch = "bounded-refusal"
    else:
        assert Path(selected) == literal
        assert Path(selected).samefile(literal)
        assert Path(selected).name == literal.name
        assert control._path.text() == selected
        assert extras.build_extra("eval")["prediction_path"] == selected
        branch = "exact-selection"
    assert literal.name in os.listdir(tmp_path)
    record_property("literal_file_choice", branch)
    print(f"Literal leading-space Qt widget choice: {branch}", flush=True)


def test_actual_qt_file_choice_error_unwinds_without_replacing_path(
    extras, monkeypatch, tmp_path
):
    control = _external(extras)
    kept = tmp_path / "kept.json"
    kept.write_text("{}")
    with monkeypatch.context() as patch:
        _chosen(control, patch, kept)
    # The failing attempt uses the real Qt dialog after the seed hook is gone.
    started = time.monotonic()
    with pytest.raises(AssertionError, match="file.dialog"):
        _real_choose(control, tmp_path / "does-not-exist.json")
    assert time.monotonic() - started < 6
    assert QApplication.activeModalWidget() is None
    assert control._path.text() == str(kept)


def test_clear_keeps_external_and_moves_keyboard_focus_to_choose(extras, monkeypatch, tmp_path):
    control = _external(extras)
    path = tmp_path / "file.json"
    path.write_text("{}")
    _chosen(control, monkeypatch, path)
    control._clear_button.setFocus()
    QTest.keyClick(control._clear_button, Qt.Key.Key_Space)
    assert control._mode.currentData() == "external"
    assert extras.build_extra("eval")["prediction_path"] == ""
    assert not control._clear_button.isEnabled()
    assert QApplication.focusWidget() is control._choose_button


@pytest.mark.parametrize("kind", ["missing", "directory", "nul"])
def test_unavailable_file_never_becomes_identity(extras, monkeypatch, tmp_path, kind):
    control = _external(extras)
    filename = {
        "missing": str(tmp_path / "gone.json"), "directory": str(tmp_path), "nul": "\0",
    }[kind]
    _chosen(control, monkeypatch, filename)
    assert "unavailable" in extras.validate_for("eval")
    assert extras.build_extra("eval")["prediction_path"] == filename


def test_removed_file_choice_is_retained_for_reselection(extras, monkeypatch, tmp_path):
    control = _external(extras)
    path = tmp_path / "removed.json"
    path.write_text("{}")
    _chosen(control, monkeypatch, path)
    assert extras.validate_for("eval") is None
    path.unlink()
    assert extras.validate_for("eval") is not None
    assert control._path.text() == str(path)
    assert control._mode.currentData() == "external"


@pytest.mark.parametrize(
    "command", ["qc", "features", "plots", "all", "pose", "kinematics", "ml_bundle"],
)
def test_other_commands_never_receive_prediction_path_and_keep_legacy_fields(
    extras, monkeypatch, tmp_path, command
):
    control = _external(extras)
    path = tmp_path / "chosen.json"
    path.write_text("{}")
    _chosen(control, monkeypatch, path)
    extras._pose_job.setEditText("pose-original")
    extras._kin_job.setEditText("kin-original")
    extras._feat_job.setEditText("features-original")
    extras._window_sec.setText("2.5")
    extras._hop_sec.setText("0.125")
    extras.set_command(command)
    assert control.isHidden()
    actual = extras.build_extra(command)
    assert "prediction_path" not in actual
    if command == "kinematics":
        assert actual == {"pose_job_id": "pose-original"}
    elif command == "ml_bundle":
        assert actual == {
            "kinematics_job_id": "kin-original", "features_job_id": "features-original",
            "window_sec": 2.5, "hop_sec": 0.125,
        }
    extras.set_command("eval")
    assert extras.build_extra("eval")["prediction_path"] == str(path)


def test_same_package_refresh_keeps_choice_and_new_package_clears_only_file(
    extras, monkeypatch, tmp_path
):
    control = _external(extras)
    path = tmp_path / "selected.json"
    path.write_text("{}")
    _chosen(control, monkeypatch, path)
    extras.set_package(str(tmp_path / "."))
    assert control._path.text() == str(path)
    extras.set_package(str(tmp_path / "other"))
    assert control._mode.currentData() == "external"
    assert control._path.text() == ""
    assert "prediction_path" in extras.build_extra("eval")
    assert extras.validate_for("eval") is not None


@pytest.mark.parametrize("change", ["package", "command", "mode", "busy", "clear", "newer"])
def test_old_modal_choice_cannot_replace_newer_context(extras, monkeypatch, tmp_path, change):
    control = _external(extras)
    paths = [tmp_path / (name + ".json") for name in ["kept", "late", "newer"]]
    for path in paths:
        path.write_text("{}")
    _chosen(control, monkeypatch, paths[0])

    def during_dialog(*_args, **_kwargs):
        if change == "package":
            extras.set_package(str(tmp_path / "other"))
        elif change == "command":
            extras.set_command("qc")
            extras.set_command("eval")
        elif change == "mode":
            control._mode.setCurrentIndex(control._mode.findData("identity"))
            control._mode.setCurrentIndex(control._mode.findData("external"))
        elif change == "busy":
            extras.set_eval_busy(True)
            extras.set_eval_busy(False)
        elif change == "clear":
            control._clear()
        else:
            _chosen(control, monkeypatch, paths[2])
        return str(paths[1]), ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", during_dialog)
    control._choose_button.click()
    expected = (
        "" if change in {"package", "clear"}
        else str(paths[2] if change == "newer" else paths[0])
    )
    assert control._path.text() == expected


def test_reserved_not_yet_started_worker_disables_run_and_allows_cancel(qapp):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    thread = QThread()
    screen._thread = thread
    try:
        screen._sync_enabled()
        assert not thread.isRunning()
        assert not screen._extras._evaluation.isEnabled()
        assert not screen._command.isEnabled()
        assert not screen._btn_run.isEnabled()
        assert screen._btn_cancel.isEnabled()
        screen._summary = object()  # Start must refuse even with an admitted package.
        screen._start_job()
        assert screen._thread is thread
        screen._summary = None
    finally:
        screen._thread = None
        screen._sync_enabled()
        assert screen._extras._evaluation.isEnabled()
        thread.deleteLater()
        screen.close()
        screen.deleteLater()


def _snapshot(package, predictions):
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*package.rglob("*"), predictions] if p.is_file()
    }


def _preserved(snapshot):
    for filename, wanted in snapshot.items():
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == wanted


def _wait(screen, qapp, seconds=90):
    if screen._thread is None:
        return
    # Use the same native event loop as the app. Repeated QTest.qWait calls can
    # starve a Python worker rendering matplotlib figures on some Qt platforms.
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    screen._thread.finished.connect(loop.quit)
    timer.start(seconds * 1000)
    loop.exec()
    timer.stop()
    qapp.processEvents()
    assert screen._thread is None, "Native worker did not finish within the bounded gate."


def _screen(qapp, package):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState

    screen = AnalysisScreen(CaptureState())
    screen.resize(1420, 1000)
    screen.set_package(str(package))
    screen._command.setCurrentIndex(screen._command.findData("eval"))
    screen._extras._bundle_job.setEditText("bundle")
    screen.show()
    qapp.processEvents()
    return screen


def _finish_screen(screen, qapp):
    if screen._thread is not None:
        screen._cancel_job()
        _wait(screen, qapp)
    screen.close()
    screen.deleteLater()
    qapp.processEvents()


def test_actual_external_file_runs_through_native_workbench(qapp, tmp_path, monkeypatch):
    from tests.analysis.test_external_predictions import _fixture

    package, predictions, windows, manifest = _fixture(tmp_path)
    before = _snapshot(package, predictions)
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_a: errors.append(_a[-1]))
    screen = _screen(qapp, package)
    try:
        control = _external(screen._extras)
        chosen = _real_choose(control, predictions)
        screen._btn_run.click()
        assert screen._thread is not None
        assert not control.isEnabled()
        assert not screen._btn_run.isEnabled()
        assert screen._btn_cancel.isEnabled()
        _wait(screen, qapp)
        assert not errors
        assert control.isEnabled()
        assert screen._btn_run.isEnabled()
        assert not screen._btn_cancel.isEnabled()
        job = Path(screen._last_job_dir)
        params = json.loads((job / "params.json").read_text())
        assert params["extra"] == {"ml_bundle_job_id": "bundle", "prediction_path": chosen}
        report = json.loads((job / "eval/eval_report.json").read_text())
        assert report["evaluationMode"] == "external_predictions"
        assert report["baseline"] is None
        assert report["modelId"] == "synthetic-offset-control"
        assert (job / "eval/prediction_input.json").read_bytes() == predictions.read_bytes()
        assert report["inputProvenance"]["predictionsSha256"] == before[str(predictions)]
        assert report["inputProvenance"]["windowsSha256"] == before[str(windows)]
        assert report["inputProvenance"]["manifestSha256"] == before[str(manifest)]
        figures = sorted((job / "eval/figures").glob("*.png"))
        assert len(figures) == 2 and all(not QPixmap(str(p)).isNull() for p in figures)
        assert screen._btn_open_job.isEnabled()
        assert "completed" in screen._inspector._meta.text()
        _preserved(before)
    finally:
        _finish_screen(screen, qapp)


def test_invalid_external_file_refuses_without_identity_then_retries(qapp, tmp_path, monkeypatch):
    from tests.analysis.test_external_predictions import _fixture

    package, predictions, _windows, _manifest = _fixture(tmp_path)
    bad = tmp_path / "wrong-source.json"
    doc = json.loads(predictions.read_text())
    doc["windowsSha256"] = "0" * 64
    bad.write_text(json.dumps(doc), encoding="utf-8")
    before = _snapshot(package, predictions)
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_a: errors.append(_a[-1]))
    screen = _screen(qapp, package)
    try:
        control = _external(screen._extras)
        _real_choose(control, bad)
        screen._btn_run.click()
        _wait(screen, qapp)
        assert len(errors) == 1
        assert control._mode.currentData() == "external"
        assert Path(control._path.text()).samefile(bad)
        assert not list((package / "processing/jobs").glob("*/eval/eval_report.json"))
        assert screen._last_job_dir == ""
        _real_choose(control, predictions)
        screen._btn_run.click()
        _wait(screen, qapp)
        assert len(errors) == 1
        job = Path(screen._last_job_dir)
        report = json.loads((job / "eval/eval_report.json").read_text())
        assert report["evaluationMode"] == "external_predictions"
        assert (job / "eval/prediction_input.json").read_bytes() == predictions.read_bytes()
        _preserved(before)
    finally:
        _finish_screen(screen, qapp)


def test_explicit_identity_after_external_choice_uses_original_job(qapp, tmp_path, monkeypatch):
    from tests.analysis.test_external_predictions import _fixture

    package, predictions, _windows, _manifest = _fixture(tmp_path)
    before = _snapshot(package, predictions)
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_a: errors.append(_a[-1]))
    screen = _screen(qapp, package)
    try:
        control = _external(screen._extras)
        _real_choose(control, predictions)
        control._mode.setCurrentIndex(control._mode.findData("identity"))
        screen._btn_run.click()
        _wait(screen, qapp)
        assert not errors
        job = Path(screen._last_job_dir)
        assert json.loads((job / "params.json").read_text())["extra"] == {
            "ml_bundle_job_id": "bundle",
        }
        report = json.loads((job / "eval/eval_report.json").read_text())
        assert report["baseline"] == "identity_teacher_sim"
        assert not (job / "eval/prediction_input.json").exists()
        _preserved(before)
    finally:
        _finish_screen(screen, qapp)


def _settle_control_layout(screen, qapp):
    control = screen._extras._evaluation

    def ready():
        for widget in (
            control._mode, control._path, control._choose_button, control._clear_button,
        ):
            if widget.height() < widget.minimumSizeHint().height():
                return False
            if not widget.parentWidget().rect().contains(widget.geometry()):
                return False
        help_height = control._help.heightForWidth(control._help.width())
        return (
            control._help.height() >= help_height
            and control.rect().contains(control._help.geometry())
            and control.parentWidget().rect().contains(control.geometry())
        )

    loop = QEventLoop()
    timer = QTimer()
    timer.timeout.connect(lambda: loop.quit() if ready() else None)
    timer.start(10)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    deadline.start(3000)
    loop.exec()
    timer.stop()
    deadline.stop()
    qapp.processEvents()
    assert ready(), "Evaluation controls or wrapped instructions are clipped."


def _activate_window(window, qapp):
    QApplication.setActiveWindow(window)  # Qt activation; no OS-focus claim.
    loop = QEventLoop()
    poll = QTimer()
    poll.timeout.connect(
        lambda: loop.quit() if QApplication.activeWindow() is window else None
    )
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    poll.start(10)
    deadline.start(3000)
    loop.exec()
    poll.stop()
    deadline.stop()
    qapp.processEvents()
    assert QApplication.activeWindow() is window


def _check_scroll_keyboard(screen, window, qapp):
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QScrollArea

    scroll = screen.findChild(QScrollArea, "AnalysisControlsScroll")
    assert scroll is not None
    assert scroll.horizontalScrollBar().maximum() == 0
    control = screen._extras._evaluation
    content = scroll.widget()
    control_bottom = control.mapTo(content, QPoint()).y() + control.height()
    assert control_bottom <= screen._btn_run.mapTo(content, QPoint()).y()

    def visible(widget):
        rect = QRect(widget.mapTo(scroll.viewport(), QPoint()), widget.size())
        return scroll.viewport().rect().contains(rect)

    _activate_window(window, qapp)
    scroll.verticalScrollBar().setValue(0)
    screen._btn_browse.setFocus()
    run_initially_clipped = not visible(screen._btn_run)
    expected = {
        "mode": control._mode, "path": control._path, "choose": control._choose_button,
        "clear": control._clear_button, "run": screen._btn_run,
    }
    seen = set()
    cleared = False
    for _step in range(40):
        focus = QApplication.focusWidget()
        assert focus is not None
        for name, widget in expected.items():
            if focus is widget:
                assert visible(widget), f"Keyboard focus on {name} is outside the viewport."
                seen.add(name)
        if focus is screen._btn_run:
            break
        if focus is control._clear_button and not cleared:
            QTest.keyClick(focus, Qt.Key.Key_Space)
            qapp.processEvents()
            assert control._path.text() == ""
            assert control._mode.currentData() == "external"
            assert QApplication.focusWidget() is control._choose_button
            cleared = True
        else:
            QTest.keyClick(focus, Qt.Key.Key_Tab)
        qapp.processEvents()
    assert seen == set(expected)
    assert cleared
    assert visible(screen._btn_run) and visible(screen._btn_cancel)
    if run_initially_clipped:
        assert scroll.verticalScrollBar().value() > 0


@pytest.mark.parametrize("size", [(1100, 700), (1280, 960)])
def test_evaluation_controls_scroll_without_clipping(qapp, tmp_path, monkeypatch, size):
    package = Path(__file__).resolve().parents[2] / "tests/fixtures/mini_session"
    screen = _screen(qapp, package)
    try:
        control = _external(screen._extras)
        path = tmp_path / " chosen predictions café .json"
        path.write_text("{}")
        _chosen(control, monkeypatch, path)
        screen.resize(*size)
        _settle_control_layout(screen, qapp)
        assert (screen.width(), screen.height()) == size
        _check_scroll_keyboard(screen, screen, qapp)
    finally:
        _finish_screen(screen, qapp)



def test_analysis_button_space_overrides_only_its_application_shortcut(
    qapp, tmp_path, monkeypatch
):
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtGui import QKeySequence, QShortcut

    screen = AnalysisScreen(CaptureState())
    seen = []
    shortcuts = []
    for key in ("Space", "C", "Ctrl+Space"):
        shortcut = QShortcut(QKeySequence(key), screen)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(lambda name=key: seen.append(name))
        shortcuts.append(shortcut)
    try:
        screen._command.setCurrentIndex(screen._command.findData("eval"))
        screen.resize(1280, 960)
        screen.show()
        _activate_window(screen, qapp)
        control = _external(screen._extras)
        path = tmp_path / "selected.json"
        path.write_text("{}")
        _chosen(control, monkeypatch, path)
        control._clear_button.setFocus()
        assert QApplication.focusWidget() is control._clear_button
        QTest.keyClick(control._clear_button, Qt.Key.Key_Space)
        assert control._path.text() == ""
        assert seen == []

        control._choose_button.setFocus()
        QTest.keyClick(control._choose_button, Qt.Key.Key_C)
        QTest.keyClick(
            control._choose_button, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier
        )
        assert seen == ["C", "Ctrl+Space"]
        screen._banner.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        screen._banner.setFocus()
        assert QApplication.focusWidget() is screen._banner
        QTest.keyClick(screen._banner, Qt.Key.Key_Space)
        assert seen == ["C", "Ctrl+Space", "Space"]
    finally:
        screen.close()
        screen.deleteLater()
        qapp.processEvents()


@pytest.mark.skipif(os.name != "nt", reason="Real MainWindow imports Windows named-pipe APIs.")
def test_evaluation_controls_in_actual_minimum_main_window(qapp, tmp_path, monkeypatch):
    from capture_desktop.app import MainWindow

    window = MainWindow(auto_connect=False)
    screen = window.analysis
    try:
        package = Path(__file__).resolve().parents[2] / "tests/fixtures/mini_session"
        screen.set_package(str(package))
        screen._command.setCurrentIndex(screen._command.findData("eval"))
        screen._extras._bundle_job.setEditText("bundle")
        control = _external(screen._extras)
        path = tmp_path / "predictions.json"
        path.write_text("{}")
        _chosen(control, monkeypatch, path)
        window.tabs.setCurrentWidget(screen)
        window.resize(1100, 700)
        window.show()
        _settle_control_layout(screen, qapp)
        assert (window.width(), window.height()) == (1100, 700)
        _check_scroll_keyboard(screen, window, qapp)
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()
