# SPDX-License-Identifier: GPL-3.0-only
"""One disjoint native QApplication.exec control of actual prior-package completion."""
from __future__ import annotations
import dataclasses
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import traceback

root = Path('/dev/shm/hamon-401c5d17da79-capturesuite-receiving')
spec = importlib.util.spec_from_file_location('receiving_helpers', root / 'methods/receive_history.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
source = helpers.DEFAULT_SOURCE
helpers.bootstrap(source)
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QMessageBox, QPushButton
from capture_desktop.state import CaptureState
import capture_analysis
Screen = helpers.load_screen('candidate', source)
app = QApplication([])
screen = Screen(CaptureState())
screen.resize(1200, 900)
screen.show()
a = root / 'fixtures/package-a.mmsession'
b = root / 'fixtures/package-b.mmsession'
ready, release = threading.Event(), threading.Event()
holder = {}
real_run = capture_analysis.run
started = time.monotonic()
phase = 'starting'
receipt = {'schema':'capturesuite.history.native-eventloop-control.v1',
           'candidate':json.loads((root / 'pins/candidate-inputs.json').read_text()),
           'method_sha256':helpers.digest(Path(__file__)),
           'loop':'QApplication.exec with QTimer; no manual processEvents or QTest.qWait',
           'events':[], 'checks':[], 'errors':[]}


def persist():
    helpers.save_json(root / 'evidence/eventloop-receipt.json', receipt)


def check(label, ok, detail=None):
    receipt['checks'].append({'label':label,'pass':bool(ok),'detail':detail})
    persist()
    print(label, bool(ok), flush=True)
    if not ok:
        raise AssertionError(label)


def held_run(package, params, **kwargs):
    try:
        actual = real_run(package, dataclasses.replace(params, overwrite_job_id='late-eventloop-actual-qc'), **kwargs)
        holder['result'] = actual
        ready.set()
        if not release.wait(30):
            raise TimeoutError('Receiving completion gate was not released')
        return actual
    except BaseException as exc:
        holder['error'] = repr(exc)
        ready.set()
        raise


def start():
    global phase
    try:
        screen.set_package(str(a))
        combo = screen.findChild(QComboBox, 'analysisHistoryJob')
        matches = [i for i in range(combo.count()) if getattr(combo.itemData(i),'job_id',None) == 'retained-prior']
        assert len(matches) == 1
        combo.setCurrentIndex(matches[0])
        screen.findChild(QPushButton,'analysisHistoryOpen').click()
        assert screen._last_job_dir == str(a / 'processing/jobs/retained-prior')
        assert len(screen._gallery._sync._linked) == 2
        screen.set_package(str(b))
        screen.set_package(str(a))
        assert not (a / 'processing/jobs/late-eventloop-actual-qc').exists()
        screen._command.setCurrentIndex(screen._command.findData('qc'))
        capture_analysis.run = held_run
        screen._btn_run.click()
        phase = 'awaiting_result'
        receipt['events'].append('actual QThread started in native application loop')
        persist()
    except BaseException:
        fail()


def fail():
    global phase
    receipt['errors'].append(traceback.format_exc())
    receipt['pass'] = False
    release.set()
    phase = 'failed_settling'
    persist()
    if screen._thread is None:
        app.exit(1)


def tick():
    global phase
    try:
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                receipt['errors'].append(widget.text())
                widget.accept()
        if phase == 'awaiting_result' and ready.is_set():
            assert 'error' not in holder, holder.get('error')
            actual = holder['result']
            check('real QC was persisted before release', (actual.job_dir / 'job_manifest.json').is_file(),
                  {'job_dir':str(actual.job_dir),'status':actual.status})
            holder['at_hold'] = helpers.snapshot(root / 'fixtures')
            screen.set_package(str(b))
            check('selected B is unbound before A completion', screen._package == str(b) and screen._last_job_dir == '' and screen._inspector._meta.text() == 'No job loaded')
            phase = 'awaiting_thread_finish'
            receipt['events'].append('selected B, released real A completion')
            persist()
            release.set()
        elif phase == 'awaiting_thread_finish' and screen._thread is None:
            check('native event loop settles without binding previous-package result',
                  screen._package == str(b) and screen._last_job_dir == '' and screen._inspector._meta.text() == 'No job loaded',
                  {'package':screen._package,'last_job_dir':screen._last_job_dir,'inspector':screen._inspector._meta.text()})
            check('completion preserves all bytes after actual job persistence', helpers.snapshot(root / 'fixtures') == holder['at_hold'])
            check('no native error dialogs', not receipt['errors'], receipt['errors'])
            receipt['seconds'] = time.monotonic() - started
            receipt['pass'] = True
            receipt['events'].append('native event loop accepted exact completion boundary')
            persist()
            phase = 'done'
            app.exit(0)
        elif phase == 'failed_settling' and screen._thread is None:
            app.exit(1)
        elif time.monotonic() - started > 35 and phase not in ('done', 'failed_settling'):
            raise TimeoutError('Native event-loop control exceeded its bounded completion deadline')
    except BaseException:
        fail()


timer = QTimer()
timer.setInterval(10)
timer.timeout.connect(tick)
timer.start()
QTimer.singleShot(0, start)
persist()
code = app.exec()
capture_analysis.run = real_run
release.set()
screen.close()
receipt['process_return'] = code
persist()
print(json.dumps({'pass':receipt.get('pass'),'checks':len(receipt['checks']),'seconds':receipt.get('seconds'),'code':code}),flush=True)
raise SystemExit(code)
