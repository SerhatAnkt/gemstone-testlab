#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the proposed CAN sender fix to a new private examples copy."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New directory; original tree is never edited')
    args = parser.parse_args()
    source = (args.source_root or default_source_root()).resolve()
    out = args.output.resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must be outside the source tree')
    lock = json.loads((BASE/'source.lock.json').read_text())
    before = {name: sha256(source/name) for name in lock['files']}
    shutil.copytree(source, out, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'build'))
    patch = BASE/'patches/0001-can-c-sender-check-interface-index.patch'
    result = {'schema_version': 1, 'status': 'failed', 'source_root': str(source), 'prepared_source': str(out),
              'patch': str(patch), 'patch_sha256': sha256(patch), 'original_hashes': before}
    try:
        for phase, extra in (('check', ['--check']), ('apply', [])):
            command = ['git', '-c', 'core.hooksPath=/dev/null', 'apply', *extra, str(patch)]
            record = run_process(command, cwd=str(out), env=copy_patch_environment(out),
                                 log_dir=out/'testlab-fix-evidence'/phase, timeout=5)
            if record['status'] != 'passed':
                raise RuntimeError('Patch '+phase+' failed; see testlab-fix-evidence')
        after = {name: sha256(out/name) for name in lock['files']}
        changed = [name for name in before if before[name] != after[name]]
        assert changed == ['canbus/c/sender/main.c'], changed
        result.update(status='passed', changed_files=changed, prepared_hashes=after)
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    finally:
        result['original_unchanged'] = before == {name: sha256(source/name) for name in lock['files']}
        if not result['original_unchanged']:
            result['status'] = 'failed'
        (out/'testlab-fix.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({key: result[key] for key in ('status', 'prepared_source', 'original_unchanged')}, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
