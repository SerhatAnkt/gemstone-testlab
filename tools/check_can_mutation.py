#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove a live receiver test rejects a deliberately corrupted DLC printout.

The upstream tree stays unchanged. A private source copy is built and run in
the Linux guest; this command succeeds only when the selected pytest case fails
for the intended mismatch and all owned resources are collected.
"""
import argparse
import difflib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab.build import default_source_root, sha256
from tests.testlab.process import run_process

NODE = 'tests/can/test_receiver.py::test_receiver_classic_lengths[c-one]'
MESSAGE = 'Receiver DLC does not match its hex output'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest-root', type=Path, required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-root', type=Path)
    args = parser.parse_args()
    source = (args.source_root or default_source_root()).resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    original = source/'canbus/c/receiver/main.c'
    before = sha256(original)
    result = {'schema_version': 1, 'experiment': 'controlled_receiver_dlc_corruption',
              'status': 'failed', 'pytest_node': NODE, 'original_sha256': before}
    try:
        modified = out/'modified-examples'
        shutil.copytree(source, modified, ignore=shutil.ignore_patterns('__pycache__', '.git', '*.pyc'))
        target = modified/original.relative_to(source)
        text = target.read_text()
        needle = 'frame.can_id, frame.can_dlc);'
        assert text.count(needle) == 1, 'Mutation anchor changed; inspect the selected source first'
        changed = text.replace(needle, 'frame.can_id, frame.can_dlc + (frame.can_id == 0x123 ? 1 : 0));')
        target.write_text(changed)
        (out/'change.patch').write_text(''.join(difflib.unified_diff(text.splitlines(True), changed.splitlines(True),
            fromfile='a/canbus/c/receiver/main.c', tofile='b/canbus/c/receiver/main.c')))
        result['mutated_sha256'] = sha256(target)
        command = [sys.executable, str(BASE/'tools/run_can_suite_vm.py'),
                   '--guest-root', str(args.guest_root.resolve()), '--wheels', str(args.wheels.resolve()),
                   '--source-root', str(modified), '--output', str(out/'guest'),
                   '--pytest-node', NODE, '--expected-tests', '1', '--timeout', '240']
        process = run_process(command, cwd=str(BASE), log_dir=out/'runner', timeout=270, expected_returncodes=(1,))
        assert process['status'] == 'passed' and process['returncode'] == 1, 'Expected the selected test to fail'
        guest = json.loads((out/'guest/run.json').read_text())
        summary = guest['summary']
        suite = ET.parse(out/'guest/guest-artifacts/junit.xml').getroot().find('testsuite')
        assert suite.get('tests') == '1' and suite.get('failures') == '1'
        assert suite.get('errors') == '0' and suite.get('skipped') == '0'
        assert guest['status'] == 'failed' and summary['scope'] == 'selected_tests'
        assert len(summary['cases']) == 1
        case = summary['cases'][0]
        assert case['status'] == 'failed' and case['error']['type'] == 'ValueError'
        assert MESSAGE in case['error']['message']
        assert case['target_uids'] == [1000]*4 and case['pty_closed'] and case['publisher_closed']
        assert summary['owned_interfaces'] == summary['owned_interfaces_removed'] == 1
        assert summary['remaining_interfaces'] == []
        records = [json.loads(p.read_text()) for p in (out/'guest/guest-artifacts').rglob('process.json')]
        assert records and all(not r.get('cleanup_errors') and all(r['cleanup'][key] for key in
            ('group_gone', 'leader_reaped', 'owned_pipe_fds_closed')) for r in records)
        result.update(status='passed', observed_failure=case['error'], pytest_failures=1,
                      interfaces_removed=1, process_records=len(records),
                      note='The experiment passed because the live test rejected the deliberate corruption. This is not an upstream defect.')
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        result['original_unchanged'] = sha256(original) == before
        if not result['original_unchanged']:
            result['status'] = 'failed'
        (out/'controlled-failure.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
