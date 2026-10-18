# SPDX-License-Identifier: Apache-2.0
import uuid
import pytest

from tests.testlab.process import ManagedProcess
from tests.testlab.serial import PtyPair, serial_case

pytestmark = pytest.mark.serial
VARIANTS = ['c', 'cpp', 'python']


def run_cli(argv, case_dir, scale, expected):
    with ManagedProcess(argv, log_dir=case_dir/'argument', expected_returncodes=expected) as process:
        process.close_input()
        code = process.wait(3*scale)
    return code, process.output()+process.output('stderr'), process


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('baud', ['0', 'garbage', '12345', '9600oops'])
def test_serial_bad_baud(variant, baud, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='SER-ARG-01', variant=variant, baud=baud) as case:
        pair = PtyPair()
        try:
            argv = [*serial_programs[variant], '--device', pair.path, '--baud', baud]
            code, output, process = run_cli(argv, serial_case_dir, serial_timeout_scale, (1, 2))
            case.update(returncode=code, diagnostic=output.decode(errors='replace'))
            assert code in (1, 2), output
            assert b'Serial terminal started.' not in output, 'Invalid baud must be rejected before opening a terminal'
            assert b'baud' in output.lower() or b'invalid int value' in output.lower(), output
            assert process.record['status'] == 'passed'
        finally:
            pair.close()


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('mode', ['missing', 'nonexistent'])
def test_serial_argument_errors(variant, mode, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='SER-ARG-02' if mode == 'nonexistent' else 'SER-ARG-missing',
                     variant=variant) as case:
        argv = list(serial_programs[variant])
        if mode == 'nonexistent':
            absent = serial_case_dir/('absent-'+uuid.uuid4().hex)
            assert not absent.exists()
            argv += ['--device', str(absent), '--baud', '115200']
        code, output, process = run_cli(argv, serial_case_dir, serial_timeout_scale, (1, 2))
        case.update(returncode=code, diagnostic=output.decode(errors='replace'))
        assert code in (1, 2), output
        if mode == 'missing':
            assert b'usage:' in output.lower() and b'device' in output.lower(), output
        else:
            assert b'Error opening serial port' in output, output
            assert not absent.exists()
        assert process.record['status'] == 'passed'


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('flag', ['-h', '--help'])
def test_serial_help(variant, flag, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='CLI-HELP-01', variant=variant, flag=flag) as case:
        code, output, process = run_cli([*serial_programs[variant], flag], serial_case_dir, serial_timeout_scale, (0,))
        case.update(returncode=code, diagnostic=output.decode(errors='replace'))
        assert code == 0, 'Help is a successful CLI operation'
        assert b'usage:' in output.lower() and b'--device' in output and b'--baud' in output
        assert process.record['status'] == 'passed'
