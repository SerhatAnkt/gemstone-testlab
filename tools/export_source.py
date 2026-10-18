#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export or verify a deterministic source-only ZIP; never include build/evidence trees."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

BASE = Path(__file__).resolve().parents[1]
ROOT = 'Gemstone_TestLab/'
MANIFEST = 'RELEASE_MANIFEST.json'
TOP = ('README.md', 'QUICKSTART.md', 'CONTRIBUTING.md', 'RESULTS.md', 'LICENSE', 'NOTICE',
       '.gitignore', 'source.lock.json', 'pytest.ini')
FOLDERS = ('tests', 'tools', 'docs', 'patches', 'contributions', '.github')
SUFFIXES = {'.py', '.sh', '.c', '.h', '.json', '.txt', '.md', '.patch', '.yml', '.yaml'}
IGNORED = {'__pycache__', '.pytest_cache', '.git'}
LIMIT = 16*1024*1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True)+'\n').encode()


def source_files():
    paths = [BASE/name for name in TOP]
    for folder in FOLDERS:
        if (BASE/folder).is_symlink() or not (BASE/folder).is_dir():
            raise ValueError('Required source directory is missing or a symlink: '+folder)
        for path in (BASE/folder).rglob('*'):
            if set(path.relative_to(BASE).parts) & IGNORED:
                continue
            if path.is_symlink():
                raise ValueError('Source export refuses symlinks: '+str(path))
            if path.is_file() and path.suffix in SUFFIXES:
                paths.append(path)
    lock = json.loads((BASE/'source.lock.json').read_text())
    for name, entry in lock['files'].items():
        path = BASE/'upstream/examples'/name
        if path.is_symlink():
            raise ValueError('Pinned upstream input is a symlink: '+name)
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if digest(data) != entry['sha256'] or len(data) != entry['size_bytes'] or blob != entry['git_blob_sha1']:
            raise ValueError('Pinned upstream input changed: '+name)
        paths.append(path)
    files = {}
    for path in sorted(set(paths)):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(BASE)) or not path.is_file():
            raise ValueError('Required export input is not a regular file: '+str(path))
        data = path.read_bytes()
        if data.startswith(b'\x7fELF'):
            raise ValueError('Binary found in source inputs: '+str(path))
        files[path.relative_to(BASE).as_posix()] = data
    if sum(map(len, files.values())) > LIMIT or len(files) > 2048:
        raise ValueError('Source export exceeds its size/file budget')
    return files, lock


def export(output):
    files, lock = source_files()
    entries = [{'path': name, 'size_bytes': len(data), 'sha256': digest(data),
                'mode': '0755' if name.endswith('.sh') else '0644'} for name, data in files.items()]
    manifest = {'schema_version': 1, 'type': 'testlab.source_distribution',
                'upstream': {'repository': lock['repository'], 'revision': lock['revision'],
                             'original_files': len(lock['files'])},
                'files': entries, 'content_sha256': digest(json_bytes(entries)),
                'excludes': ['historical evidence', 'SDK', 'wheels', 'build outputs', 'Git metadata'],
                'execution': {'github_hosted_runner': 'not_executed', 'board_runtime': 'not_run'}}
    files[MANIFEST] = json_bytes(manifest)
    output = output.resolve()
    if any(output.is_relative_to(BASE/name) for name in (*FOLDERS, 'upstream')):
        raise ValueError('Export output must not be inside source input directories')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(ROOT+name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return verify(output)


def verify(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > 2049:
            raise ValueError('Duplicate or excessive archive entries')
        if sum(p.file_size for p in archive.infolist()) > LIMIT+2*1024*1024:
            raise ValueError('Archive exceeds its expanded-size budget')
        for item in archive.infolist():
            name = item.filename
            relative = PurePosixPath(name)
            if not name.startswith(ROOT) or '..' in relative.parts or '\\' in name or relative.is_absolute():
                raise ValueError('Invalid source archive path')
            if not stat.S_ISREG(item.external_attr >> 16) or item.is_dir():
                raise ValueError('Source archive must contain regular files only')
        manifest = json.loads(archive.read(ROOT+MANIFEST))
        if not isinstance(manifest, dict) or manifest.get('type') != 'testlab.source_distribution' or manifest.get('schema_version') != 1:
            raise ValueError('Unknown source manifest')
        files = manifest['files']
        if not isinstance(files, list) or not files or len(files) > 2048:
            raise ValueError('Invalid source inventory')
        for entry in files:
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                raise ValueError('Invalid source inventory entry')
            name = entry['path']
            parts = PurePosixPath(name).parts
            if not parts or '..' in parts or name.startswith('/') or '\\' in name:
                raise ValueError('Invalid manifest path')
            allowed = name in TOP or (parts[0] in FOLDERS and PurePosixPath(name).suffix in SUFFIXES)
            allowed = allowed or name.startswith('upstream/examples/')
            if not allowed or set(parts) & IGNORED or data_binary_name(name):
                raise ValueError('Non-source manifest entry: '+name)
            if entry.get('mode') not in ('0644', '0755') or not isinstance(entry.get('size_bytes'), int):
                raise ValueError('Invalid source inventory metadata')
            if not isinstance(entry.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
                raise ValueError('Invalid source inventory digest')
        if manifest['content_sha256'] != digest(json_bytes(files)):
            raise ValueError('Manifest content digest differs')
        expected = [ROOT+e['path'] for e in files] + [ROOT+MANIFEST]
        if len(expected) != len(set(expected)) or set(expected) != set(names):
            raise ValueError('Archive inventory differs')
        for entry in files:
            data = archive.read(ROOT+entry['path'])
            if len(data) != entry['size_bytes'] or digest(data) != entry['sha256']:
                raise ValueError('Source file digest differs: '+entry['path'])
            mode = stat.S_IMODE(archive.getinfo(ROOT+entry['path']).external_attr >> 16)
            if mode != int(entry['mode'], 8):
                raise ValueError('Source file mode differs: '+entry['path'])
        if archive.testzip():
            raise ValueError('ZIP CRC failure')
    return {'status': 'passed', 'archive': str(path.absolute()), 'files': len(files),
            'size_bytes': path.stat().st_size, 'sha256': digest(path.read_bytes()),
            'content_sha256': manifest['content_sha256']}


def data_binary_name(name):
    return PurePosixPath(name).suffix in {'.o', '.pyc', '.whl', '.deb', '.cpio', '.zip', '.tar', '.gz'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path, help='New ZIP path; existing files are refused')
    group.add_argument('--verify', type=Path, help='Verify a previously exported ZIP without extracting it')
    args = parser.parse_args()
    try:
        result = export(args.output) if args.output else verify(args.verify)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
