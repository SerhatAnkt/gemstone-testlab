# SPDX-License-Identifier: Apache-2.0
"""Small, versioned input manifests and result helpers; no pytest dependency."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import uuid

from .build import PROJECT

SCHEMA = 1
SOURCE_LIMIT = 2*1024*1024
SUFFIXES = {'.c', '.cpp', '.h', '.hpp', '.py', '.mk'}
PACKAGES = ('pytest', 'pluggy', 'iniconfig', 'packaging', 'Pygments')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n')
    temporary.replace(path)


def run_directory(parent):
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:10]
    path = Path(parent).resolve()/name
    path.mkdir(parents=True, exist_ok=False)
    return path


def safe_relative(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or '\x00' in name:
        raise ValueError('Invalid relative input path')
    return Path(*path.parts)


def inside(root, name):
    path = root/safe_relative(name)
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError('Input path escapes its root')
    return path


def suite_of(nodeid):
    return next((name for name in ('can', 'serial') if nodeid.startswith('tests/'+name+'/')), 'host')


def source_names(root, suites):
    lock = json.loads((PROJECT/'source.lock.json').read_text())
    scopes = {'canbus' if name == 'can' else 'serial' for name in suites if name in ('can', 'serial')}
    if 'host' in suites or not scopes:
        scopes = {'canbus', 'serial'}
    names = {'common.mk'}
    names.update(name for name in lock['files'] if name.split('/')[0] in scopes)
    for scope in sorted(scopes):
        directory = root/scope
        if directory.is_symlink():
            raise ValueError('Source scope must not be a symlink')
        for path in directory.rglob('*'):
            if path.is_file() and (path.name == 'Makefile' or path.suffix in SUFFIXES):
                names.add(path.relative_to(root).as_posix())
    names.update(p.name for p in root.glob('*.mk') if p.is_file())
    return sorted(names)


def source_manifest(root, suites, destination=None):
    root = Path(root).resolve()
    entries, size = [], 0
    names = source_names(root, suites)
    if len(names) > 512:
        raise ValueError('Source snapshot exceeds 512 files')
    for name in names:
        path = inside(root, name)
        item = {'path': name, 'sha256': None, 'size_bytes': None}
        if path.is_file():
            size += path.stat().st_size
            if size > SOURCE_LIMIT:
                raise ValueError('Source snapshot exceeds 2 MiB')
            data = path.read_bytes()
            item.update(sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data))
            if destination is not None:
                output = inside(destination, name)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(data)
        entries.append(item)
    content = {'suites': sorted(suites), 'files': entries}
    return {**content, 'digest': digest_json(content)}


def harness_manifest():
    paths = [p for p in (PROJECT/'tests').rglob('*') if p.is_file() and
             not set(p.relative_to(PROJECT).parts) & {'__pycache__', '.pytest_cache'} and
             p.suffix in {'.py', '.json', '.txt', '.sh'}]
    paths += [PROJECT/'pytest.ini', PROJECT/'source.lock.json']
    entries = [{'path': p.relative_to(PROJECT).as_posix(), 'sha256': sha256(p)} for p in sorted(paths)]
    return {'files': entries, 'digest': digest_json(entries)}


def dependency_versions(suites):
    names = [*PACKAGES, *(['pyserial'] if 'serial' in suites else [])]
    result = {}
    for name in names:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def environment(suites):
    return {'python': platform.python_version(), 'python_compatibility': list(os.sys.version_info[:2]),
            'system': platform.system(), 'machine': platform.machine(), 'kernel': platform.release(),
            'runner_uid': os.getuid(), 'dependencies': dependency_versions(suites)}


def case_id(nodeid):
    label = re.sub(r'[^A-Za-z0-9_.-]+', '-', nodeid.rsplit('::', 1)[-1])[:64]
    return label+'-'+hashlib.sha256(nodeid.encode()).hexdigest()[:12]


def outcome(phases):
    # A teardown/setup failure dominates a passed or failed call.
    if any(p['outcome'] == 'failed' and (p['phase'] != 'call' or
           p.get('error_type') in {'CleanupError', 'ProcessStartError'}) for p in phases):
        return 'error'
    if any(p['outcome'] == 'failed' for p in phases):
        return 'failed'
    if any(p['outcome'] == 'skipped' for p in phases):
        return 'skipped'
    return 'passed' if any(p['phase'] == 'call' and p['outcome'] == 'passed' for p in phases) else 'not_run'


def oracle(case_dir):
    path = case_dir/'evidence/case.json'
    if not path.is_file():
        return None, None
    value = json.loads(path.read_text())
    expected = {k: value[k] for k in ('expected', 'expected_first', 'expected_end', 'payload_hex',
                                    'rx_chunks', 'tx_chunks', 'closing', 'must_continue_after') if k in value}
    actual = {k: value[k] for k in ('frames', 'received', 'returncode', 'diagnostic', 'error',
                                   'ctrl_c_completed', 'pty_fds_closed', 'cleanup_errors') if k in value}
    events = case_dir/'evidence/terminal/events.jsonl'
    if events.is_file():
        actual['transfers'] = [json.loads(line) for line in events.read_text().splitlines()
                               if json.loads(line).get('action') == 'receive']
    device = case_dir/'evidence/terminal/device.log'
    if device.is_file() and value.get('error'):
        data = device.read_bytes()
        actual.update(device_output_hex=data[:4096].hex(), device_output_truncated=len(data)>4096)
    return expected or None, actual or None


def inventory(root, directory):
    result = []
    for path in sorted(directory.rglob('*')):
        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()):
            result.append({'path': path.relative_to(root).as_posix(),
                           'sha256': sha256(path), 'size_bytes': path.stat().st_size})
    return result


def command_records(root):
    result = []
    for path in sorted(root.rglob('process.json')):
        if path.is_symlink():
            continue
        record = json.loads(path.read_text())
        result.append({key: record.get(key) for key in
            ('argv', 'cwd', 'started_at', 'finished_at', 'returncode', 'signal', 'status', 'timed_out', 'cleanup')})
        result[-1]['artifact'] = path.relative_to(root).as_posix()
    return result
