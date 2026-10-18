#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove that the real PTY test rejects a deliberately corrupted serial byte."""
import argparse
import difflib
import json
import os
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab.build import default_source_root, sha256
from tests.testlab.process import run_process


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = (args.source_root or default_source_root()).resolve()
    out = args.output.resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must be outside the source tree')
    out.mkdir(parents=True, exist_ok=False)
    lock = json.loads((BASE/'source.lock.json').read_text())
    original = {p: sha256(source/p) for p in lock['files']}
    copy = out/'modified-examples'
    shutil.copytree(source, copy, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'build'))
    target = copy/'serial/c/main.c'
    before = target.read_text()
    old = '                // Send to serial port\n'
    assert before.count(old) == 1
    after = before.replace(old, old+'                buffer[0] ^= 1; // Controlled TestLab fault, private copy only.\n')
    target.write_text(after)
    (out/'change.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
        fromfile='a/serial/c/main.c', tofile='b/serial/c/main.c')))
    argv = [sys.executable, '-W', 'error::ResourceWarning', '-m', 'pytest',
        'tests/serial/test_terminal.py::test_serial_transmit[text-burst-c]', '-q',
        '--source-root', str(copy), '--evidence-root', str(out/'cases'), '--junitxml='+str(out/'junit.xml')]
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1')
    process = run_process(argv, cwd=str(BASE), env=env, log_dir=out/'pytest',
                          expected_returncodes=(1,), timeout=45)
    result = {'schema_version': 1, 'status': 'failed', 'source_root': str(source),
              'pytest_returncode': process['returncode'], 'mutation': 'flip first TX byte in C only',
              'expected_failure': 'tx byte mismatch', 'source_before': original}
    try:
        root = ET.parse(out/'junit.xml').getroot()
        cases = root.findall('.//testcase')
        assert process['status'] == 'passed' and process['returncode'] == 1, process
        assert len(cases) == 1 and len(cases[0].findall('failure')) == 1
        assert not root.findall('.//error') and not root.findall('.//skipped')
        assert 'tx byte mismatch' in cases[0].find('failure').get('message', '')
        reports = [json.loads(p.read_text()) for p in (out/'cases').rglob('case.json')]
        assert len(reports) == 1 and reports[0]['status'] == 'failed'
        assert reports[0]['pty_fds_closed'] and not reports[0]['cleanup_errors']
        assert reports[0]['readiness']['attempts'] == 1
        records = [json.loads(p.read_text()) for p in (out/'cases').rglob('process.json')]
        assert records and all(r['cleanup']['group_gone'] and r['cleanup']['leader_reaped'] for r in records)
        assert set(p for p in original if sha256(copy/p) != original[p]) == {'serial/c/main.c'}
        result.update(status='passed', observed_message=cases[0].find('failure').get('message'),
                      selected_tests=1, observed_failures=1, process_records=len(records),
                      pty_fds_closed=True, groups_collected=True)
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        result['original_unchanged'] = original == {p: sha256(source/p) for p in original}
        if not result['original_unchanged']:
            result['status'] = 'failed'
        (out/'experiment.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ('status', 'pytest_returncode', 'original_unchanged')}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
