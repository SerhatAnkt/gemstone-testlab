# SPDX-License-Identifier: Apache-2.0
import json
import os
from contextlib import contextmanager
import pytest

from tests.testlab.contracts import CanFrame, CONTRACT, END
from tests.testlab.receiver import ReceiverSession

pytestmark = pytest.mark.can
VARIANTS = ['c', 'cpp', 'python']


@contextmanager
def receiver_case(variant, scenario, can_programs, vcan, case_dir, can_timeout_scale):
    evidence = {'contract': CONTRACT, 'kind': 'receiver', 'scenario': scenario,
                'variant': variant, 'runner_uid': os.getuid(), 'status': 'failed',
                'python_sources': can_programs['python_sources'],
                'process_report': str(case_dir/'receiver/process.json')}
    try:
        with ReceiverSession([*can_programs['receiver_argv'][variant], vcan.name], vcan.name,
                             log_dir=case_dir/'receiver', evidence=evidence, timeout_scale=can_timeout_scale) as session:
            yield session, evidence
        evidence['status'] = 'passed'
    except BaseException as exc:
        evidence['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        (case_dir/'case.json').write_text(json.dumps(evidence, indent=2)+'\n')


@pytest.mark.parametrize('payload', [b'', b'A', b'ABCDEFGH'], ids=['zero', 'one', 'eight'])
@pytest.mark.parametrize('variant', VARIANTS)
def test_receiver_classic_lengths(variant, payload, can_programs, vcan, case_dir, can_timeout_scale):
    with receiver_case(variant, 'CAN-RX-01', can_programs, vcan, case_dir, can_timeout_scale) as (session, evidence):
        frame = CanFrame(0x123, payload)
        evidence['expected'] = frame.evidence()
        session.send_and_expect(frame)
        session.finish(END)


@pytest.mark.parametrize('variant', VARIANTS)
def test_receiver_nonprintable_bytes(variant, can_programs, vcan, case_dir, can_timeout_scale):
    with receiver_case(variant, 'CAN-RX-02', can_programs, vcan, case_dir, can_timeout_scale) as (session, evidence):
        frame = CanFrame(0x123, b'\x00\x01\x1f \x7f\x80\xffA')
        evidence['expected'] = {**frame.evidence(), 'text': '... ...A'}
        output = session.send_and_expect(frame)
        assert output.text == evidence['expected']['text']
        session.finish(END)


@pytest.mark.parametrize('closing', [b'END', b'ENDtail'], ids=['exact', 'prefix'])
@pytest.mark.parametrize('variant', VARIANTS)
def test_receiver_end_condition(variant, closing, can_programs, vcan, case_dir, can_timeout_scale):
    with receiver_case(variant, 'CAN-RX-03', can_programs, vcan, case_dir, can_timeout_scale) as (session, evidence):
        invalid = (CanFrame(0x125, b'END'), CanFrame(0x124, b'EN'), CanFrame(0x124, b'ENX'))
        evidence['must_continue_after'] = [frame.evidence() for frame in invalid]
        for index, frame in enumerate(invalid):
            session.send_and_expect(frame)
            # A later frame processed by the target proves it kept running;
            # a sleep and a live PID alone would not establish this behavior.
            session.send_and_expect(CanFrame(0x123, bytes([0x41+index])))
        session.finish(CanFrame(0x124, closing))
        evidence['closing'] = CanFrame(0x124, closing).evidence()
