# SPDX-License-Identifier: GPL-3.0-only
"""Existing-interface baseline: retained job is readable but not offered by Analysis."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
for package in ('capture_analysis', 'capture_session', 'capture_protocol'):
    sys.path.insert(0, str(SOURCE / 'libs/python' / package))
sys.path.insert(0, str(SOURCE / 'desktop'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
for key, suffix in [('LOCALAPPDATA', 'local'), ('APPDATA', 'roaming'), ('XDG_CONFIG_HOME', 'config'),
                    ('XDG_DATA_HOME', 'data'), ('XDG_CACHE_HOME', 'cache'), ('MPLCONFIGDIR', 'mpl')]:
    path = ROOT / 'tmp' / suffix
    path.mkdir(exist_ok=True)
    os.environ[key] = str(path)

from capture_analysis import JobParams, run
from capture_desktop.screen_analysis import AnalysisScreen
from capture_desktop.state import CaptureState
from capture_desktop import theme
from PySide6.QtWidgets import QApplication, QPushButton

package = ROOT / 'evidence/baseline-saved.mmsession'
shutil.copytree(SOURCE / 'tests/fixtures/mini_session', package)
def raw_hashes():
    return {p.relative_to(package).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(package.rglob('*')) if p.is_file() and 'processing' not in p.relative_to(package).parts}
before = raw_hashes()
result = run(package, JobParams(command='qc', overwrite_job_id='retained-qc'))
assert before == raw_hashes()
app = QApplication([])
theme.apply_theme(app, setting='dark')
screen = AnalysisScreen(CaptureState())
screen.set_package(str(package))
screen.resize(1220, 850)
screen.show()
app.processEvents()
assert not screen._last_job_dir
assert screen._inspector._meta.text() == 'No job loaded'
assert not screen._btn_open_job.isEnabled()
assert not hasattr(screen, '_history')
buttons = [b.text() for b in screen.findChildren(QPushButton)]
assert not any('saved' in b.casefold() or 'history' in b.casefold() for b in buttons)
screen.grab().save(str(ROOT/'evidence/baseline-no-history.png'))
# The existing reader already understands the retained job, isolating the UI gap.
screen._inspector.load_job_dir(result.job_dir)
assert 'job_id=retained-qc' in screen._inspector._meta.text()
assert before == raw_hashes()
receipt = {'source_commit':'72c15d6b623e217291a824e4e4808a385df896a9',
           'source_tree':'221cf5c7bb3c3392a7c4186ba0bcf5a8664135d1',
           'python':sys.version,'qt_platform':app.platformName(),
           'actual_job_status':result.status,'retained_job':str(result.job_dir),
           'baseline':'feature absent: reopening a package leaves gallery/inspector unbound',
           'existing_inspector_manual_control':True,'raw_unchanged':True,
           'buttons':buttons,'raw_sha256':before}
(ROOT/'evidence/baseline-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='raw_sha256'},indent=2))
screen.close()
