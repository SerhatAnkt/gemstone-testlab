# SPDX-License-Identifier: Apache-2.0
"""Bounded receiver readiness and output parsing over a real PTY console."""
import os
import math
from pathlib import Path
import pty
import time
import tty

from .can import CanPublisher
from .contracts import READY, parse_receiver_line, require_frame
from .process import ManagedProcess, ProcessError


def target_uids(process):
    status = Path(f"/proc/{process.record['procfs_pgid']}/status").read_text()
    line = next(line for line in status.splitlines() if line.startswith('Uid:'))
    uids = [int(value) for value in line.split()[1:]]
    if uids != [os.getuid()]*4:
        raise AssertionError(f"Target privilege changed: {uids}")
    return uids


class ReceiverSession:
    def __init__(self, argv, interface, *, log_dir, evidence, timeout_scale=1.0):
        if not math.isfinite(timeout_scale) or timeout_scale <= 0:
            raise ValueError('Timeout scale must be finite and positive')
        self.argv, self.interface = argv, interface
        self.log_dir, self.evidence = log_dir, evidence
        self.scale = timeout_scale
        self.evidence['timeout_scale'] = timeout_scale
        self.process = self.publisher = None
        self.master = self.slave = None
        self.cursor = 0
        self.received = []

    def __enter__(self):
        try:
            self.master, self.slave = pty.openpty()
            tty.setraw(self.slave)
            self.publisher = CanPublisher(self.interface)
            self.process = ManagedProcess(self.argv, log_dir=self.log_dir,
                stdout=self.slave, readers={'console': self.master})
            self.process.start()
            os.close(self.slave)
            self.slave = None
            self.evidence['target_uids'] = target_uids(self.process)
            self.ready()
            return self
        except BaseException as exc:
            self.__exit__(type(exc), exc, exc.__traceback__)
            raise

    def _next_output(self):
        data = self.process.output('console')
        while True:
            end = data.find(b'\n', self.cursor)
            if end < 0:
                return None
            line = data[self.cursor:end]
            self.cursor = end+1
            output = parse_receiver_line(line)
            if output is not None:
                self.received.append(output.evidence())
                return output

    def ready(self, timeout=None):
        timeout = 5*self.scale if timeout is None else timeout
        deadline = time.monotonic()+timeout
        attempts = 0
        next_send = 0
        frame_output_started = False
        while time.monotonic() < deadline:
            now = time.monotonic()
            # Bounded retries handle the race between process start and bind.
            # Once a frame line starts arriving, the receiver has bound. Do not
            # fill its queue with probes while Python prints a line in pieces.
            if not frame_output_started and now >= next_send and attempts < math.ceil(timeout/0.1):
                self.publisher.send(READY)
                attempts += 1
                next_send = now+0.1
            self.process.service_io(min(0.05, max(0, deadline-time.monotonic())))
            frame_output_started = b'Received:' in self.process.output('console')
            output = self._next_output()
            if output is not None:
                require_frame(output.frame, READY)
                self.evidence['readiness'] = {'attempts': attempts, 'frame': output.evidence()}
                return
            if self.process.process.poll() is not None:
                raise ProcessError("Receiver exited before the independent readiness probe")
        raise TimeoutError("Receiver did not echo the readiness CAN frame within the deadline")

    def expect(self, expected, timeout=None):
        timeout = 3*self.scale if timeout is None else timeout
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            self.process.service_io(min(0.05, max(0, deadline-time.monotonic())))
            output = self._next_output()
            if output is not None:
                # Only readiness traffic may repeat; real test frames are not retried.
                if output.frame == READY:
                    continue
                require_frame(output.frame, expected)
                return output
            if self.process.channels['console']['eof']:
                raise ProcessError("Receiver exited before the expected frame output")
        raise TimeoutError(f"Receiver did not print the expected frame: {expected.evidence()}")

    def send_and_expect(self, frame):
        self.publisher.send(frame)
        return self.expect(frame)

    def finish(self, frame):
        self.send_and_expect(frame)
        self.process.expect(b'Received END message, stopping receiver', channel='console', timeout=3*self.scale, phase='shutdown')
        if self.process.wait(3*self.scale, phase='shutdown') != 0:
            raise AssertionError('Receiver did not exit normally')

    def __exit__(self, exc_type, exc, traceback):
        try:
            if self.process is not None and not self.process.closed:
                self.process.__exit__(exc_type, exc, traceback)
        finally:
            if self.publisher is not None:
                self.publisher.close()
            for name in ('master', 'slave'):
                descriptor = getattr(self, name)
                if descriptor is not None:
                    os.close(descriptor)
                    setattr(self, name, None)
            self.evidence.update(received=self.received,
                sent=self.publisher.frames if self.publisher else [],
                publisher_closed=self.publisher.closed if self.publisher else True,
                pty_closed=self.master is None and self.slave is None)
        if exc is None and self.process is not None and self.process.record['status'] != 'passed':
            raise AssertionError(self.process.record)
        return False
