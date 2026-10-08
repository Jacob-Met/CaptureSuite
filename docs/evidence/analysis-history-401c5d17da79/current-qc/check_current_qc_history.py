# SPDX-License-Identifier: GPL-3.0-only
"""Receive one current QC/2 artifact through the saved native result workflow."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import traceback
from pathlib import Path


def hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output == source or source in output.parents or output.exists():
        raise ValueError('Output must be a new private directory outside the source.')
    manifest = json.loads(args.inputs.read_text())
    expected = {x['path']: x['sha256'] for x in manifest['files']}
    assert hashes(source) == expected, 'Input projection must match all frozen files.'
    output.mkdir(parents=True, exist_ok=False)
    for key, name in [('LOCALAPPDATA', 'local'), ('APPDATA', 'roaming'),
                      ('XDG_CONFIG_HOME', 'config'), ('XDG_DATA_HOME', 'data'),
                      ('XDG_CACHE_HOME', 'cache'), ('MPLCONFIGDIR', 'matplotlib')]:
        folder = output / 'private-state' / name
        folder.mkdir(parents=True)
        os.environ[key] = str(folder)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    for relative in reversed(['desktop', 'libs/python/capture_analysis',
                              'libs/python/capture_session', 'libs/python/capture_protocol',
                              'libs/python/capture_protocol/capture_protocol/generated',
                              'libs/python/capture_worker', 'workers/python_host']):
        sys.path.insert(0, str(source / relative))

    report = {'canonical_main': manifest['canonical_parent'],
              'author_source': manifest['author_source'],
              'composition_tree': manifest['composition_tree'],
              'source_inputs_sha256': hashlib.sha256(args.inputs.read_bytes()).hexdigest(),
              'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'python': sys.version, 'platform': platform.platform(),
              'checks': [], 'scope': 'One current-QC/2 to saved-history reader boundary; no worker-thread, Windows, daemon or hardware acceptance.'}

    def check(name: str, value: bool) -> None:
        report['checks'].append({'name': name, 'passed': bool(value)})
        assert value, name

    status = 1
    try:
        import PySide6
        from PySide6.QtCore import QCoreApplication, QEvent, QTimer
        from PySide6.QtWidgets import QApplication, QPlainTextEdit
        import capture_analysis.qc as qc_module
        import capture_analysis.report_html as html_module
        from capture_analysis import JobParams, run
        from capture_desktop import theme
        from capture_desktop.screen_analysis import AnalysisScreen
        from capture_desktop.state import CaptureState

        report['pyside6'] = PySide6.__version__
        check('current QC producer loaded from pinned source',
              Path(qc_module.__file__).resolve() == source / 'libs/python/capture_analysis/capture_analysis/qc.py')
        check('current HTML producer loaded from pinned source',
              Path(html_module.__file__).resolve() == source / 'libs/python/capture_analysis/capture_analysis/report_html.py')
        package = output / 'current QC saved.mmsession'
        shutil.copytree(source / 'tests/fixtures/mini_session', package)
        gap_dir = package / 'sources/sim.emg.main/health'
        gap_dir.mkdir(parents=True, exist_ok=True)
        (gap_dir / 'gaps.jsonl').write_text(json.dumps({
            'sourceId': 'sim.emg.main', 'streamId': 'sim.emg.main.batch',
            'cause': 'transport_loss', 'startSessionTimeNs': '1000000001',
            'endSessionTimeNs': '2000000003', 'closed': True, 'estimatedLostCount': '3'
        }) + '\n', encoding='utf-8')
        result = run(package, JobParams(command='qc', overwrite_job_id='current-qc'))
        qc_path = result.job_dir / 'reports/qc.json'
        html_path = result.job_dir / 'reports/qc.html'
        qc = json.loads(qc_path.read_text())
        check('current producer emits capture.analysis_qc/2', qc['schemaId'] == 'capture.analysis_qc/2')
        check('native gap precision retained in generated result',
              len(qc['gaps']) == 1 and qc['gaps'][0]['durationNs'] == '1000000002'
              and qc['gaps'][0]['estimatedLostCount'] == '3')
        check('current generated report includes the recorded gap',
              'Recorded gaps' in html_path.read_text() and 'transport_loss' in html_path.read_text())
        before = hashes(package)
        app = QApplication([])
        theme.apply_theme(app, setting='dark')
        screen = AnalysisScreen(CaptureState())
        callback_status = [1]

        def receive() -> None:
            try:
                screen.set_package(str(package))
                check('package selection offers saved result without opening it',
                      screen._history._jobs.count() == 1 and not screen._last_job_dir)
                screen._history._open.click()
                check('explicit native Open selects the current result',
                      screen._last_job_dir == str(result.job_dir)
                      and screen._history.loaded_job_id == 'current-qc')
                check('existing inspector receives current result provenance',
                      'job_id=current-qc' in screen._inspector._meta.text())
                check('existing report action is available for the retained current report',
                      screen._btn_open_report.isEnabled())
                screen._history._details.click()
                dialog = screen._history._dialog
                check('native result details dialog opens', dialog is not None and dialog.isVisible())
                editors = {w.objectName(): w for w in dialog.findChildren(QPlainTextEdit)}
                check('saved parameters and provenance remain read-only',
                      all(w.isReadOnly() for w in editors.values())
                      and json.loads(editors['analysisHistoryParameters'].toPlainText())['command'] == 'qc'
                      and json.loads(editors['analysisHistoryManifest'].toPlainText())['jobId'] == 'current-qc')
                check('browsing starts no computation thread', screen._thread is None)
                check('all generated package and job bytes stay unchanged while browsing', hashes(package) == before)
                dialog.close()
                callback_status[0] = 0
            except BaseException:
                report['error'] = traceback.format_exc()
            finally:
                screen.close()
                app.exit(callback_status[0])

        QTimer.singleShot(0, receive)
        loop_status = app.exec()
        check('actual QApplication event loop returned successfully', loop_status == 0)
        screen.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        report['package_hashes'] = before
        report['artifact_schema'] = qc['schemaId']
        report['artifact_gap'] = qc['gaps'][0]
        status = callback_status[0]
    except BaseException:
        report.setdefault('error', traceback.format_exc())
    finally:
        report['source_unchanged'] = hashes(source) == expected
        if not report['source_unchanged']:
            status = 1
        report['exit_code'] = status
        report['passed'] = sum(x['passed'] for x in report['checks'])
        report['failed'] = sum(not x['passed'] for x in report['checks'])
        (output / 'receipt.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k: report[k] for k in ['passed', 'failed', 'exit_code', 'source_unchanged']}))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
