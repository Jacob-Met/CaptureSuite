# SPDX-License-Identifier: GPL-3.0-only
"""Read-only native visual check of the frozen saved-job details window."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path('/dev/shm/capturesuite-history-401c5d17da79')
SOURCE = ROOT / 'source'
PACKAGE = Path('/dev/shm/hamon-401c5d17da79-capture-history-pr/current-boundary/current-run/current QC saved.mmsession')
os.environ.update(QT_QPA_PLATFORM='offscreen', PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode = True
sys.path[:0] = [str(SOURCE / part) for part in (
    'desktop', 'libs/python/capture_analysis', 'libs/python/capture_session',
    'libs/python/capture_protocol')]

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QTabWidget
from capture_desktop import theme
from capture_desktop.screen_analysis import AnalysisScreen
from capture_desktop.state import CaptureState


def hashes():
    return {str(path.relative_to(PACKAGE)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in PACKAGE.rglob('*') if path.is_file()}


before = hashes()
app = QApplication([])
theme.apply_theme(app, setting='dark')
screen = AnalysisScreen(CaptureState())
screen.resize(1220, 900)
receipt = {'source_commit': '37443f0d4d5ffa684b5423d58501856cadbe0655',
           'saved_fixture_author': 'independent current-main QC/2 receiver',
           'package': str(PACKAGE), 'qt_platform': app.platformName(), 'screens': {}}


def finish():
    try:
        dialog = screen._history._dialog
        image = ROOT / 'evidence/details-log.png'
        assert dialog.grab().save(str(image))
        receipt['screens'][image.name] = hashlib.sha256(image.read_bytes()).hexdigest()
        receipt['saved_bytes_unchanged'] = hashes() == before
        receipt['no_worker_started'] = screen._thread is None
        assert receipt['saved_bytes_unchanged'] and receipt['no_worker_started']
        receipt['result'] = 'Native details visually captured; read-only boundaries passed.'
    except BaseException:
        receipt['failure'] = traceback.format_exc()
    finally:
        (ROOT / 'evidence/details-visual-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if screen._history._dialog is not None:
            screen._history._dialog.close()
        screen.close()
        app.quit()


def capture():
    try:
        dialog = screen._history._dialog
        assert dialog is not None and dialog.isVisible()
        params = dialog.findChild(QPlainTextEdit, 'analysisHistoryParameters')
        assert params.isReadOnly() and json.loads(params.toPlainText())['command'] == 'qc'
        image = ROOT / 'evidence/details-parameters.png'
        assert dialog.grab().save(str(image))
        receipt['screens'][image.name] = hashlib.sha256(image.read_bytes()).hexdigest()
        dialog.findChild(QTabWidget).setCurrentIndex(1)
        QTimer.singleShot(20, finish)
    except BaseException:
        receipt['failure'] = traceback.format_exc()
        finish()


def start():
    try:
        screen.set_package(str(PACKAGE))
        combo = screen._history._jobs
        index = next(i for i in range(combo.count()) if combo.itemData(i).job_id == 'current-qc')
        combo.setCurrentIndex(index)
        screen.show()
        screen._history._open.click()
        screen._history._details.click()
        QTimer.singleShot(30, capture)
    except BaseException:
        receipt['failure'] = traceback.format_exc()
        finish()


QTimer.singleShot(0, start)
app.exec()
print(json.dumps(receipt, indent=2))
raise SystemExit(1 if 'failure' in receipt else 0)
