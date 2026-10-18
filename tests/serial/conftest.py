# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import platform
import sys
import pytest

from tests.testlab.build import PROJECT, build_targets, default_source_root, sha256


@pytest.fixture(scope='session')
def serial_programs(request, evidence_root):
    source = (request.config.getoption('--source-root') or default_source_root()).resolve()
    report = build_targets(source_root=source, target_ids=['serial.c', 'serial.cpp'],
                           output_root=evidence_root/'builds')
    assert report['status'] == 'passed', report
    main = source/'serial/python/main.py'
    python_files = (main, main.with_name('serial_terminal.py'))
    assert all(p.is_file() for p in python_files), 'Missing Python serial sources'
    import serial
    manifest = {'source_root': str(source), 'native_build_report': report,
        'python_executable': sys.executable, 'pyserial_version': serial.VERSION,
        'python_sources': {str(p.relative_to(source)): sha256(p) for p in python_files}}
    lock = json.loads((PROJECT/'source.lock.json').read_text())
    files = sorted({p for name in ('tests/testlab', 'tests/serial')
                    for p in (PROJECT/name).glob('*.py')} |
                   {PROJECT/'tests/conftest.py', PROJECT/'tests/requirements.txt',
                    PROJECT/'tests/requirements-serial.txt', PROJECT/'source.lock.json', PROJECT/'pytest.ini'})
    manifest.update(schema_version=1, contract='serial_terminal_v1',
        environment={'python': sys.version, 'platform': platform.platform(), 'runner_uid': os.getuid(),
                     'pytest': pytest.__version__, 'timeout_scale': request.config.getoption('--timeout-scale'),
                     'capabilities': [line for line in Path('/proc/self/status').read_text().splitlines()
                                      if line.startswith(('CapEff:', 'CapBnd:', 'NoNewPrivs:', 'Seccomp:'))]},
        command=sys.orig_argv,
        upstream_reference={'repository': lock['repository'], 'revision': lock['revision'],
            'changed_files': [name for name, info in lock['files'].items()
                              if (name.startswith('serial/') or name == 'common.mk')
                              and (not (source/name).is_file() or sha256(source/name) != info['sha256'])]},
        harness_sha256={str(p.relative_to(PROJECT)): sha256(p) for p in files})
    (evidence_root/'serial-programs.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return {'c': [report['targets'][0]['binary']['path']],
            'cpp': [report['targets'][1]['binary']['path']],
            'python': [sys.executable, '-u', str(main)]}


@pytest.fixture
def serial_case_dir(case_evidence_dir):
    return case_evidence_dir


@pytest.fixture(scope='session')
def serial_timeout_scale(request):
    import math
    value = request.config.getoption('--timeout-scale')
    if not math.isfinite(value) or value <= 0:
        pytest.fail('--timeout-scale must be finite and positive')
    return value
