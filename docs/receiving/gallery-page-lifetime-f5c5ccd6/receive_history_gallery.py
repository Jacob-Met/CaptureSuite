# SPDX-License-Identifier: GPL-3.0-only
"""Native current history/gallery composition receiving on synthetic MCAP data."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--out", required=True)
parser.add_argument("--variant", required=True)
args = parser.parse_args()
SOURCE = Path(args.source).resolve()
OUT = Path(args.out).resolve() / args.variant
OUT.mkdir(parents=True, exist_ok=False)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
for name, subdir in (
    ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
    ("XDG_CACHE_HOME", "cache"), ("LOCALAPPDATA", "local"),
    ("APPDATA", "roaming"), ("MPLCONFIGDIR", "matplotlib"),
):
    folder = OUT / "state" / subdir
    folder.mkdir(parents=True)
    os.environ[name] = str(folder)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
for part in ("desktop", "libs/python/capture_protocol", "libs/python/capture_session",
             "libs/python/capture_analysis"):
    sys.path.insert(0, str(SOURCE / part))

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, qVersion
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPlainTextEdit, QScrollArea
from shiboken6 import isValid

from capture_desktop import theme
from capture_desktop.screen_analysis import AnalysisScreen
from capture_desktop.state import CaptureState
from capture_desktop.widgets_analysis_scope import ScopeSelection

CHECKS = []
OBSERVATIONS = {}
WARNINGS = []
app = QApplication.instance() or QApplication([])
theme.apply_theme(app, setting="dark")
screen = None


def git(*values):
    return subprocess.check_output(["git", *values], cwd=SOURCE).decode().strip()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root, *, raw_only=False):
    return {
        p.relative_to(root).as_posix(): sha(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and (not raw_only or p.relative_to(root).parts[0] != "processing")
    }


def source_state():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=SOURCE).split(b"\0")
    hashes = {
        name.decode(): sha(SOURCE / name.decode()) for name in names
        if name and (SOURCE / name.decode()).is_file()
    }
    return {"head": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "status": git("status", "--short"), "files": hashes}


def check(name, condition, **details):
    CHECKS.append({"name": name, "pass": bool(condition), **details})
    print(json.dumps(CHECKS[-1]), flush=True)


def drain():
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def await_condition(predicate, milliseconds=60000):
    if predicate():
        drain()
        return True
    loop = QEventLoop()
    deadline = QTimer()
    deadline.setSingleShot(True)
    poll = QTimer()
    poll.setInterval(10)

    def tick():
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox):
                WARNINGS.append(widget.text())
                widget.accept()
        if predicate():
            loop.quit()

    deadline.timeout.connect(loop.quit)
    poll.timeout.connect(tick)
    deadline.start(milliseconds)
    poll.start()
    loop.exec()
    poll.stop()
    deadline.stop()
    drain()
    return predicate()


def figure_pages(gallery):
    return [
        area for area in gallery._tabs.findChildren(QScrollArea)
        if isinstance(area.widget(), QLabel)
    ]


def source_pins(before):
    expected = {
        "current_main": "11cc78297d8d214407aea693548af4de855d61da",
        "history_pr71": "8747cb95bfb2ac91aa4f1ff604ad677f3597fa12",
        "gallery_pr80": "837fa1fbf2c5ad471cbb3924c212fc08d0e0f0ed",
    }
    for name, pin in expected.items():
        result = subprocess.run(["git", "merge-base", "--is-ancestor", pin, "HEAD"], cwd=SOURCE)
        check(name + "_is_real_ancestor", result.returncode == 0, commit=pin)
    OBSERVATIONS["source_before"] = before


started = time.monotonic()
setup_error = None
before = source_state()
try:
    source_pins(before)
    fixture_path = SOURCE / "tests/analysis/test_numeric_cli_receiving.py"
    spec = importlib.util.spec_from_file_location("capture_numeric_fixture_receiver", fixture_path)
    fixture = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(fixture)
    package = fixture.make_package(OUT / "synthetic-input.mmsession")
    untouched = files(package, raw_only=True)
    OBSERVATIONS["fixture_builder"] = {
        "path": str(fixture_path.relative_to(SOURCE)),
        "sha256": sha(fixture_path),
        "use": "only public synthetic protobuf/MCAP fixture constructor; no prior assertions run",
    }
    screen = AnalysisScreen(CaptureState())
    screen.resize(1280, 860)
    screen.set_package(str(package))
    scope = ScopeSelection(mode="range", start_ns=1500000000, end_ns=3000000000)
    screen.set_scope(str(package), scope)
    screen._command.setCurrentIndex(screen._command.findData("plots"))
    assert screen._btn_run.isEnabled(), screen._scope_note.text()
    screen._btn_run.click()
    check("real_analysis_thread_disables_saved_history",
          screen._thread is not None and not screen._history._open.isEnabled()
          and not screen._history._refresh.isEnabled())
    completed = await_condition(lambda: screen._thread is None)
    assert completed, "real analysis thread exceeded receiver deadline"
    assert screen._last_job_dir, screen._log.toPlainText()
    job = Path(screen._last_job_dir)
    manifest = json.loads((job / "job_manifest.json").read_text())
    params = json.loads((job / "params.json").read_text())
    check("real_range_job_completes_into_saved_history",
          manifest["status"] == "completed"
          and screen._history.loaded_job_id == job.name
          and screen._history._open.isEnabled(),
          status=manifest["status"], job_id=job.name)
    check("current_job_provenance_preserves_scope_and_sync_refusal_contract",
          params["startSessionNs"] == 1500000000
          and params["endSessionNs"] == 3000000000
          and manifest["syncAnchorsApplied"]["applied"] is False
          and screen.scope == scope)
    gallery = screen._gallery
    nested = sorted((job / "figures/numeric").rglob("*.png"))
    assert len(nested) == 3, [str(p.relative_to(job)) for p in nested]
    expected_tips = {p.relative_to(job / "figures").as_posix() for p in nested}
    tips = {gallery._tabs.tabToolTip(i) for i in range(1, gallery._tabs.count())}
    check("real_nested_artifacts_reach_history_gallery", expected_tips <= tips,
          expected=sorted(expected_tips), observed=sorted(tips))
    check("nested_png_pixels_decode",
          all(not gallery._tabs.widget(i).widget().pixmap().isNull()
              for i in range(1, gallery._tabs.count())))
    retained = files(package)
    initial_pages = figure_pages(gallery)
    initial_count = len(initial_pages)
    assert initial_count == len(tips)
    page_counts = [initial_count]
    old_pages = []
    for _ in range(3):
        old_pages.extend(gallery._tabs.widget(i) for i in range(1, gallery._tabs.count()))
        screen._history._open.click()
        drain()
        page_counts.append(len(figure_pages(gallery)))
    check("reopening_saved_nested_results_releases_old_qt_pages",
          page_counts == [initial_count] * 4 and not any(isValid(p) for p in old_pages),
          qt_figure_page_counts=page_counts,
          replaced_pages_still_alive=sum(isValid(p) for p in old_pages))
    check("reopen_keeps_scope_and_exact_job_association",
          screen.scope == scope and screen._last_job_dir == str(job)
          and screen._history.loaded_job_id == job.name
          and f"job_id={job.name}" in screen._inspector._meta.text())
    screen._history._details.click()
    drain()
    details = screen._history._dialog
    assert details is not None
    editors = {p.objectName(): p for p in details.findChildren(QPlainTextEdit)}
    check("history_details_keep_exact_saved_params_read_only",
          all(p.isReadOnly() for p in editors.values())
          and json.loads(editors["analysisHistoryParameters"].toPlainText()) == params)
    details.close()
    drain()
    bar = gallery._figure_export
    assert bar._source is not None
    export_paths = {p.relative_path for p in bar._source.figures}
    check("export_source_tracks_same_nested_job",
          bar._source.job_id == job.name
          and {p.relative_to(job).as_posix() for p in nested} <= export_paths,
          selected_job=bar._source.job_id, recorded_figure_count=len(export_paths))
    bar._button.click()
    drain()
    dialog = bar._dialog
    assert dialog is not None
    destination = OUT / "nested-figures.zip"
    dialog._destination.setText(str(destination))
    dialog._selection_changed()
    dialog._export.click()
    check("native_figure_export_starts_real_thread", dialog._worker is not None)
    assert await_condition(lambda: dialog._worker is None), "export thread deadline"
    assert destination.is_file(), dialog._status.text()
    with zipfile.ZipFile(destination) as archive:
        members = set(archive.namelist())
        exact_nested = all(
            p.relative_to(job).as_posix() in members
            and archive.read(p.relative_to(job).as_posix()) == p.read_bytes()
            for p in nested
        )
        check("exported_nested_png_bytes_match_saved_artifacts", exact_nested,
              zip_sha256=sha(destination), zip_members=sorted(members))
    screen.show()
    drain()
    screen.grab().save(str(OUT / "native-history-nested-gallery.png"))
    screen._history._open.click()
    drain()
    check("history_reopen_invalidates_finished_export_dialog",
          bar._dialog is None and not isValid(dialog) and bar._source.job_id == job.name)
    check("browsing_details_reopen_export_leave_source_unchanged",
          files(package) == retained and files(package, raw_only=True) == untouched)
    alternate = OUT / "other-input.mmsession"
    shutil.copytree(package, alternate, ignore=shutil.ignore_patterns("processing"))
    last_pages = list(figure_pages(gallery))
    screen.set_package(str(alternate))
    drain()
    check("package_switch_releases_pages_and_saved_export_identity",
          gallery._tabs.count() == 1 and not figure_pages(gallery)
          and not any(isValid(p) for p in last_pages)
          and bar._source is None and not bar._button.isEnabled()
          and not screen._history.loaded_job_id and not screen._last_job_dir,
          retained_pages_after_switch=len(figure_pages(gallery)))
    OBSERVATIONS["raw_fixture_sha256"] = untouched
    OBSERVATIONS["job_manifest_sha256"] = sha(job / "job_manifest.json")
    OBSERVATIONS["job_params_sha256"] = sha(job / "params.json")
except Exception:
    setup_error = traceback.format_exc()
    print(setup_error, flush=True)
finally:
    if screen is not None:
        if screen._thread is not None:
            screen._cancel_job()
            await_condition(lambda: screen._thread is None, 10000)
        screen.close()
        screen.deleteLater()
    drain()
    after = source_state()
    check("tracked_source_unchanged_during_receiver", before == after)
    receipt = {
        "schema": "capturesuite.native_history_gallery_composition.v1",
        "variant": args.variant,
        "runtime": {"python": sys.version, "qt": qVersion(),
                    "packages": {name: importlib.metadata.version(name) for name in
                                 ("PySide6", "numpy", "scipy", "pyarrow", "matplotlib", "mcap")}},
        "source_before": before, "source_after": after,
        "checks": CHECKS, "passed": sum(row["pass"] for row in CHECKS),
        "failed": sum(not row["pass"] for row in CHECKS),
        "setup_error": setup_error, "warnings": WARNINGS,
        "elapsed_seconds": time.monotonic() - started,
        "observations": OBSERVATIONS,
        "scope": "new current composition on real synthetic MCAP, real native Qt and real worker threads; no hardware, service or private capture",
    }
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: receipt[key] for key in
                      ("variant", "passed", "failed", "setup_error", "elapsed_seconds")}), flush=True)

raise SystemExit(0 if setup_error is None and all(row["pass"] for row in CHECKS) else 1)
