#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run all four mandatory profiles, then verify their local acceptance together."""
import argparse
import json
import math
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab import reporting as r
from tests.testlab.build import default_source_root, git_state
from tests.testlab.ci_gate import verify_profiles
from tests.testlab.process import run_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New evidence directory')
    parser.add_argument('--toolchain-root', required=True, type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--source-profile', choices=('working-tree', 'proposed-fixes'), default='working-tree')
    parser.add_argument('--can-backend', choices=('native', 'vm'), default='native')
    parser.add_argument('--guest-root', type=Path, help='Prepared x86 Linux VM runtime, for --can-backend vm')
    parser.add_argument('--wheels', type=Path, help='Pinned pytest wheels, for --can-backend vm')
    parser.add_argument('--profile-timeout', type=float, default=600)
    args = parser.parse_args()
    if not math.isfinite(args.profile_timeout) or args.profile_timeout <= 60:
        parser.error('--profile-timeout must be finite and exceed 60 seconds')
    if args.can_backend == 'vm' and (not args.guest_root or not args.wheels):
        parser.error('--can-backend vm requires --guest-root and --wheels')
    if args.can_backend == 'vm' and args.source_profile != 'proposed-fixes':
        parser.error('The current VM CI adapter requires explicit --source-profile proposed-fixes')
    if args.can_backend == 'native' and (args.guest_root or args.wheels):
        parser.error('VM runtime options require --can-backend vm')
    out = args.output.resolve()
    source = (args.source_root or default_source_root()).resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must be outside the examples source tree')
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(str(exc))
    report = {'schema_version': 1, 'type': 'testlab.release', 'status': 'error', 'exitcode': 2,
              'started_at': r.now(), 'source_profile': args.source_profile,
              'can_backend': args.can_backend, 'profiles': [], 'errors': [],
              'execution': {'github_hosted_runner': 'not_executed', 'board_runtime': 'not_run',
                            'arm64_execution_mode': 'cross_build_only'}}
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    profiles = []
    try:
        if args.can_backend == 'vm' and git_state(BASE).get('commit'):
            raise ValueError('The VM adapter cannot carry checkout identity; use the source ZIP without Git metadata, or native CAN from the checkout')
        # Run every profile even when one fails: a missing prerequisite must stay visible.
        for profile in ('host', 'serial', 'can', 'aarch64'):
            print('TestLab release: starting '+profile, flush=True)
            folder = out/profile
            ci = folder/'ci.json'
            if profile == 'can' and args.can_backend == 'vm':
                argv = [sys.executable, str(BASE/'tools/run_can_suite_vm.py'), '--ci-profile',
                        '--guest-root', str(args.guest_root.resolve()), '--wheels', str(args.wheels.resolve()),
                        '--source-root', str(source), '--output', str(folder),
                        '--timeout', str(args.profile_timeout)]
                ci = folder/'guest-artifacts/ci-can/ci.json'
            else:
                argv = [sys.executable, '-m', 'tests.testlab', 'ci', '--profile', profile,
                        '--source-root', str(source), '--output', str(folder),
                        '--timeout', str(args.profile_timeout-30)]
                if profile in ('serial', 'can'):
                    argv += ['--source-profile', args.source_profile]
                if profile == 'aarch64':
                    argv += ['--toolchain-root', str(args.toolchain_root.resolve())]
            process = run_process(argv, cwd=BASE, env=environment,
                                  log_dir=out/'launchers'/profile,
                                  timeout=args.profile_timeout+60, max_output_bytes=8*1024*1024,
                                  expected_returncodes=(0, 1, 2))
            entry = {'profile': profile, 'returncode': process['returncode'],
                     'launcher_status': process['status'], 'timed_out': process['timed_out'],
                     'ci_report': ci.relative_to(out).as_posix(),
                     'process_report': 'launchers/'+profile+'/process.json'}
            report['profiles'].append(entry)
            profiles.append(ci)
            if process['status'] != 'passed' or process['returncode'] != 0:
                report['errors'].append(profile+' execution failed; see '+entry['process_report'])
            print('TestLab release: '+profile+' exit '+str(process['returncode']), flush=True)
        acceptance = verify_profiles(profiles, out/'acceptance.json',
                                     expected_commit=os.environ.get('TESTLAB_EXPECTED_COMMIT'))
        report['acceptance_report'] = 'acceptance.json'
        if acceptance['status'] != 'passed':
            report['errors'].extend(acceptance['errors'])
        if not report['errors']:
            report.update(status='passed', exitcode=0)
        else:
            infrastructure = any(x['launcher_status'] != 'passed' or x['returncode'] not in (0, 1)
                                 for x in report['profiles'])
            report.update(status='error' if infrastructure else 'failed', exitcode=2 if infrastructure else 1)
    except Exception as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    finally:
        report['finished_at'] = r.now()
        r.save_json(out/'release.json', report)
    print(json.dumps({'status': report['status'], 'exitcode': report['exitcode'],
                      'report': str(out/'release.json'), 'errors': report['errors']}, indent=2))
    return report['exitcode']


if __name__ == '__main__':
    raise SystemExit(main())
