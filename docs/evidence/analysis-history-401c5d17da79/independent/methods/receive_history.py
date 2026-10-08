# SPDX-License-Identifier: GPL-3.0-only
"""Independent real Qt receiving of saved-job/package lifetime boundaries.

Uses the project's genuine analysis pipeline. Only return delivery is delayed for
one actual QThread QC result; the analysis algorithm and worker are unmodified.
All writable fixtures are confined to this receiver's unique RAM directory.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import traceback

ROOT = Path('/dev/shm/hamon-401c5d17da79-capturesuite-receiving')
DEFAULT_SOURCE = Path('/dev/shm/capturesuite-history-401c5d17da79/source')
BASE_COMMIT = '72c15d6b623e217291a824e4e4808a385df896a9'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(path: Path) -> dict:
    result = {}
    for item in sorted(path.rglob('*')):
        if item.is_symlink():
            result[str(item.relative_to(path))] = {'symlink': os.readlink(item)}
        elif item.is_file():
            result[str(item.relative_to(path))] = {'bytes': item.stat().st_size, 'sha256': digest(item)}
    return result


def save_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')


def bootstrap(source: Path) -> None:
    for part in ('tmp', 'mpl', 'evidence', 'pins'):
        (ROOT / part).mkdir(parents=True, exist_ok=True)
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['TMPDIR'] = str(ROOT / 'tmp')
    os.environ['MPLCONFIGDIR'] = str(ROOT / 'mpl')
    os.environ['MPLBACKEND'] = 'Agg'
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / rel) for rel in (
        'desktop', 'libs/python/capture_analysis', 'libs/python/capture_session',
        'libs/python/capture_protocol')]
    import capture_analysis, capture_session, capture_protocol, capture_desktop
    for module in (capture_analysis, capture_session, capture_protocol, capture_desktop):
        if not Path(module.__file__).resolve().is_relative_to(source):
            raise AssertionError(f'Editable dependency escaped source: {module.__file__}')


def make_package(source: Path, dest: Path, session: str, amplitude: float) -> Path:
    """The existing phase-B native fixture shape, without deleting placeholders."""
    import numpy as np
    from mcap.writer import Writer
    from capture_protocol.generated.capture.v1.data import emg_batch_pb2, imu_frame_pb2
    if dest.exists():
        raise RuntimeError(f'Refusing to replace existing fixture {dest}')
    shutil.copytree(source / 'tests/fixtures/mini_session', dest,
                    ignore=shutil.ignore_patterns('*.mcap', 'processing', '__pycache__'))
    manifest_path = dest / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['sessionId'] = session
    save_json(manifest_path, manifest)
    samples = (amplitude * np.sin(2 * np.pi * 40.0 * np.arange(400) / 2000.0)).astype(np.float32)
    emg = emg_batch_pb2.EmgBatch()
    emg.timing.session_time_ns = 0
    emg.timing.sequence_number = 1
    emg.first_sample_index = 0
    emg.sample_count = 400
    emg.channel_ids.extend(['ch0', 'ch1'])
    emg.samples_f32_le = np.stack([samples, samples * 0.5]).astype('<f4').tobytes()
    emg_path = dest / 'sources/sim.emg.main/streams/sim.emg.main.batch/segments/000000.mcap'
    with emg_path.open('wb') as fh:
        writer = Writer(fh)
        writer.start(profile='', library='CaptureSuite independent history receiver')
        sid = writer.register_schema(name='emg.batch/1', encoding='protobuf', data=b'')
        cid = writer.register_channel(topic='emg', message_encoding='protobuf', schema_id=sid)
        writer.add_message(channel_id=cid, log_time=0, data=emg.SerializeToString(), publish_time=0)
        writer.finish()
    stream_path = emg_path.parents[1] / 'stream.json'
    stream = json.loads(stream_path.read_text())
    stream['dimensions'] = [2]
    save_json(stream_path, stream)
    imu_path = dest / 'sources/sim.imu.upper/streams/sim.imu.upper.frames/segments/000000.mcap'
    with imu_path.open('wb') as fh:
        writer = Writer(fh)
        writer.start(profile='', library='CaptureSuite independent history receiver')
        sid = writer.register_schema(name='imu.frame/1', encoding='protobuf', data=b'')
        cid = writer.register_channel(topic='imu', message_encoding='protobuf', schema_id=sid)
        for index in range(30):
            frame = imu_frame_pb2.ImuFrame()
            frame.timing.session_time_ns = int(index * 1e9 / 60.0)
            frame.timing.sequence_number = index
            frame.frame_index = index
            sensor = frame.sensors.add()
            sensor.sensor_id = 'pelvis'
            sensor.accel_z = 9.81
            sensor.qw = 1.0
            writer.add_message(channel_id=cid, log_time=frame.timing.session_time_ns,
                               data=frame.SerializeToString(), publish_time=frame.timing.session_time_ns)
        writer.finish()
    integrity_path = dest / 'integrity.json'
    integrity = json.loads(integrity_path.read_text())
    integrity['files'][0]['endSessionTimeNs'] = 500_000_000
    save_json(integrity_path, integrity)
    return dest


def prepare(source: Path) -> None:
    from capture_analysis import JobParams, run
    fixture_root = ROOT / 'fixtures'
    if fixture_root.exists():
        raise RuntimeError('Receiving fixtures already exist; use the saved receipt, do not regenerate.')
    if shutil.disk_usage(ROOT).free < 2_000_000:
        raise RuntimeError('Less than the bounded 2 MB fixture budget is available.')
    fixture_root.mkdir()
    result_doc = {'source_commit': BASE_COMMIT, 'fixtures': {}, 'method':
                  'Real protobuf EMG/IMU MCAP, synchronous native all jobs, same job basename in distinct sessions.'}
    for letter, amplitude in (('a', 1.5), ('b', 0.75)):
        package = make_package(source, fixture_root / f'package-{letter}.mmsession',
                               f'receiving-{letter}-401c5d17da79', amplitude)
        raw_before = snapshot(package)
        result = run(package, JobParams(command='all', overwrite_job_id='retained-prior'))
        assert result.status in ('completed', 'completed_with_warnings'), result.status
        raw_after = {key: value for key, value in snapshot(package).items() if not key.startswith('processing/')}
        assert raw_before == raw_after
        figures = sorted((result.job_dir / 'figures').glob('*.png'))
        assert len(figures) >= 2, 'Need genuine images beyond the linked Sync view'
        series = json.loads((result.job_dir / 'figures/sync_dashboard_series.json').read_text())
        assert series.get('series'), 'Need genuine linked plot data'
        result_doc['fixtures'][letter] = {
            'package': str(package), 'job_dir': str(result.job_dir), 'job_id': result.job_id,
            'status': result.status, 'session_id': f'receiving-{letter}-401c5d17da79',
            'figures': [p.name for p in figures], 'sync_series_count': len(series['series']),
            'raw_unchanged_by_analysis': True, 'files': snapshot(package),
        }
        print(f'Prepared real {letter} result: {len(figures)} PNGs, {len(series["series"])} linked series', flush=True)
    # These intentionally unavailable rows are admitted only to our private fixture.
    b = fixture_root / 'package-b.mmsession/processing/jobs'
    (b / 'malformed-manifest').mkdir()
    (b / 'malformed-manifest/job_manifest.json').write_text('{not JSON')
    (b / 'missing-manifest').mkdir()
    (b / 'missing-manifest/params.json').write_text('{}\n')
    (b / 'foreign-session').mkdir()
    foreign = json.loads((fixture_root / 'package-a.mmsession/processing/jobs/retained-prior/job_manifest.json').read_text())
    foreign['jobId'] = 'foreign-session'
    save_json(b / 'foreign-session/job_manifest.json', foreign)
    (b / 'foreign-directory').symlink_to(fixture_root / 'package-a.mmsession/processing/jobs/retained-prior', target_is_directory=True)
    # A valid real QC result lets the UI hold a catalog row before its manifest is moved.
    result = run(b.parents[1], JobParams(command='qc', overwrite_job_id='selected-before-missing'))
    assert result.status in ('completed', 'completed_with_warnings')
    result_doc['selected_before_missing'] = str(result.job_dir)
    result_doc['fixture_files'] = snapshot(fixture_root)
    result_doc['total_bytes'] = sum(row.get('bytes', 0) for row in result_doc['fixture_files'].values())
    result_doc['free_bytes_after'] = shutil.disk_usage(ROOT).free
    save_json(ROOT / 'evidence/fixtures.json', result_doc)
    print(json.dumps({key: result_doc[key] for key in ('total_bytes', 'free_bytes_after')}, sort_keys=True))


def load_screen(mode: str, source: Path):
    if mode == 'baseline':
        name = 'capture_desktop.screen_analysis'
        spec = importlib.util.spec_from_file_location(name, ROOT / 'pins/baseline-screen_analysis.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module.AnalysisScreen
    pins = json.loads((ROOT / 'pins/candidate-inputs.json').read_text())
    for rel, record in pins['inputs'].items():
        assert digest(source / rel) == record['sha256'], f'Candidate bytes changed: {rel}'
    return importlib.import_module('capture_desktop.screen_analysis').AnalysisScreen


def receive(mode: str, source: Path) -> int:
    from PySide6 import __version__ as qt_version
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QMessageBox, QPushButton
    import capture_analysis
    from capture_desktop.state import CaptureState
    Screen = load_screen(mode, source)
    app = QApplication.instance() or QApplication([])
    a = ROOT / 'fixtures/package-a.mmsession'
    b = ROOT / 'fixtures/package-b.mmsession'
    job_a, job_b = (p / 'processing/jobs/retained-prior' for p in (a, b))
    receipt = {'mode': mode, 'source_commit': BASE_COMMIT, 'python': sys.version,
               'pyside6': qt_version, 'qt_platform': app.platformName(), 'checks': [],
               'screens': {}, 'dialog_errors': [], 'source_imports': {}}
    for name in ('capture_analysis', 'capture_analysis.jobs', 'capture_desktop.screen_analysis',
                 'capture_desktop.widgets_analysis_plots', 'capture_desktop.state'):
        module = importlib.import_module(name)
        receipt['source_imports'][name] = {'path': module.__file__, 'sha256': digest(Path(module.__file__))}
    if mode == 'candidate':
        receipt['candidate_inputs'] = json.loads((ROOT / 'pins/candidate-inputs.json').read_text())
    fixture_before = snapshot(ROOT / 'fixtures')
    raw_before = {key: val for key, val in fixture_before.items() if '/processing/' not in key}
    release, ready = threading.Event(), threading.Event()
    holder = {}
    real_run = capture_analysis.run
    screen = Screen(CaptureState())
    screen.resize(1200, 900)
    screen.show()

    def pump() -> None:
        app.processEvents()
        for widget in app.topLevelWidgets():
            if isinstance(widget, QMessageBox) and widget.isVisible():
                receipt['dialog_errors'].append(widget.text())
                widget.accept()
        QTest.qWait(5)

    def until(predicate, message: str, seconds: float = 25.0) -> None:
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() > deadline:
                raise AssertionError(message)
            pump()
        pump()

    def state() -> dict:
        tabs = screen._gallery._tabs
        png_count = 0
        for i in range(1, tabs.count()):
            for label in tabs.widget(i).findChildren(QLabel):
                image = label.pixmap()
                if image is not None and not image.isNull():
                    png_count += 1
        return {'package': screen._package, 'last_job_dir': screen._last_job_dir,
                'inspector': screen._inspector._meta.text(),
                'tabs': [tabs.tabText(i) for i in range(tabs.count())],
                'png_count': png_count, 'sync_title': screen._gallery._sync._title.text(),
                'linked_plot_count': len(screen._gallery._sync._linked),
                'history_loaded_job_id': screen._history.loaded_job_id if hasattr(screen, '_history') else None,
                'open_folder_enabled': screen._btn_open_job.isEnabled(),
                'open_report_enabled': screen._btn_open_report.isEnabled()}

    def check(name: str, condition: bool, evidence=None) -> None:
        receipt['checks'].append({'name': name, 'pass': bool(condition), 'evidence': evidence})
        print(f'{mode}: {name}: {bool(condition)}', flush=True)
        if not condition:
            raise AssertionError(name)

    def open_history(job_id: str) -> None:
        combo = screen.findChild(QComboBox, 'analysisHistoryJob')
        button = screen.findChild(QPushButton, 'analysisHistoryOpen')
        assert combo is not None and button is not None
        matches = [i for i in range(combo.count()) if getattr(combo.itemData(i), 'job_id', None) == job_id]
        assert len(matches) == 1, (job_id, matches)
        combo.setCurrentIndex(matches[0])
        pump()
        assert button.isEnabled(), f'Cannot open {job_id}'
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        pump()

    try:
        screen.set_package(str(a))
        pump()
        if mode == 'candidate':
            open_history('retained-prior')
            loaded_a = state()
            check('fresh screen reopens real prior A result into gallery and inspector',
                  loaded_a['last_job_dir'] == str(job_a) and str(job_a) in loaded_a['inspector']
                  and loaded_a['png_count'] >= 1 and loaded_a['linked_plot_count'] >= 1
                  and 'receiving-a-401c5d17da79' in loaded_a['sync_title'], loaded_a)
        else:
            # Baseline already lacks history. Bind the existing renderer directly as
            # the established control, then challenge only package/lifetime behavior.
            screen._gallery.load_job_dir(job_a)
            screen._inspector.load_job_dir(job_a)
            screen._last_job_dir = str(job_a)
            pump()
        receipt['screens']['initial_a'] = state()
        if mode == 'candidate':
            visual_path = ROOT / 'evidence/candidate-reopened-a.png'
            assert screen.grab().save(str(visual_path))
            receipt['screens']['initial_a_screenshot'] = {'path': str(visual_path), 'sha256': digest(visual_path)}
        screen.set_package(str(b))
        pump()
        switched = state()
        receipt['screens']['after_package_switch'] = switched
        cleared = switched['last_job_dir'] == '' and switched['inspector'] == 'No job loaded' and switched['png_count'] == 0 and switched['linked_plot_count'] == 0
        if mode == 'candidate':
            check('package switch clears prior package result and launch targets',
                  cleared and not switched['open_folder_enabled'] and not switched['open_report_enabled'], switched)
            open_history('retained-prior')
            loaded_b = state()
            check('same basename in package B resolves only B saved figures and metadata',
                  loaded_b['last_job_dir'] == str(job_b) and str(job_b) in loaded_b['inspector']
                  and loaded_b['png_count'] >= 1 and loaded_b['linked_plot_count'] >= 1
                  and 'receiving-b-401c5d17da79' in loaded_b['sync_title'], loaded_b)
            visual_path = ROOT / 'evidence/candidate-reopened-b.png'
            assert screen.grab().save(str(visual_path))
            receipt['screens']['reopened_b_screenshot'] = {'path': str(visual_path), 'sha256': digest(visual_path)}
            before_refusals = snapshot(ROOT / 'fixtures')
            combo = screen.findChild(QComboBox, 'analysisHistoryJob')
            button = screen.findChild(QPushButton, 'analysisHistoryOpen')
            for bad_id in ('malformed-manifest', 'missing-manifest', 'foreign-session', 'foreign-directory'):
                matches = [i for i in range(combo.count()) if getattr(combo.itemData(i), 'job_id', None) == bad_id]
                check(f'{bad_id} is visibly unavailable', len(matches) == 1, matches)
                combo.setCurrentIndex(matches[0]); pump()
                disabled = not button.isEnabled()
                QTest.mouseClick(button, Qt.MouseButton.LeftButton); pump()
                check(f'{bad_id} refuses opening without replacing valid B view', disabled and state() == loaded_b,
                      {'status': screen._history._status.text(), 'view': state()})
            check('unavailable-row inspection leaves all saved bytes unchanged', snapshot(ROOT / 'fixtures') == before_refusals)
            # Deliberate private fixture rename simulates a disappearing manifest
            # after catalog selection. Keep the exact bytes, never delete them.
            missing_id = 'selected-before-missing'
            selected = [i for i in range(combo.count()) if getattr(combo.itemData(i), 'job_id', None) == missing_id]
            assert len(selected) == 1
            combo.setCurrentIndex(selected[0]); pump()
            assert button.isEnabled()
            manifest = b / 'processing/jobs' / missing_id / 'job_manifest.json'
            held = manifest.with_name('job_manifest.receiver-held.json')
            assert not held.exists()
            manifest.rename(held)
            mutated_fixture = snapshot(ROOT / 'fixtures')
            QTest.mouseClick(button, Qt.MouseButton.LeftButton); pump()
            check('Open revalidates cached row when manifest disappears',
                  state() == loaded_b and 'Could not open' in screen._history._status.text(),
                  screen._history._status.text())
            check('failed Open preserves every persisted byte after controlled fixture rename', snapshot(ROOT / 'fixtures') == mutated_fixture)
        else:
            check('baseline reproduces stale A view after switching to B', not cleared and str(job_a) in switched['inspector'], switched)

        screen.set_package(str(a)); pump()
        qc_index = screen._command.findData('qc')
        assert qc_index >= 0
        screen._command.setCurrentIndex(qc_index)
        late_id = f'late-{mode}-actual-qc'
        assert not (a / 'processing/jobs' / late_id).exists()

        def held_real_run(package, params, **kwargs):
            try:
                actual_params = dataclasses.replace(params, overwrite_job_id=late_id)
                result = real_run(package, actual_params, **kwargs)
                holder['result'] = result
                ready.set()
                if not release.wait(30):
                    raise TimeoutError('Receiving completion gate not released')
                return result
            except BaseException as exc:
                holder['error'] = repr(exc)
                ready.set()
                raise

        capture_analysis.run = held_real_run
        screen._btn_run.click()
        until(ready.is_set, 'Actual native QC never reached completion hold')
        assert 'error' not in holder, holder.get('error')
        actual = holder['result']
        check('actual QThread QC result exists before deferred delivery',
              actual.status in ('completed', 'completed_with_warnings') and (actual.job_dir / 'job_manifest.json').is_file(),
              {'job_dir': str(actual.job_dir), 'status': actual.status})
        persisted_at_hold = snapshot(ROOT / 'fixtures')
        screen.set_package(str(b)); pump()
        receipt['screens']['late_before_delivery'] = state()
        release.set()
        until(lambda: screen._thread is None, 'Native worker completion did not finish its Qt lifecycle')
        late_state = state()
        receipt['screens']['late_after_delivery'] = late_state
        if mode == 'candidate':
            check('prior-package real completion cannot bind current B gallery or inspector',
                  late_state['package'] == str(b) and late_state['last_job_dir'] == ''
                  and late_state['inspector'] == 'No job loaded' and late_state['png_count'] == 0
                  and late_state['linked_plot_count'] == 0 and not late_state['open_folder_enabled'], late_state)
            check('late result remains discoverable by explicit package selection',
                  'Result saved for the previous package' in screen._log.toPlainText(), screen._log.toPlainText())
            open_history('retained-prior')
            check('current B result reopens after native thread completion', state()['last_job_dir'] == str(job_b), state())
            screen.set_package(str(a)); pump()
            open_history(late_id)
            check('returning to A explicitly opens its genuine late saved QC',
                  state()['last_job_dir'] == str(actual.job_dir) and str(actual.job_dir) in state()['inspector'], state())
        else:
            check('baseline reproduces foreign binding after late real completion',
                  late_state['package'] == str(b) and late_state['last_job_dir'] == str(actual.job_dir)
                  and str(actual.job_dir) in late_state['inspector'], late_state)
        check('delivery and reopening perform no persisted writes', snapshot(ROOT / 'fixtures') == persisted_at_hold)
        raw_after = {key: val for key, val in snapshot(ROOT / 'fixtures').items() if '/processing/' not in key}
        check('all captured raw package bytes remain unchanged', raw_after == raw_before)
        check('no Qt error dialogs or worker failures occurred', not receipt['dialog_errors'], receipt['dialog_errors'])
        screenshot = ROOT / 'evidence' / f'{mode}-qt.png'
        assert screen.grab().save(str(screenshot))
        receipt['screenshot'] = {'path': str(screenshot), 'sha256': digest(screenshot)}
        receipt['result'] = 'expected baseline defects reproduced' if mode == 'baseline' else 'candidate independent receiving passed'
        code = 0
    except BaseException:
        receipt['result'] = 'receiving failure'
        receipt['traceback'] = traceback.format_exc()
        print(receipt['traceback'], flush=True)
        code = 1
    finally:
        release.set()
        capture_analysis.run = real_run
        if screen._thread is not None:
            try:
                until(lambda: screen._thread is None, 'Worker did not settle during receiving close', 10)
            except BaseException:
                receipt['close_error'] = traceback.format_exc()
        receipt['harness_sha256'] = digest(Path(__file__))
        receipt['free_bytes_after'] = shutil.disk_usage(ROOT).free
        save_json(ROOT / 'evidence' / f'{mode}-receipt.json', receipt)
        screen.close()
        app.processEvents()
    print(json.dumps({'mode': mode, 'result': receipt['result'], 'checks': len(receipt['checks']), 'free_bytes': receipt['free_bytes_after']}), flush=True)
    return code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'baseline', 'candidate'))
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    bootstrap(args.source.resolve())
    if args.mode == 'prepare':
        prepare(args.source.resolve())
        return 0
    return receive(args.mode, args.source.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
