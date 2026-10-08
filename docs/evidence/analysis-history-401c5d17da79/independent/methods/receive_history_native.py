# SPDX-License-Identifier: GPL-3.0-only
"""Complete independent receiving in the real QApplication event loop.

Actions advance from QTimer callbacks; no manual processEvents/qWait pumping,
no retained worker/thread references, no production source or worker edits.
"""
from __future__ import annotations
import dataclasses
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path('/dev/shm/hamon-401c5d17da79-capturesuite-receiving')
FIXTURES = ROOT / 'fixtures-native'
spec = importlib.util.spec_from_file_location('receiving_helpers', ROOT / 'methods/receive_history.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
helpers.bootstrap(helpers.DEFAULT_SOURCE)
from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QMessageBox, QPushButton
from capture_desktop.state import CaptureState
import capture_analysis

Screen = helpers.load_screen('candidate', helpers.DEFAULT_SOURCE)
app = QApplication([])
screen = Screen(CaptureState())
screen.resize(1200, 900)
screen.show()
a, b = (FIXTURES / f'package-{letter}.mmsession' for letter in ('a','b'))
job_a, job_b = (p / 'processing/jobs/retained-prior' for p in (a,b))
release, ready = threading.Event(), threading.Event()
holder = {}
real_run = capture_analysis.run
started = time.monotonic()
settling_failure = False
before = helpers.snapshot(FIXTURES)
raw_before = {key:value for key,value in before.items() if '/processing/' not in key}
receipt = {'schema':'capturesuite.history.independent-native-receiving.v1',
           'candidate':json.loads((ROOT / 'pins/candidate-inputs.json').read_text()),
           'runtime':{'python':sys.version,'pyside6':pyside_version,'qt_platform':app.platformName()},
           'loop':'QApplication.exec; state-machine actions via QTimer; no manual processEvents, QTest.qWait, source edits, worker replacement, or retained worker/thread reference',
           'method_sha256':helpers.digest(Path(__file__)), 'helper_sha256':helpers.digest(ROOT / 'methods/receive_history.py'),
           'fixture_root':str(FIXTURES),'checks':[],'screens':{},'errors':[], 'source_imports':{}}
for module in (capture_analysis, sys.modules['capture_analysis.jobs'],sys.modules['capture_desktop.screen_analysis'],sys.modules['capture_desktop.widgets_analysis_plots']):
    receipt['source_imports'][module.__name__] = {'path':module.__file__,'sha256':helpers.digest(Path(module.__file__))}


def persist():
    helpers.save_json(ROOT / 'evidence/native-candidate-receipt.json', receipt)


def check(name, condition, evidence=None):
    receipt['checks'].append({'name':name,'pass':bool(condition),'evidence':evidence})
    persist()
    print(name, bool(condition), flush=True)
    if not condition:
        raise AssertionError(name)


def view():
    tabs = screen._gallery._tabs
    png_count = 0
    for index in range(1,tabs.count()):
        for label in tabs.widget(index).findChildren(QLabel):
            pixmap = label.pixmap()
            if pixmap is not None and not pixmap.isNull(): png_count += 1
    return {'package':screen._package,'last_job_dir':screen._last_job_dir,
            'inspector':screen._inspector._meta.text(),
            'tabs':[tabs.tabText(i) for i in range(tabs.count())],
            'png_count':png_count,'linked_plot_count':len(screen._gallery._sync._linked),
            'sync_title':screen._gallery._sync._title.text(),
            'history_loaded_job_id':screen._history.loaded_job_id,
            'open_folder_enabled':screen._btn_open_job.isEnabled(),
            'open_report_enabled':screen._btn_open_report.isEnabled()}


def select(job_id):
    combo = screen.findChild(QComboBox,'analysisHistoryJob')
    matches = [i for i in range(combo.count()) if getattr(combo.itemData(i),'job_id',None) == job_id]
    assert len(matches) == 1, (job_id,matches)
    combo.setCurrentIndex(matches[0])
    return screen.findChild(QPushButton,'analysisHistoryOpen')


def open_saved(job_id):
    button = select(job_id)
    assert button.isEnabled(), job_id
    button.click()


def capture(name):
    path = ROOT / 'evidence' / name
    assert screen.grab().save(str(path))
    return {'path':str(path),'sha256':helpers.digest(path)}


def held_actual_run(package, params, **kwargs):
    try:
        actual = real_run(package,dataclasses.replace(params,overwrite_job_id='late-native-candidate-qc'),**kwargs)
        holder['result'] = actual
        ready.set()
        if not release.wait(30): raise TimeoutError('Receiving gate was not released')
        return actual
    except BaseException as exc:
        holder['error'] = repr(exc)
        ready.set()
        raise


def flow():
    screen.set_package(str(a)); yield
    open_saved('retained-prior'); yield
    current = view()
    check('fresh screen reopens real prior A result into native gallery and inspector',
          current['last_job_dir']==str(job_a) and str(job_a) in current['inspector']
          and current['png_count']==2 and current['linked_plot_count']==2
          and 'receiving-a-401c5d17da79' in current['sync_title'],current)
    receipt['screens']['reopened_a']=capture('native-reopened-a.png')
    screen.set_package(str(b)); yield
    current = view()
    check('package switch clears prior result and both launch targets',
          current['last_job_dir']=='' and current['inspector']=='No job loaded'
          and current['png_count']==0 and current['linked_plot_count']==0
          and not current['open_folder_enabled'] and not current['open_report_enabled'],current)
    open_saved('retained-prior'); yield
    loaded_b = view()
    check('same basename in B resolves B figures and metadata only',
          loaded_b['last_job_dir']==str(job_b) and str(job_b) in loaded_b['inspector']
          and loaded_b['png_count']==2 and loaded_b['linked_plot_count']==2
          and 'receiving-b-401c5d17da79' in loaded_b['sync_title'],loaded_b)
    receipt['screens']['reopened_b']=capture('native-reopened-b.png')
    before_refusals=helpers.snapshot(FIXTURES)
    for bad_id in ('malformed-manifest','missing-manifest','foreign-session','foreign-directory'):
        button=select(bad_id); yield
        disabled=not button.isEnabled()
        button.click(); yield
        check(f'{bad_id} is visibly unavailable and refuses Open without replacing B',
              disabled and view()==loaded_b,
              {'status':screen._history._status.text(),'view':view()})
    check('unavailable-row actions leave every saved byte unchanged',helpers.snapshot(FIXTURES)==before_refusals)
    button=select('selected-before-missing'); yield
    assert button.isEnabled()
    manifest=b/'processing/jobs/selected-before-missing/job_manifest.json'
    held=manifest.with_name('job_manifest.receiver-held.json')
    assert not held.exists()
    manifest.rename(held)
    at_missing=helpers.snapshot(FIXTURES)
    button.click(); yield
    check('Open revalidates a cached row after its manifest disappears',
          view()==loaded_b and 'Could not open' in screen._history._status.text(),screen._history._status.text())
    check('refused cached Open preserves all bytes after the controlled rename',helpers.snapshot(FIXTURES)==at_missing)
    screen.set_package(str(a)); yield
    screen._command.setCurrentIndex(screen._command.findData('qc'))
    assert not (a/'processing/jobs/late-native-candidate-qc').exists()
    capture_analysis.run=held_actual_run
    screen._btn_run.click()
    while not ready.is_set(): yield
    assert 'error' not in holder,holder.get('error')
    actual=holder['result']
    check('real QThread QC completed and persisted before receiving release',
          actual.status in ('completed','completed_with_warnings') and (actual.job_dir/'job_manifest.json').is_file(),
          {'job_dir':str(actual.job_dir),'status':actual.status})
    at_hold=helpers.snapshot(FIXTURES)
    screen.set_package(str(b)); yield
    receipt['screens']['before_late_delivery']=view()
    release.set()
    while screen._thread is not None: yield
    current=view()
    check('prior-package real completion cannot bind current B gallery or inspector',
          current['package']==str(b) and current['last_job_dir']==''
          and current['inspector']=='No job loaded' and current['png_count']==0
          and current['linked_plot_count']==0 and not current['open_folder_enabled'],current)
    check('prior-package result is explicitly retained for later inspection',
          'Result saved for the previous package' in screen._log.toPlainText(),screen._log.toPlainText())
    open_saved('retained-prior'); yield
    check('current B saved result reopens after actual Qt thread completion',view()['last_job_dir']==str(job_b),view())
    screen.set_package(str(a)); yield
    open_saved(actual.job_id); yield
    check('returning to A explicitly opens the genuinely completed late QC',
          view()['last_job_dir']==str(actual.job_dir) and str(actual.job_dir) in view()['inspector'],view())
    check('late delivery and later reopenings perform no persisted writes',helpers.snapshot(FIXTURES)==at_hold)
    raw_after={key:value for key,value in helpers.snapshot(FIXTURES).items() if '/processing/' not in key}
    check('all captured raw data remains unchanged',raw_before==raw_after)
    check('no Qt error dialog or native worker failure',not receipt['errors'],receipt['errors'])
    for rel,pin in receipt['candidate']['inputs'].items():
        assert helpers.digest(helpers.DEFAULT_SOURCE/rel)==pin['sha256'],rel+' changed during receiving'
    check('frozen source bytes remained exact throughout native receiving',True)
    receipt['screens']['late_qc']=capture('native-late-qc.png')
    receipt['fixture_files_after']=helpers.snapshot(FIXTURES)
    receipt['source_unchanged']=True
    receipt['seconds']=time.monotonic()-started
    receipt['pass']=True
    receipt['result']='All independent native QApplication receiving checks passed on exact corrected candidate'
    persist()


iterator=flow()

def advance():
    global settling_failure
    try:
        for widget in app.topLevelWidgets():
            if isinstance(widget,QMessageBox) and widget.isVisible():
                receipt['errors'].append(widget.text());widget.accept()
        if settling_failure:
            if screen._thread is None:app.exit(1)
            return
        if time.monotonic()-started>35:raise TimeoutError('Native receiving exceeded its bounded deadline')
        next(iterator)
    except StopIteration:
        app.exit(0)
    except BaseException:
        receipt['errors'].append(traceback.format_exc())
        receipt['pass']=False
        receipt['result']='Independent native receiving failed'
        release.set()
        settling_failure=True
        persist()
        if screen._thread is None:app.exit(1)


timer=QTimer()
timer.setInterval(10)
timer.timeout.connect(advance)
timer.start()
persist()
code=app.exec()
release.set()
capture_analysis.run=real_run
screen.close()
receipt['process_return']=code
persist()
print(json.dumps({'pass':receipt.get('pass'),'checks':len(receipt['checks']),'seconds':receipt.get('seconds'),'code':code}),flush=True)
raise SystemExit(code)
