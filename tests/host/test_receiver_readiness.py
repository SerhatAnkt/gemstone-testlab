# SPDX-License-Identifier: Apache-2.0
"""Host-only regression for probes ending before the readiness deadline.

The publisher is simulated; the process, console PTY and its cleanup are real.
Actual SocketCAN integration remains in tests/can.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.testlab.build import PROJECT
from tests.testlab.contracts import READY, require_frame
from tests.testlab.receiver import ReceiverSession


class ReceiverReadinessTests(unittest.TestCase):
    def test_late_bind_still_receives_a_probe_before_five_second_deadline(self):
        parent = os.environ.get('TESTLAB_EVIDENCE_ROOT')
        if parent:
            Path(parent).mkdir(parents=True, exist_ok=True)
            root = Path(tempfile.mkdtemp(prefix='late-can-ready-', dir=Path(parent).resolve()))
        else:
            temporary = tempfile.TemporaryDirectory(prefix='late-can-ready-')
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name)
        evidence = {'publisher': 'simulated_late_bind', 'actual_socketcan': False}
        session = ReceiverSession([sys.executable, '-u', str(PROJECT/'tests/fixtures/process_helper.py'),
                                   'can_ready_after_trigger'], 'simulated', log_dir=root/'process', evidence=evidence)

        class LatePublisher:
            def __init__(self, interface):
                self.started = None
                self.frames = []
                self.closed = self.triggered = False

            def send(self, frame):
                require_frame(frame, READY)
                now = time.monotonic()
                if self.started is None:
                    self.started = now
                self.frames.append(frame.evidence())
                if not self.triggered and now-self.started >= 3.6:
                    session.process.send(b'G')
                    self.triggered = True

            def close(self):
                self.closed = True

        with patch('tests.testlab.receiver.CanPublisher', LatePublisher):
            with session:
                self.assertTrue(session.publisher.triggered)
                self.assertEqual(session.process.wait(1), 0)
        self.assertEqual(session.process.record['status'], 'passed')
        self.assertTrue(evidence['publisher_closed'] and evidence['pty_closed'])
        self.assertTrue(session.process.record['cleanup']['group_gone'])
        (root/'readiness.json').write_text(json.dumps(evidence, indent=2)+'\n')
