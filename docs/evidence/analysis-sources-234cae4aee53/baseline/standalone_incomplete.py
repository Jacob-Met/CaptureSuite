# SPDX-License-Identifier: GPL-3.0-only
import hashlib, json, os, subprocess, tempfile, time
from pathlib import Path

repo = Path.cwd()
before = {p: hashlib.sha256((repo / p).read_bytes()).hexdigest()
          for p in subprocess.check_output(["git", "ls-files"], text=True).splitlines()}
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
with tempfile.TemporaryDirectory(prefix="source-baseline-", dir="/dev/shm/capturesuite-234cae4aee53") as td:
    root = Path(td)
    for key in ("LOCALAPPDATA", "APPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        folder = root / key
        folder.mkdir()
        os.environ[key] = str(folder)
    from tests.analysis.test_numeric_cli_receiving import make_package, retained_files, write_json
    from capture_analysis.discover import discover_streams
    from capture_session import load_review_summary
    from capture_desktop.screen_analysis import AnalysisScreen
    from capture_desktop.state import CaptureState
    from PySide6.QtCore import Qt, QTimer, QCoreApplication, QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox
    app = QApplication.instance() or QApplication([])
    package = make_package(root / "folder mismatch μ.mmsession")
    (package / "sources" / "sampler.a").rename(package / "sources" / "folder-a")
    integrity = json.loads((package / "integrity.json").read_text())
    for item in integrity["files"]:
        item["path"] = item["path"].replace("sources/sampler.a/", "sources/folder-a/")
    write_json(package / "integrity.json", integrity)
    raw = retained_files(package)
    summary = load_review_summary(package)
    ids = sorted({ref.source_id for ref in discover_streams(package)})
    assert summary.source_ids == ["folder-a", "sampler.b"], summary.source_ids
    assert ids == ["sampler.a", "sampler.b"], ids
    screen = AnalysisScreen(CaptureState())
    screen.set_package(str(package))
    controls = [w for w in screen.findChildren(QComboBox)
                if w.accessibleName() == "Analysis source mode"]
    assert not controls, "baseline already exposes the proposed source picker"
    screen._command.setCurrentIndex(screen._command.findData("features"))
    dialogs = []
    def close_dialog():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            dialogs.append(dialog.text())
            dialog.accept()
    timer = QTimer()
    timer.timeout.connect(close_dialog)
    timer.start(20)
    try:
        assert screen._btn_run.isEnabled()
        screen._start_job()
        until = time.monotonic() + 120
        while screen._thread is not None and time.monotonic() < until:
            QTest.qWait(20)
        assert screen._thread is None, "baseline worker did not finish"
        assert not dialogs, dialogs
        assert screen._last_job_dir, screen._log.toPlainText()
        job = Path(screen._last_job_dir)
        manifest = json.loads((job / "job_manifest.json").read_text())
        params = json.loads((job / "params.json").read_text())
        tables = json.loads((job / "features" / "_schema.json").read_text())["tables"]
        identities = sorted([d["sourceId"], d["streamId"]] for d in tables.values())
        assert params["sources"] == []
        assert manifest["sourcesSelected"] == ids
        assert identities == [["sampler.a", "force"], ["sampler.a", "voltage"],
                              ["sampler.b", "temperature"]], identities
        assert retained_files(package) == raw
        record = {"source_head": head, "baseline_control": "no operator-accessible source picker",
                  "review_directory_ids": summary.source_ids, "analysis_descriptor_ids": ids,
                  "actual_default_job": {"params": params, "manifest": manifest,
                                         "feature_identities": identities},
                  "raw_sha256": raw, "raw_unchanged": True, "dialogs": dialogs}
    finally:
        if screen._thread is not None:
            screen._cancel_job()
            while screen._thread is not None:
                QTest.qWait(20)
        timer.stop()
        screen.close()
        screen.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
after = {p: hashlib.sha256((repo / p).read_bytes()).hexdigest() for p in before}
assert before == after
record["source_files_checked"] = len(before)
record["source_unchanged"] = True
record["git_status_after"] = subprocess.check_output(["git", "status", "--porcelain"], text=True)
print("RECEIPT=" + json.dumps(record, sort_keys=True))
