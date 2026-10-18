# SPDX-License-Identifier: Apache-2.0
"""Rebuild one recorded case from verified inputs, without executing report argv."""
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

from .build import PROJECT, default_source_root
from .process import run_process
from . import reporting as r


class ReproductionError(ValueError):
    pass


def read_json(path):
    if path.stat().st_size > 2*1024*1024:
        raise ReproductionError('Report exceeds 2 MiB')
    return json.loads(path.read_text())


def load_case(path):
    path = Path(path).resolve()
    if path.name != 'failure.json' or path.parent.parent.name != 'cases':
        raise ReproductionError('Select cases/<case-id>/failure.json; run/collection errors are not case replays')
    failure = read_json(path)
    spec = failure.get('reproduction')
    if failure.get('schema_version') != 1 or failure.get('type') != 'testlab.case_failure' or not spec:
        raise ReproductionError('Unsupported or incomplete case reproduction descriptor')
    run_root = path.parent.parent.parent
    run = read_json(run_root/'run.json')
    if run.get('type') != 'testlab.run' or run.get('schema_version') != 1 or run.get('run_id') != failure.get('run_id'):
        raise ReproductionError('Failure and run identity do not match')
    node = spec.get('nodeid', '')
    if spec.get('schema_version') != 1 or spec.get('source_mode') not in {'packaged','snapshot'}:
        raise ReproductionError('Unsupported reproduction profile')
    filename = node.split('::',1)[0]
    allowed = re.fullmatch(r'tests/(host|can|serial)/test_[A-Za-z0-9_]+\.py', filename)
    if not allowed and filename != 'tests/fixtures/reporting_cases.py':
        raise ReproductionError('Test selector must name a recorded TestLab test file')
    if '::' not in node or len(node) > 1024 or any(c in node for c in ('\x00','\n','\r','\\')):
        raise ReproductionError('Invalid exact pytest node')
    if spec.get('suite') != r.suite_of(node) or failure['case'].get('nodeid') != node:
        raise ReproductionError('Case selector identity mismatch')
    if not any(case.get('nodeid') == node and case.get('id') == failure['case'].get('id') for case in run['cases']):
        raise ReproductionError('Case does not belong to this run')
    scale = spec.get('timeout_scale')
    if isinstance(scale, bool) or not isinstance(scale, (int,float)) or not math.isfinite(scale) or scale <= 0:
        raise ReproductionError('Timeout multiplier must be finite and positive')
    if scale != run['context']['timeout_scale']:
        raise ReproductionError('Timeout profile mismatch')
    source = run['source']['snapshot']
    content = {'suites':source['suites'], 'files':source['files']}
    if r.digest_json(content) != source['digest'] or spec.get('source_digest') != source['digest']:
        raise ReproductionError('Recorded source manifest digest mismatch')
    if spec.get('harness_digest') != run['harness']['digest']:
        raise ReproductionError('Recorded harness identity mismatch')
    if r.harness_manifest()['digest'] != run['harness']['digest']:
        raise ReproductionError('Current test harness differs from the recorded harness')
    if run['environment']['python_compatibility'] != list(sys.version_info[:2]):
        raise ReproductionError('Use the recorded Python major/minor version')
    environment = r.environment(set(source['suites']))
    if (environment['system'], environment['machine']) != (run['environment']['system'], run['environment']['machine']):
        raise ReproductionError('Use the recorded OS family and native architecture')
    if environment['dependencies'] != run['environment']['dependencies']:
        raise ReproductionError('Python dependency versions differ from the recorded run')
    # Every path comes from the bounded source manifest, never from a command.
    snapshot = run_root/'inputs/source'
    if r.source_manifest(snapshot, set(source['suites']))['digest'] != source['digest']:
        raise ReproductionError('Saved source snapshot is missing, changed, or contains extra build inputs')
    return failure, run, snapshot


def reproduce(path, *, output_root, source_root=None, backend='native', guest_root=None, wheels=None, timeout=180):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ReproductionError('Launcher timeout must be finite and positive')
    failure, original, snapshot = load_case(path)
    spec = failure['reproduction']
    if backend == 'can-vm' and spec['suite'] != 'can':
        raise ReproductionError('can-vm can reproduce only CAN cases')
    if backend == 'can-vm' and (guest_root is None or wheels is None):
        raise ReproductionError('can-vm requires --guest-root and --wheels')
    expected = original['source']['snapshot']
    selected = Path(source_root).resolve() if source_root is not None else snapshot
    if spec.get('source_mode') == 'packaged':
        selected = default_source_root()
    if r.source_manifest(selected, set(expected['suites']))['digest'] != expected['digest']:
        raise ReproductionError('Selected source tree does not match the recorded inputs')
    out = r.run_directory(output_root)
    prepared = out/'tested-source'
    # Reconstruct a new copy from the validated manifest; no resets/checkouts.
    prepared.mkdir()
    for item in expected['files']:
        if item['sha256'] is not None:
            source = r.inside(selected, item['path'])
            target = r.inside(prepared, item['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    if backend == 'native':
        command = [sys.executable, '-W', 'error::ResourceWarning', '-m', 'pytest', '-q', spec['nodeid'],
            '--source-root', str(prepared), '--timeout-scale', str(spec['timeout_scale']),
            '--testlab-exact-node', spec['nodeid'], '--evidence-root', str(out/'reports')]
    else:
        command = [sys.executable, str(PROJECT/'tools/run_can_suite_vm.py'),
            '--guest-root', str(Path(guest_root).resolve()), '--wheels', str(Path(wheels).resolve()),
            '--source-root', str(prepared), '--pytest-node', spec['nodeid'], '--expected-tests', '1',
            '--case-timeout-scale', str(spec['timeout_scale']), '--timeout', str(max(60,timeout-10)),
            '--output', str(out/'guest')]
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1')
    launched = run_process(command, cwd=str(PROJECT), env=env, log_dir=out/'launcher',
        expected_returncodes=tuple(range(6)), timeout=timeout, max_output_bytes=1024*1024)
    reports = list((out/'reports').glob('*/run.json')) if backend == 'native' else list(
        (out/'guest/guest-artifacts/cases').glob('*/run.json'))
    current = read_json(reports[0]) if len(reports) == 1 else None
    code = current.get('pytest_exitcode') if current else launched.get('returncode')
    if launched.get('timed_out') or not current or launched.get('cleanup_errors'):
        code = 2
    same_node = bool(current and len(current['cases']) == 1 and current['cases'][0]['nodeid'] == spec['nodeid'])
    if not same_node:
        code = 2
    status = 'passed' if code == 0 else 'failed' if code == 1 and current and current['status']=='failed' else 'error'
    result = {'schema_version':1,'type':'testlab.reproduction','status':status,'pytest_exitcode':code,
        'original_status':failure['case']['status'],'nodeid':spec['nodeid'],
        'same_exact_node':same_node,'backend':backend,'original_run_id':original['run_id'],
        'source_digest':expected['digest'],'harness_digest':original['harness']['digest'],
        'source_mode':'verified_packaged_inputs' if spec.get('source_mode')=='packaged' else 'verified_private_snapshot',
        'new_run':str(reports[0]) if len(reports)==1 else None,
        'new_status':current['status'] if current else None,
        'same_case_outcome':bool(current and current['cases'] and current['cases'][0]['status']==failure['case']['status']),
        'new_environment':current['environment'] if current else None,
        'launcher_artifact':'launcher/process.json'}
    r.save_json(out/'reproduction.json', result)
    return int(code), out/'reproduction.json', result
