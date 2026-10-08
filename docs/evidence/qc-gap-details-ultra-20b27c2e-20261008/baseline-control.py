# SPDX-License-Identifier: GPL-3.0-only
"""Reproduce the baseline QC omission using the native package and CLI."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / 'capturesuite'
for name in ('capture_protocol', 'capture_session', 'capture_analysis'):
    sys.path.insert(0, str(REPO / 'libs' / 'python' / name))
os.environ.setdefault('MPLCONFIGDIR', str(HERE / 'mpl-cache'))
from capture_analysis import collect_qc  # noqa: E402
from capture_analysis.report_html import render_qc_html  # noqa: E402


def raw_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file()
            and p.relative_to(root).parts[0] != 'processing'}


def main() -> None:
    gap = {'sourceId': 'sim.emg.main', 'streamId': 'sim.emg.main.batch',
           'cause': 'DISCONNECT', 'startSessionTimeNs': '2000000000',
           'endSessionTimeNs': '4500000000', 'closed': True,
           'estimatedLostCount': '5000'}
    observations = {}
    for case in ('no_gap', 'closed_gap'):
        dest = HERE / (case + '.mmsession')
        if dest.exists():
            raise RuntimeError(f'refusing to overwrite prior evidence: {dest}')
        shutil.copytree(REPO / 'tests' / 'fixtures' / 'mini_session', dest)
        if case == 'closed_gap':
            (dest / 'sources/sim.emg.main/health/gaps.jsonl').write_text(
                json.dumps(gap) + '\n', encoding='utf-8')
        before = raw_hashes(dest)
        qc = collect_qc(dest).to_dict()
        html = render_qc_html(qc)
        (HERE / (case + '-qc.json')).write_text(json.dumps(qc, indent=2) + '\n')
        (HERE / (case + '-qc.html')).write_text(html)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        cli = subprocess.run([sys.executable, str(REPO / 'tools/run_analysis.py'), 'qc',
                              str(dest), '--overwrite-job-id', 'baseline-qc'],
                             cwd=REPO, env=env, text=True, capture_output=True, timeout=30)
        (HERE / (case + '-cli.log')).write_text(cli.stdout + cli.stderr)
        assert cli.returncode == 0, cli.stdout + cli.stderr
        emitted = json.loads((dest / 'processing/jobs/baseline-qc/reports/qc.json').read_text())
        assert emitted == qc
        assert raw_hashes(dest) == before, 'QC changed input bytes'
        observations[case] = {'trafficLights': qc['trafficLights'],
                              'openGapCount': qc['openGapCount'],
                              'closedGapCount': qc['closedGapCount'],
                              'warnings': qc['warnings'],
                              'hasGapDetails': 'gaps' in qc,
                              'htmlContainsDisconnect': 'DISCONNECT' in html,
                              'cliExitCode': cli.returncode,
                              'rawHashesBeforeAndAfter': before}
    receipt = {'base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip(),
               'python': sys.version, 'fixtureGap': gap, 'observations': observations,
               'scope': 'Native Python collect_qc, renderer, and actual run_analysis.py qc; copied synthetic fixture only.',
               'environmentLimit': 'The base environment does not include jsonschema; native job validation records that warning. Gap collection, report output, and raw preservation are exercised without a replacement implementation.'}
    (HERE / 'baseline-reproduction.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({k:{x:v for x,v in row.items() if x != 'rawHashesBeforeAndAfter'}
                      for k,row in observations.items()}, indent=2))

if __name__ == '__main__':
    main()

