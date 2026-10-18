# SPDX-License-Identifier: Apache-2.0
import os
import pytest

from tests.testlab.serial import SerialSession, serial_case

pytestmark = pytest.mark.serial
VARIANTS = ['c', 'cpp', 'python']
RX = [pytest.param(b'Gemstone RX 0123456789\n', id='text'),
      pytest.param(b'RX\x00\x7f\x80\xff\r\n\rEND', id='binary-crlf')]
TX = [pytest.param(b'Gemstone TX 0123456789\n', id='text-burst'),
      pytest.param(b'TX\x00\x7f\x80\xff\r\nEND', id='binary-burst')]


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('payload', RX)
def test_serial_receive(variant, payload, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='SER-RX-01', variant=variant, payload_hex=payload.hex()) as case:
        with SerialSession(serial_programs[variant], log_dir=serial_case_dir/'terminal',
                           evidence=case, timeout_scale=serial_timeout_scale) as session:
            session.transfer('rx', payload)
            session.finish()


@pytest.mark.parametrize('variant', VARIANTS)
@pytest.mark.parametrize('payload', TX)
def test_serial_transmit(variant, payload, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='SER-TX-01', variant=variant, payload_hex=payload.hex()) as case:
        with SerialSession(serial_programs[variant], log_dir=serial_case_dir/'terminal',
                           evidence=case, timeout_scale=serial_timeout_scale) as session:
            session.transfer('tx', payload)
            session.finish()


@pytest.mark.parametrize('variant', VARIANTS)
def test_serial_fragmented_duplex(variant, serial_programs, serial_case_dir, serial_timeout_scale):
    # Each fragment is acknowledged by observing its exact bytes, without sleeps.
    # The 257-byte piece also crosses the native application's 255-byte buffer.
    rx = [b'A', b'BC\x00', bytes(range(16, 32)), b'R'*257, b'\r\nZ']
    tx = [b'1', b'23\x00', b'\x7f\x80\xff', b'T'*257, b'\r\n9']
    with serial_case(serial_case_dir, scenario='SER-IO-01', variant=variant,
                     rx_chunks=[p.hex() for p in rx], tx_chunks=[p.hex() for p in tx]) as case:
        with SerialSession(serial_programs[variant], log_dir=serial_case_dir/'terminal',
                           evidence=case, timeout_scale=serial_timeout_scale) as session:
            for incoming, outgoing in zip(rx, tx):
                session.transfer('rx', incoming)
                session.transfer('tx', outgoing)
            session.finish()


@pytest.mark.parametrize('variant', VARIANTS)
def test_serial_console_ctrl_c(variant, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='SER-LIFE-01', variant=variant) as case:
        with SerialSession(serial_programs[variant], log_dir=serial_case_dir/'terminal',
                           evidence=case, timeout_scale=serial_timeout_scale) as session:
            session.finish()
        assert session.process.record['cleanup']['leader_reaped']
        assert session.process.record['cleanup']['group_gone']
        assert not [e for e in session.process.record['events'] if e['action'] == 'signal']
        assert case['console_attributes']['restored_by_target']


@pytest.mark.parametrize('variant', VARIANTS)
def test_serial_failure_closes_owned_resources(variant, serial_programs, serial_case_dir, serial_timeout_scale):
    with serial_case(serial_case_dir, scenario='HARNESS-02-serial', variant=variant) as case:
        before = set(os.listdir('/proc/self/fd'))
        # This unrelated descriptor must survive the session's forced cleanup.
        with (serial_case_dir/'unrelated.log').open('wb', buffering=0) as external:
            with pytest.raises(ValueError, match='controlled serial scenario failure'):
                with SerialSession(serial_programs[variant], log_dir=serial_case_dir/'terminal',
                                   evidence=case, timeout_scale=serial_timeout_scale) as session:
                    raise ValueError('controlled serial scenario failure')
            external.write(b'external descriptor preserved\n')
            assert session.process.record['status'] == 'failed'
            assert session.process.record['failure']['reason'] == 'context_exception'
            assert session.process.record['cleanup']['leader_reaped']
            assert session.process.record['cleanup']['group_gone']
            assert case['pty_fds_closed'] and not case['cleanup_errors']
            assert case['console_fd_flags_restored'] and case['device_fd_flags_restored']
        assert set(os.listdir('/proc/self/fd')) == before
