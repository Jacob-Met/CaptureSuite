# SPDX-License-Identifier: GPL-3.0-only
"""Bounded native receiving replay; uses existing dependencies without installs."""

from __future__ import annotations

import hashlib
import json
import os
import resource
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OWNER = Path('/workspace/scratch/20b27c2ea29e/workers/estate-production/capturesuite')
DEPS = [
    '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages',
    '/workspace/scratch/20b27c2ea29e/workers/estate-production/venv/lib/python3.12/site-packages',
    '/workspace/scratch/20b27c2ea29e/workers/runtime-integration/product-discovery/canvaspilot/venv/lib/python3.12/site-packages',
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limits() -> None:
    resource.setrlimit(resource.RLIMIT_FSIZE, (3 * 1024**2, 3 * 1024**2))


def used_bytes() -> int:
    return sum(p.stat().st_blocks * 512 for p in ROOT.rglob('*') if p.is_file())


def main() -> None:
    closure = json.loads((ROOT / 'source-closure.json').read_text())
    frozen = closure['candidate_entries']
    for row in frozen:
        assert sha(ROOT / 'candidate' / row['path']) == row['sha256']
    owner_before = {p: sha(OWNER / p) for p in closure['candidate_owned']}
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=os.pathsep.join(DEPS),
               TMPDIR=str(ROOT / 'temp'), MPLCONFIGDIR=str(ROOT / 'mpl-config'),
               OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    versions_code = '''import importlib.metadata as m,json,sys
print(json.dumps({"python":sys.version,"distributions":{n:m.version(n) for n in ("pytest","numpy","scipy","pandas","matplotlib","PyYAML","jsonschema")}}))'''
    versions = subprocess.run([sys.executable, '-c', versions_code], env=env,
                              capture_output=True, text=True, check=True, timeout=15)
    receipt = {'review_source_closure_sha256': sha(ROOT / 'source-closure.json'),
               'harness_sha256': sha(ROOT / 'test_independent_capture_receiving.py'),
               'versions': json.loads(versions.stdout), 'runs': [],
               'limits': {'namespace_abort_bytes': 20 * 1024**2,
                          'child_file_bytes': 3 * 1024**2, 'timeout_seconds': 60},
               'environment': {key: env[key] for key in ('PYTHONDONTWRITEBYTECODE','PYTHONPATH','TMPDIR','MPLCONFIGDIR','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')}}
    peak = used_bytes()
    for label in ('candidate', 'baseline'):
        xml_path = ROOT / (label + '-result.xml')
        command = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '--capture=sys', '--basetemp', str(ROOT / 'temp' / label),
                   '--junitxml', str(xml_path), str(ROOT / 'test_independent_capture_receiving.py')]
        if label == 'baseline':
            command += ['-k', 'actual_cli_renders_gap or actual_cli_no_gap_positive_control']
        child_env = env | {'CAPTURE_REVIEW_CHECKOUT': str(ROOT / label)}
        started = time.monotonic()
        aborted = None
        log_path = ROOT / (label + '-result.log')
        with log_path.open('wb') as log:
            proc = subprocess.Popen(command, cwd=ROOT, env=child_env, stdout=log,
                                    stderr=subprocess.STDOUT, preexec_fn=limits)
            while proc.poll() is None:
                peak = max(peak, used_bytes())
                if peak > 20 * 1024**2 or time.monotonic() - started > 60:
                    aborted = 'bounded namespace or time limit reached'
                    proc.terminate()
                    break
                time.sleep(0.05)
            try:
                code = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = proc.wait(timeout=5)
        suites = list(ET.parse(xml_path).getroot().iter('testsuite')) if xml_path.exists() else []
        counts = {key: sum(int(s.get(key, '0')) for s in suites)
                  for key in ('tests', 'failures', 'errors', 'skipped')}
        item = {'label': label, 'command': command, 'returncode': code,
                'seconds': round(time.monotonic()-started, 3), 'counts': counts,
                'aborted': aborted, 'log_sha256': sha(log_path),
                'xml_sha256': sha(xml_path) if xml_path.exists() else None}
        receipt['runs'].append(item)
        print(json.dumps(item), flush=True)
        (ROOT / 'execution-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    receipt['peak_namespace_allocated_bytes'] = max(peak, used_bytes())
    receipt['frozen_candidate_closure_unchanged'] = all(
        sha(ROOT / 'candidate' / row['path']) == row['sha256'] for row in frozen)
    receipt['owner_source_unchanged'] = owner_before == {p: sha(OWNER / p) for p in owner_before}
    (ROOT / 'execution-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')


if __name__ == '__main__':
    main()
