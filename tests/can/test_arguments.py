# SPDX-License-Identifier: Apache-2.0
import json
import os
import socket
import uuid
import pytest

from tests.testlab.process import ManagedProcess
from tests.testlab.receiver import target_uids

pytestmark = pytest.mark.can
ENTRYPOINTS = ['c.sender', 'cpp.sender', 'python.sender', 'c.receiver', 'cpp.receiver', 'python.receiver']


@pytest.mark.parametrize('entrypoint', ENTRYPOINTS)
@pytest.mark.parametrize('mode', ['missing', 'nonexistent'])
def test_can_argument_error(entrypoint, mode, can_programs, case_dir, can_timeout_scale):
    variant, role = entrypoint.split('.')
    argv = list(can_programs['argv' if role == 'sender' else 'receiver_argv'][variant])
    absent = None
    if mode == 'nonexistent':
        absent = 'gtl'+uuid.uuid4().hex[:10]
        with pytest.raises(OSError):
            socket.if_nametoindex(absent)
        argv.append(absent)
    evidence = {'kind': 'argument', 'scenario': 'CAN-ARG-01' if mode == 'missing' else 'CAN-ARG-02',
                'entrypoint': entrypoint, 'variant': variant, 'runner_uid': os.getuid(),
                'absent_interface': absent, 'status': 'failed',
                'timeout_scale': can_timeout_scale,
                'process_report': str(case_dir/'argument/process.json')}
    try:
        with ManagedProcess(argv, log_dir=case_dir/'argument', expected_returncodes=(1,)) as process:
            evidence['target_uids'] = target_uids(process)
            assert process.wait(3*can_timeout_scale) == 1
        assert process.record['status'] == 'passed'
        output = process.output()+process.output('stderr')
        evidence.update(returncode=process.record['returncode'], diagnostic=output.decode(errors='replace'))
        if mode == 'missing':
            assert b'Usage:' in output and b'DEVICE' in output
        else:
            assert f'Interface {absent} at index'.encode() not in output, 'Unknown interface must be rejected before index use'
            assert b'Sending:' not in output, 'Unknown interface must be rejected before transmission'
            assert b'Error getting interface index' in output or b'Error in socket bind' in output
        evidence['status'] = 'passed'
    except BaseException as exc:
        evidence['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        (case_dir/'case.json').write_text(json.dumps(evidence, indent=2)+'\n')
