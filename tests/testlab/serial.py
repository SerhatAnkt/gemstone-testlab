# SPDX-License-Identifier: Apache-2.0
"""Independent byte endpoints and explicitly owned console/device PTYs."""
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import pty
import termios
import time
import uuid

from .process import ManagedProcess, ProcessError


def attributes(fd):
    values = termios.tcgetattr(fd)
    return values[:6]+[[value.hex() if isinstance(value, bytes) else value for value in values[6]]]


class PtyPair:
    """Do not preconfigure raw mode: the application must configure its device."""
    def __init__(self):
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.original = termios.tcgetattr(self.slave)
        self.before = attributes(self.slave)
        self.flags = fcntl.fcntl(self.master, fcntl.F_GETFL)

    def close(self):
        errors = []
        try:
            if self.slave is not None:
                termios.tcsetattr(self.slave, termios.TCSANOW, self.original)
        except OSError as exc:
            errors.append(str(exc))
        finally:
            for name in ('master', 'slave'):
                fd = getattr(self, name)
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as exc:
                        errors.append(str(exc))
                    setattr(self, name, None)
        if errors:
            raise OSError('; '.join(errors))


class SerialSession:
    def __init__(self, argv, *, log_dir, evidence, timeout_scale=1.0):
        if not math.isfinite(timeout_scale) or timeout_scale <= 0:
            raise ValueError('Timeout scale must be finite and positive')
        self.argv, self.log_dir, self.evidence = argv, Path(log_dir), evidence
        self.scale = timeout_scale
        self.process = self.device = self.console = None
        self.events = []
        self.expected_device = bytearray()
        self.started = time.monotonic()
        self.scenario_deadline = None
        self.finished = False
        self.evidence.update(timeout_scale=timeout_scale, runner_uid=os.getuid(),
            budgets_seconds={name: value*timeout_scale for name, value in
                             (('ready', 5), ('scenario', 10), ('shutdown', 3), ('cleanup', 2))})

    def event(self, action, **values):
        self.events.append({'elapsed_seconds': round(time.monotonic()-self.started, 6),
                            'action': action, **values})

    def __enter__(self):
        try:
            self.device = PtyPair()
            self.console = PtyPair()
            argv = [*self.argv, '--device', self.device.path, '--baud', '115200']
            self.evidence['devices'] = {'serial': self.device.path, 'console': self.console.path}
            self.process = ManagedProcess(argv, log_dir=self.log_dir,
                stdin=self.console.slave, stdout=self.console.slave,
                readers={'console': self.console.master, 'device': self.device.master},
                cleanup_timeout=2*self.scale)
            self.process.start()
            # Slave leases stay open solely for observing restoration after exit.
            # They are not input/output endpoints of the independent test peer.
            self.ready()
            self.scenario_deadline = time.monotonic()+10*self.scale
            return self
        except BaseException as exc:
            self.__exit__(type(exc), exc, exc.__traceback__)
            raise

    def ready(self):
        deadline = time.monotonic()+5*self.scale
        while True:
            states = [termios.tcgetattr(pair.slave) for pair in (self.device, self.console)]
            if all(not (state[3] & (termios.ECHO | termios.ICANON | termios.ISIG)) for state in states):
                break
            if self.process.service_io(min(0.02, max(0, deadline-time.monotonic()))) is not None:
                raise ProcessError('Serial application exited before configuring its terminals')
            if time.monotonic() >= deadline:
                raise TimeoutError('Serial terminal configuration exceeded the readiness deadline')
        nonce = ('GTL_READY_'+uuid.uuid4().hex).encode()
        self.process.send(nonce, fd=self.device.master, timeout=max(0.001, deadline-time.monotonic()))
        observed = self.process.expect(nonce, channel='console', phase='ready',
                                       timeout=max(0.001, deadline-time.monotonic()))
        prefix = observed[:-len(nonce)]
        assert b'Serial terminal started. Press Ctrl+C to exit.' in prefix, prefix
        self.evidence['readiness'] = {'method': 'single independent device-to-console nonce',
            'attempts': 1, 'sent_hex': nonce.hex(), 'received_hex': observed[-len(nonce):].hex(),
            'startup_hex': prefix.hex(), 'device_attributes': attributes(self.device.slave),
            'console_attributes': attributes(self.console.slave)}
        self.event('ready', data_hex=nonce.hex())

    def transfer(self, direction, data):
        if direction not in ('rx', 'tx') or not data:
            raise ValueError('Transfer requires rx/tx and nonempty bytes')
        remaining = self.scenario_deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Serial scenario deadline expired')
        fd = self.device.master if direction == 'rx' else self.console.master
        channel = 'console' if direction == 'rx' else 'device'
        self.event('send', direction=direction, data_hex=data.hex())
        self.process.send(data, fd=fd, timeout=remaining)
        actual = self.process.read_exact(len(data), channel=channel,
            timeout=max(0.001, self.scenario_deadline-time.monotonic()))
        self.event('receive', direction=direction, expected_hex=data.hex(), actual_hex=actual.hex())
        assert actual == data, f'{direction} byte mismatch: expected {data.hex()}, got {actual.hex()}'
        if direction == 'tx':
            self.expected_device.extend(data)
        return actual

    def finish(self):
        self.event('console_ctrl_c', data_hex='03')
        self.process.send(b'\x03', fd=self.console.master, timeout=3*self.scale)
        assert self.process.wait(3*self.scale, phase='shutdown') == 0, 'Ctrl+C must exit successfully'
        self.finished = True

    def __exit__(self, exc_type, exc, traceback):
        errors = []
        try:
            if self.process is not None and not self.process.closed:
                self.process.__exit__(exc_type, exc, traceback)
        except BaseException as error:
            errors.append(str(error))
        finally:
            for name in ('console', 'device'):
                pair = getattr(self, name)
                if pair is None:
                    continue
                try:
                    after = attributes(pair.slave)
                    self.evidence[name+'_attributes'] = {'before': pair.before, 'after_target': after,
                        'restored_by_target': pair.before == after}
                    self.evidence[name+'_fd_flags_restored'] = (
                        fcntl.fcntl(pair.master, fcntl.F_GETFL) == pair.flags)
                except BaseException as error:
                    errors.append(str(error))
                try:
                    pair.close()
                except BaseException as error:
                    errors.append(str(error))
            self.evidence['pty_fds_closed'] = all(pair is None or pair.master is None and pair.slave is None
                                                for pair in (self.console, self.device))
            self.evidence['ctrl_c_completed'] = self.finished
            self.evidence['cleanup_errors'] = errors
            self.log_dir.mkdir(parents=True, exist_ok=True)
        validated = False
        try:
            if exc is None:
                assert not errors, errors
                assert self.process.record['status'] == 'passed', self.process.record
                assert self.finished, 'Scenario must complete the console Ctrl+C shutdown'
                assert self.evidence['console_attributes']['restored_by_target'], 'Console termios was not restored'
                assert self.evidence['console_fd_flags_restored'] and self.evidence['device_fd_flags_restored']
                assert self.process.output('device') == bytes(self.expected_device), 'Unexpected serial-side bytes'
                # Only the Python destructor emits a normal-shutdown message.
                assert not self.process.output('stderr'), self.process.output('stderr')
                trailing = self.process.output('console')[self.process.channels['console']['cursor']:]
                assert trailing in (b'', b'\nShutting down...\n', b'\r\nShutting down...\r\n'), trailing
            validated = exc is None
        finally:
            report = {**self.evidence, 'status': 'passed' if validated else 'failed',
                      'process_status': self.process.record['status'] if self.process else 'not_started'}
            (self.log_dir/'serial.json').write_text(json.dumps(report, indent=2)+'\n')
            (self.log_dir/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in self.events))
        return False


@contextmanager
def serial_case(path, **metadata):
    evidence = {'schema_version': 1, 'status': 'failed', **metadata}
    try:
        yield evidence
        evidence['status'] = 'passed'
    except BaseException as exc:
        evidence['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        (path/'failure.json').write_text(json.dumps(evidence, indent=2)+'\n')
        raise
    finally:
        (path/'case.json').write_text(json.dumps(evidence, indent=2)+'\n')
