#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove each proposed patch independently: failing pristine cases, then passing patched cases."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab import reporting as r
from tests.testlab import ci_gate as gate
from tests.testlab.patching import copy_patch_environment
from tests.testlab.process import run_process


def check_run(path, nodes, phase):
    value = gate.read(path)
    gate.require(value['collected'] == len(nodes) and
                 sorted(c['nodeid'] for c in value['cases']) == sorted(nodes), 'Wrong regression selection')
    expected = 'failed' if phase == 'baseline' else 'passed'
    gate.require(value['status'] == expected and not value['policy_errors'], 'Wrong regression outcome/phase')
    gate.require(value['counts'][expected] == len(nodes) and
                 sum(value['counts'].values()) == len(nodes), 'Unexpected skip or setup/teardown error')
    if phase == 'fixed':
        gate.validate_pytest(path, nodes)
    else:
        for case in value['cases']:
            detail = gate.read(path.parent/case['result_artifact'])
            gate.require([(p['phase'], p['outcome']) for p in detail['phases']] ==
                         [('setup', 'passed'), ('call', 'failed'), ('teardown', 'passed')],
                         'Baseline must fail in the assertion, not in setup or cleanup')
        gate.require(value['pytest_exitcode'] == value['original_pytest_exitcode'] == 1,
                     'Baseline must preserve the real pytest failure code')
    return {'run_report': str(path), 'status': value['status'], 'counts': value['counts'],
            'pytest_exitcode': value['pytest_exitcode']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--entry', choices=('01', '02', '03', '04', '05'), action='append')
    parser.add_argument('--can-backend', choices=('native', 'vm'), default='native')
    parser.add_argument('--guest-root', type=Path)
    parser.add_argument('--wheels', type=Path)
    args = parser.parse_args()
    if args.can_backend == 'vm' and (not args.guest_root or not args.wheels):
        parser.error('VM backend requires --guest-root and --wheels')
    if args.can_backend == 'native' and (args.guest_root or args.wheels):
        parser.error('VM options require --can-backend vm')
    out = args.output.resolve()
    source = BASE/'upstream/examples'
    if out == source or out.is_relative_to(source):
        parser.error('Output must be outside the pristine source tree')
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(str(exc))
    result = {'schema_version': 1, 'type': 'testlab.contribution_check', 'status': 'error',
              'started_at': r.now(), 'publication_status': 'draft_not_submitted', 'entries': [], 'errors': [],
              'execution': {'github_hosted_runner': 'not_executed', 'board_runtime': 'not_run'}}
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    for name in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'TESTLAB_EVIDENCE_ROOT'):
        environment.pop(name, None)
    before = None
    lock = gate.read(BASE/'source.lock.json')
    try:
        series = gate.read(BASE/'contributions/series.json')
        gate.require(series['upstream_revision'] == lock['revision'], 'Series revision differs')
        before = {name: r.sha256(source/name) for name in lock['files']}
        gate.require(all(before[n] == e['sha256'] for n, e in lock['files'].items()), 'Pristine inputs changed')
        rules = gate.contract()['profiles']
        for entry in series['entries']:
            if args.entry and entry['id'] not in args.entry:
                continue
            item = {'id': entry['id'], 'patch': entry['patch'], 'status': 'error'}
            result['entries'].append(item)
            try:
                nodes = entry['nodes']
                gate.require(entry['profile'] in ('can', 'serial') and nodes and
                             set(nodes).issubset(rules[entry['profile']]['required_nodes']), 'Unknown regression selectors')
                patch = BASE/'patches'/entry['patch']
                gate.require(patch.parent == BASE/'patches' and patch.is_file(), 'Invalid patch path')
                item['patch_sha256'] = r.sha256(patch)
                folder = out/entry['id']
                work = folder/'work'
                work.mkdir(parents=True)
                fixed = work/'fixed'
                for name in lock['files']:
                    destination = fixed/name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source/name, destination)
                for phase, extra in (('check', ['--check']), ('apply', [])):
                    process = run_process(['git', '-c', 'core.hooksPath=/dev/null', 'apply', *extra, str(patch)],
                        cwd=fixed, env=copy_patch_environment(fixed), log_dir=folder/('patch-'+phase), timeout=10)
                    gate.require(process['status'] == 'passed', 'Patch '+phase+' failed')
                changed = sorted(n for n in before if r.sha256(fixed/n) != before[n])
                gate.require(changed == sorted(entry['files']), 'Patch touched unexpected files')
                item['changed_files'] = changed
                for phase, tree in (('baseline', source), ('fixed', fixed)):
                    destination = folder/phase
                    vm = entry['profile'] == 'can' and args.can_backend == 'vm'
                    if vm:
                        gate.require(len(nodes) == 1, 'VM focused adapter requires one exact node')
                        argv = [sys.executable, str(BASE/'tools/run_can_suite_vm.py'),
                                '--guest-root', str(args.guest_root.resolve()), '--wheels', str(args.wheels.resolve()),
                                '--source-root', str(tree), '--output', str(destination),
                                '--pytest-node', nodes[0], '--expected-tests', '1']
                    else:
                        argv = [sys.executable, '-W', 'error::ResourceWarning', '-m', 'pytest', '-q',
                                *nodes, '--source-root', str(tree), '--evidence-root', str(destination/'reports')]
                    expected = 1 if phase == 'baseline' else 0
                    process = run_process(argv, cwd=BASE, env=environment, timeout=660 if vm else 150,
                        log_dir=folder/(phase+'-launcher'), expected_returncodes=(expected,),
                        max_output_bytes=8*1024*1024)
                    gate.require(process['status'] == 'passed' and process['returncode'] == expected,
                                 'Unexpected '+phase+' launcher outcome')
                    runs = [p for p in destination.rglob('run.json') if gate.read(p).get('type') == 'testlab.run']
                    gate.require(len(runs) == 1, 'Missing or ambiguous pytest regression report')
                    item[phase] = check_run(runs[0], nodes, phase)
                    if vm:
                        summary = gate.read(destination/'guest-artifacts/guest-summary.json')
                        gate.require(summary['remaining_interfaces'] == [] and summary['runner_uid'] == 1000,
                                     'VM cleanup or UID differs')
                item['status'] = 'passed'
                shutil.rmtree(work)
            except Exception as exc:
                item['error'] = type(exc).__name__+': '+str(exc)
                result['errors'].append(entry['id']+': '+item['error'])
        gate.require(bool(result['entries']), 'No contribution selected')
        result['status'] = 'failed' if result['errors'] else 'passed'
    except Exception as exc:
        result['errors'].append(type(exc).__name__+': '+str(exc))
    finally:
        result['original_unchanged'] = before is not None and before == {n: r.sha256(source/n) for n in lock['files']}
        if not result['original_unchanged']:
            result['status'] = 'error'
        result['finished_at'] = r.now()
        r.save_json(out/'contributions.json', result)
    print(json.dumps(result, indent=2))
    return {'passed': 0, 'failed': 1, 'error': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
