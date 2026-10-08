# SPDX-License-Identifier: GPL-3.0-only
"""Observe current numeric artifacts through history and the unchanged gallery."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import traceback


def hashes(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    assert not out.exists() and source not in out.parents and out!=source
    manifest=json.loads(args.inputs.read_text());expected={r['path']:r['sha256'] for r in manifest['files']}
    assert hashes(source)==expected
    out.mkdir(parents=True,exist_ok=False)
    for key,leaf in [('LOCALAPPDATA','local'),('APPDATA','roaming'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('MPLCONFIGDIR','mpl')]:
        p=out/'state'/leaf;p.mkdir(parents=True);os.environ[key]=str(p)
    os.environ['QT_QPA_PLATFORM']='offscreen';sys.dont_write_bytecode=True
    for rel in reversed(['desktop','libs/python/capture_analysis','libs/python/capture_session','libs/python/capture_protocol','libs/python/capture_protocol/capture_protocol/generated','libs/python/capture_worker']):
        sys.path.insert(0,str(source/rel))
    report={'canonical_main':manifest['canonical_parent'],'author_source':manifest['author_source'],'runtime_tree':manifest['composition_tree'],'checks':[],'errors':[],'method_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_inputs_sha256':hashlib.sha256(args.inputs.read_bytes()).hexdigest()}
    def check(name,value):report['checks'].append({'name':name,'passed':bool(value)})
    status=1
    try:
        import PySide6
        from PySide6.QtCore import QTimer,QCoreApplication,QEvent
        from PySide6.QtWidgets import QApplication
        from capture_analysis import run,JobParams
        from capture_desktop import theme
        from capture_desktop.screen_analysis import AnalysisScreen
        from capture_desktop.state import CaptureState
        from capture_desktop.widgets_analysis_plots import FigureGallery
        fixture_path=source/'tests/analysis/test_numeric_batch_pipeline.py'
        spec=importlib.util.spec_from_file_location('accepted_numeric_fixture',fixture_path)
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        package=out/'numeric.mmsession';package.mkdir()
        (package/'manifest.json').write_text(json.dumps({'sessionId':'history.numeric.current','state':'sealed'})+'\n')
        stream=package/'sources/lsl/streams/numeric';stream.mkdir(parents=True)
        helper._write_mcap(stream/'segments/000000.mcap',[(1_000_000_000,helper._batch())])
        (stream/'stream.json').write_text(json.dumps({'sourceId':'lsl','streamId':'numeric.stream','modality':'eeg','dataSchemaId':'generic.numeric_batch/1','nominalRateHz':2.0,'units':'V','dimensions':[2]})+'\n')
        result=run(package,JobParams(command='all',overwrite_job_id='retained-numeric'))
        job=result.job_dir
        pngs=sorted(p for p in (job/'figures').rglob('*.png') if p.name!='sync_dashboard.png')
        report['figure_paths']=[p.relative_to(job).as_posix() for p in pngs]
        report['job_manifest']=json.loads((job/'job_manifest.json').read_text())
        check('current accepted numeric pipeline creates two real channel figures',len(pngs)==2 and all(p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') for p in pngs))
        before=hashes(package)
        app=QApplication([]);theme.apply_theme(app,setting='dark');screen=AnalysisScreen(CaptureState());screen.resize(1280,820)
        direct=FigureGallery();direct.resize(900,620)
        def receive():
            try:
                screen.set_package(str(package));screen.show();screen._history._open.click()
                check('history explicitly selects the retained numeric job',screen._history.loaded_job_id=='retained-numeric' and screen._last_job_dir==str(job))
                check('inspector receives that saved manifest', 'job_id=retained-numeric' in screen._inspector._meta.text())
                history_tabs=[screen._gallery._tabs.tabText(i) for i in range(screen._gallery._tabs.count())]
                report['history_gallery_tabs']=history_tabs
                check('history gallery presents both existing numeric channel figures',screen._gallery._tabs.count()-1==len(pngs))
                direct.load_job_dir(job)
                report['direct_gallery_tabs']=[direct._tabs.tabText(i) for i in range(direct._tabs.count())]
                check('unchanged direct gallery reproduces the same omitted numeric figures',direct._tabs.count()==1 and report['direct_gallery_tabs']==history_tabs and len(pngs)==2)
                check('native history browsing starts no computation thread',screen._thread is None)
                check('native viewing preserves every generated and captured byte',hashes(package)==before)
                screen.grab().save(str(out/'numeric-history-gap.png'))
            except BaseException:report['errors'].append(traceback.format_exc())
            finally:screen.close();direct.close();app.quit()
        QTimer.singleShot(0,receive);loop_code=app.exec()
        screen.deleteLater();direct.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
        report.update({'event_loop_exit':loop_code,'pyside6':PySide6.__version__,'python':sys.version,'package_hashes':before,'fixture_helper_sha256':hashlib.sha256(fixture_path.read_bytes()).hexdigest()})
        status=0 if not report['errors'] and all(c['passed'] for c in report['checks']) else 1
    except BaseException:report['errors'].append(traceback.format_exc())
    report['source_unchanged']=hashes(source)==expected
    report['exit_code']=status;report['passed']=sum(c['passed'] for c in report['checks']);report['failed']=sum(not c['passed'] for c in report['checks'])
    (out/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','failed','source_unchanged','exit_code']}))
    return status


if __name__=='__main__':raise SystemExit(main())
