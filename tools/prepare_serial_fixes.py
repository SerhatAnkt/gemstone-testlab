#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the four proposed serial fixes to a new, explicitly selected source copy."""
import argparse
import json
from pathlib import Path
import shutil
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from tests.testlab.build import default_source_root, sha256
from tests.testlab.process import run_process
from tests.testlab.patching import copy_patch_environment

PATCHES = (
    '0002-serial-preserve-raw-input-bytes.patch',
    '0003-serial-reject-partial-baud-arguments.patch',
    '0004-serial-python-read-unbuffered-stdin.patch',
    '0005-serial-python-preserve-argparse-exit-code.patch',
)
CHANGED = {'serial/c/main.c', 'serial/cpp/main.cpp', 'serial/cpp/serial_terminal.cpp',
           'serial/python/main.py', 'serial/python/serial_terminal.py'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New directory outside the source tree')
    args = parser.parse_args()
    source = (args.source_root or default_source_root()).resolve()
    out = args.output.resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must be outside the source tree')
    lock = json.loads((BASE/'source.lock.json').read_text())
    before = {name: sha256(source/name) for name in lock['files']}
    shutil.copytree(source, out, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'build'))
    result = {'schema_version': 1, 'status': 'failed', 'source_root': str(source),
              'prepared_source': str(out), 'original_hashes': before, 'patches': []}
    try:
        for index, name in enumerate(PATCHES, 1):
            patch = BASE/'patches'/name
            entry = {'path': str(patch), 'sha256': sha256(patch)}
            result['patches'].append(entry)
            for phase, extra in (('check', ['--check']), ('apply', [])):
                command = ['git', '-c', 'core.hooksPath=/dev/null', 'apply', *extra, str(patch)]
                record = run_process(command, cwd=str(out),
                    env=copy_patch_environment(out),
                    log_dir=out/'testlab-serial-fix-evidence'/f'{index:02d}-{phase}', timeout=5)
                if record['status'] != 'passed':
                    raise RuntimeError('Patch '+name+' '+phase+' failed; see testlab-serial-fix-evidence')
        after = {name: sha256(out/name) for name in lock['files']}
        changed = sorted(name for name in before if before[name] != after[name])
        assert set(changed) == CHANGED, changed
        result.update(status='passed', changed_files=changed, prepared_hashes=after)
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        result['original_unchanged'] = before == {name: sha256(source/name) for name in lock['files']}
        if not result['original_unchanged']:
            result['status'] = 'failed'
        (out/'testlab-serial-fixes.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ('status', 'prepared_source', 'original_unchanged')}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
