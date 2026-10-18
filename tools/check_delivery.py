#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the source exporter with real archives, corruption, and isolated source changes."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import stat
import tempfile
import zipfile

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE/'tools'))
from tests.testlab import reporting as r
from tests.testlab.process import run_process
from export_source import source_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(BASE/'upstream'):
        parser.error('Output must be outside source inputs')
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        parser.error(str(exc))
    report = {'schema_version': 1, 'type': 'testlab.delivery_check', 'status': 'error',
              'started_at': r.now(), 'checks': [], 'errors': []}
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    try:
        files, lock = source_files()
        before = {name: r.sha256(BASE/'upstream/examples'/name) for name in lock['files']}
        with tempfile.TemporaryDirectory(prefix='gemstone-delivery-') as temporary:
            root = Path(temporary)
            checkout = root/'source with spaces'
            for name, data in files.items():
                destination = checkout/name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            for name in ('build/private.log', 'artifacts/private.json', '.venv-testlab/token.txt', '.git/config'):
                path = checkout/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('delivery-exclusion-sentinel\n')

            def command(name, *argv, expected=0):
                process = run_process([sys.executable, str(checkout/'tools/export_source.py'), *map(str, argv)],
                    cwd=checkout, env=environment, log_dir=out/name, timeout=30,
                    expected_returncodes=(expected,))
                if process['status'] != 'passed' or process['returncode'] != expected:
                    raise RuntimeError(name+' had an unexpected outcome')
                value = json.loads((out/name/'stdout.log').read_text())
                report['checks'].append({'name': name, 'exitcode': process['returncode'], 'result': value})
                return value

            first, second = root/'first.zip', root/'second.zip'
            command('export-first', '--output', first)
            command('export-second', '--output', second)
            if first.read_bytes() != second.read_bytes():
                raise RuntimeError('Identical source exports differ byte for byte')
            report['deterministic_zip'] = True
            command('verify-intact', '--verify', first)
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
                if any('/'+scope+'/' in n for scope in ('build', 'artifacts', '.git', '.venv-testlab') for n in names):
                    raise RuntimeError('Excluded payload leaked into source ZIP')
                for name, data in files.items():
                    if archive.read('Gemstone_TestLab/'+name) != data:
                        raise RuntimeError('Exported source differs: '+name)
            report['exported_files_match'] = len(files)
            original = first.read_bytes()
            command('refuse-existing-output', '--output', first, expected=2)
            if first.read_bytes() != original:
                raise RuntimeError('Existing ZIP was overwritten')

            def altered(name, change):
                target = root/(name+'.zip')
                with zipfile.ZipFile(first) as source, zipfile.ZipFile(target, 'w') as destination:
                    for item in source.infolist():
                        data = source.read(item.filename)
                        result = change(item, data)
                        if result is not None:
                            destination.writestr(copy.copy(item), result)
                    if name == 'unlisted-file':
                        extra = zipfile.ZipInfo('Gemstone_TestLab/extra.txt')
                        extra.create_system = 3
                        extra.external_attr = (stat.S_IFREG | 0o644) << 16
                        destination.writestr(extra, b'unlisted')
                    elif name == 'escaping-path':
                        destination.writestr('Gemstone_TestLab/../outside.txt', b'outside')
                    elif name == 'duplicate-entry':
                        import warnings
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore', UserWarning)
                            item = source.getinfo('Gemstone_TestLab/README.md')
                            destination.writestr(copy.copy(item), source.read(item.filename))
                command(name, '--verify', target, expected=2)

            altered('changed-file', lambda item, data: data+b'corrupted' if item.filename == 'Gemstone_TestLab/README.md' else data)
            altered('missing-file', lambda item, data: None if item.filename == 'Gemstone_TestLab/README.md' else data)
            altered('unlisted-file', lambda item, data: data)
            altered('escaping-path', lambda item, data: data)
            altered('duplicate-entry', lambda item, data: data)
            altered('malformed-manifest', lambda item, data: b'[]' if item.filename.endswith('/RELEASE_MANIFEST.json') else data)

            upstream = checkout/'upstream/examples/canbus/c/sender/main.c'
            data = upstream.read_bytes()
            upstream.write_bytes(data+b'\n/* controlled source change */\n')
            command('changed-upstream-refused', '--output', root/'dirty.zip', expected=2)
            upstream.write_bytes(data)
            readme = checkout/'README.md'
            data = readme.read_bytes()
            readme.unlink()
            readme.symlink_to(root/'external.txt')
            (root/'external.txt').write_text('external sentinel')
            command('source-symlink-refused', '--output', root/'symlink.zip', expected=2)
            readme.unlink()
            readme.write_bytes(data)
            command('source-output-path-refused', '--output', checkout/'tools/export.zip', expected=2)
        report['original_unchanged'] = before == {name: r.sha256(BASE/'upstream/examples'/name) for name in lock['files']}
        if not report['original_unchanged']:
            raise RuntimeError('Original source changed during delivery checks')
        report['status'] = 'passed'
    except Exception as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    report['finished_at'] = r.now()
    r.save_json(out/'delivery.json', report)
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
