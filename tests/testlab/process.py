# SPDX-License-Identifier: Apache-2.0
"""Linux process groups, bounded binary I/O and observable resource cleanup.

No shell, background reader threads or global waitpid(-1). Borrowed descriptors
remain owned by the fixture. Children that deliberately leave their session are
outside this module's process-group contract.
"""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import errno
import fcntl
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import threading
import time


class ProcessError(RuntimeError):
    pass


class ProcessTimeout(ProcessError):
    pass


class ProcessStartError(ProcessError):
    pass


class OutputLimitExceeded(ProcessError):
    pass


class CleanupError(ProcessError):
    pass


_reaper_lock = threading.RLock()
_reaper_users = 0
_reaper_previous = 0


def _prctl(option, value):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(option, value, 0, 0, 0) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))


def subreaper_state():
    state = ctypes.c_int()
    _prctl(37, ctypes.byref(state))  # PR_GET_CHILD_SUBREAPER
    return state.value


def _acquire_reaper():
    global _reaper_users, _reaper_previous
    with _reaper_lock:
        if _reaper_users == 0:
            _reaper_previous = subreaper_state()
            _prctl(36, 1)  # PR_SET_CHILD_SUBREAPER, unprivileged Linux API
        _reaper_users += 1


def _release_reaper():
    global _reaper_users
    with _reaper_lock:
        _reaper_users -= 1
        if _reaper_users == 0:
            _prctl(36, _reaper_previous)
        return {"active_leases": _reaper_users, "state": subreaper_state(),
                "previous_state": _reaper_previous}


def _namespace_index():
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("NSpid:"):
            return len(line.split()[1:])-1
    raise ProcessError("Linux procfs NSpid metadata is required")


def _proc_fields(entry):
    data = (entry / "stat").read_text()
    return data[data.rfind(")")+2:].split()


def _namespace_pid(entry, index):
    for line in (entry / "status").read_text().splitlines():
        if line.startswith("NSpid:"):
            values = line.split()[1:]
            return int(values[index]) if len(values) > index else None
    return None


def _procfs_group(child_pid):
    # /proc may be mounted from an ancestor PID namespace. Popen/kill/wait use
    # caller-namespace PIDs, whereas stat uses the procfs mount's namespace.
    parent = int(Path("/proc/self/stat").read_text().split(" ", 1)[0])
    index = _namespace_index()
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                fields = _proc_fields(entry)
                if int(fields[1]) == parent and _namespace_pid(entry, index) == child_pid:
                    return int(fields[2])
            except (FileNotFoundError, ProcessLookupError):
                pass
    raise ProcessError("Could not map the child process group into procfs")


def group_members(procfs_pgid):
    """Inspect the cached procfs group id; include zombies and translate PIDs."""
    members = []
    if procfs_pgid is None:
        return members
    parent = int(Path("/proc/self/stat").read_text().split(" ", 1)[0])
    index = _namespace_index()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = _proc_fields(entry)
            if int(fields[2]) == procfs_pgid:
                members.append({"pid": _namespace_pid(entry, index),
                                "procfs_pid": int(entry.name),
                                "parent_is_testlab": int(fields[1]) == parent,
                                "state": fields[0]})
        except (FileNotFoundError, ProcessLookupError):
            continue
    return members


def _seconds(value):
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Timeouts must be finite positive seconds")
    return value


def _utc():
    return datetime.now(timezone.utc).isoformat()


class ManagedProcess:
    def __init__(self, argv, *, log_dir, cwd=None, env=None, stdin=subprocess.PIPE,
                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, readers=None,
                 expected_returncodes=(0,), max_output_bytes=1024*1024,
                 terminate_grace=1.0, cleanup_timeout=2.0):
        if not isinstance(argv, (list, tuple)) or not argv or not all(isinstance(a, str) for a in argv):
            raise ValueError("argv must be a nonempty list of strings")
        if not expected_returncodes or max_output_bytes < 1:
            raise ValueError("Expected exit codes and a positive output budget are required")
        self.argv, self.cwd, self.env = list(argv), cwd, env
        self.stdio = (stdin, stdout, stderr)
        self.readers = dict(readers or {})
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name) for name in self.readers):
            raise ValueError("Invalid capture channel name")
        if set(self.readers) & {"stdout", "stderr"}:
            raise ValueError("stdout/stderr are reserved capture names")
        self.expected = tuple(expected_returncodes)
        self.limit = max_output_bytes
        self.grace = _seconds(terminate_grace)
        self.cleanup_timeout = _seconds(cleanup_timeout)
        self.log_dir = Path(log_dir).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=False)
        self.selector = selectors.DefaultSelector()
        self.process = None
        self.pgid = None
        self.procfs_pgid = None
        self.channels = {}
        self.borrowed_flags = {}
        self.owned_streams = []
        self.failure = None
        self.closed = False
        self.reaper_lease = False
        self.started = time.monotonic()
        self.record = {"schema_version": 1, "argv": self.argv,
                       "cwd": str(Path(cwd or Path.cwd()).resolve()),
                       "started_at": _utc(), "status": "running", "pid": None,
                       "pgid": None, "returncode": None, "signal": None,
                       "expected_returncodes": list(self.expected), "timed_out": False,
                       "events": [], "channels": {}, "cleanup": {}}

    def _fail(self, reason, **details):
        if self.failure is None:
            self.failure = {"reason": reason, **details}

    def _event(self, action, **values):
        self.record["events"].append({"action": action,
            "elapsed_seconds": round(time.monotonic()-self.started, 6), **values})

    def _nonblocking(self, fd, borrowed=False):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if borrowed and fd not in self.borrowed_flags:
            self.borrowed_flags[fd] = flags
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _capture(self, name, fd, borrowed=False):
        self._nonblocking(fd, borrowed)
        self.channels[name] = {"fd": fd, "buffer": bytearray(), "cursor": 0,
            "bytes_seen": 0, "eof": False, "borrowed": borrowed,
            "file": (self.log_dir / f"{name}.log").open("wb", buffering=0)}
        self.selector.register(fd, selectors.EVENT_READ, name)

    def start(self):
        if self.process is not None or self.closed:
            raise ProcessError("Process already started or closed")
        try:
            _acquire_reaper()
            self.reaper_lease = True
            self.process = subprocess.Popen(self.argv, cwd=self.cwd, env=self.env,
                stdin=self.stdio[0], stdout=self.stdio[1], stderr=self.stdio[2],
                start_new_session=True, close_fds=True, bufsize=0)
            self.pgid = self.process.pid
            self.procfs_pgid = _procfs_group(self.process.pid)
            self.record.update(pid=self.process.pid, pgid=self.pgid, procfs_pgid=self.procfs_pgid)
            for name in ("stdin", "stdout", "stderr"):
                stream = getattr(self.process, name)
                if stream is not None:
                    self.owned_streams.append(stream)
                    self._nonblocking(stream.fileno())
                    if name != "stdin":
                        self._capture(name, stream.fileno())
            for name, fd in self.readers.items():
                self._capture(name, fd, borrowed=True)
            self._event("spawn")
            return self
        except Exception as exc:
            self._fail("start_error", error=str(exc))
            self.close()
            raise ProcessStartError(str(exc)) from exc

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, traceback):
        if exc is not None and self.failure is None:
            self._fail("context_exception", error_type=exc_type.__name__, error=str(exc))
        self.close()
        return False

    def _pump(self, timeout):
        for key, mask in self.selector.select(max(0, timeout)):
            if not mask & selectors.EVENT_READ:
                continue
            channel = self.channels[key.data]
            try:
                chunk = os.read(key.fd, 32768)
            except BlockingIOError:
                continue
            except OSError as exc:
                if exc.errno != errno.EIO or not channel["borrowed"]:
                    raise
                chunk = b""  # PTY master reports EIO when its slave disappears.
            if not chunk:
                channel["eof"] = True
                self.selector.unregister(key.fd)
                continue
            channel["bytes_seen"] += len(chunk)
            room = max(0, self.limit-len(channel["buffer"]))
            kept = chunk[:room]
            channel["buffer"].extend(kept)
            channel["file"].write(kept)
            if len(kept) != len(chunk):
                self._fail("output_limit", channel=key.data, max_bytes=self.limit)

    def _check_output(self):
        if self.failure and self.failure["reason"] == "output_limit":
            raise OutputLimitExceeded(str(self.failure))

    def _timeout(self, phase):
        self.record["timed_out"] = True
        self._fail("timeout", phase=phase)
        raise ProcessTimeout(f"{phase} deadline expired for {self.argv[0]}")

    def output(self, channel="stdout"):
        return bytes(self.channels[channel]["buffer"])

    def service_io(self, timeout=0.0):
        """Drain output while a scenario waits on an independent device/socket."""
        if not math.isfinite(timeout) or timeout < 0:
            raise ValueError("I/O service timeout must be finite and nonnegative")
        self._pump(timeout)
        self._check_output()
        return self.process.poll()

    def expect(self, data, *, channel="stdout", timeout=5.0, phase="ready"):
        if not data:
            raise ValueError("Expected marker must be nonempty")
        deadline = time.monotonic() + _seconds(timeout)
        stream = self.channels[channel]
        while True:
            self._check_output()
            index = stream["buffer"].find(data, stream["cursor"])
            if index >= 0:
                end = index+len(data)
                result = bytes(stream["buffer"][stream["cursor"]:end])
                stream["cursor"] = end
                self._event("marker_observed", channel=channel, data_hex=data.hex())
                return result
            if stream["eof"]:
                self._fail("unexpected_eof", channel=channel)
                raise ProcessError(f"{channel} closed before marker {data!r}")
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                self._timeout(phase)
            self._pump(min(remaining, 0.05))

    def read_exact(self, size, *, channel="stdout", timeout=5.0):
        if size < 0:
            raise ValueError("Read size must be nonnegative")
        deadline = time.monotonic() + _seconds(timeout)
        stream = self.channels[channel]
        while len(stream["buffer"])-stream["cursor"] < size:
            self._check_output()
            if stream["eof"]:
                self._fail("unexpected_eof", channel=channel)
                raise ProcessError(f"{channel} closed during exact read")
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                self._timeout("read")
            self._pump(min(remaining, 0.05))
        self._check_output()
        start = stream["cursor"]
        stream["cursor"] += size
        return bytes(stream["buffer"][start:stream["cursor"]])

    def send(self, data, *, timeout=5.0, fd=None):
        if fd is None:
            if self.process.stdin is None:
                raise ProcessError("No managed stdin pipe; specify a borrowed peer fd")
            fd = self.process.stdin.fileno()
        elif fd not in self.readers.values():
            raise ValueError("Explicit write fd must be a registered borrowed peer")
        deadline = time.monotonic() + _seconds(timeout)
        try:
            prior = self.selector.get_key(fd)
            self.selector.modify(fd, prior.events | selectors.EVENT_WRITE, prior.data)
        except KeyError:
            prior = None
            self.selector.register(fd, selectors.EVENT_WRITE, "_write")
        view = memoryview(data)
        try:
            while view:
                self._check_output()
                if time.monotonic() >= deadline:
                    self._timeout("write")
                try:
                    count = os.write(fd, view)
                    view = view[count:]
                except BlockingIOError:
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        self._timeout("write")
                    self._pump(min(remaining, 0.05))
                except BrokenPipeError as exc:
                    self._fail("stdin_closed")
                    raise ProcessError("Child closed its input") from exc
            self._event("input_sent", bytes=len(data))
        finally:
            try:
                if prior:
                    self.selector.modify(fd, prior.events, prior.data)
                else:
                    self.selector.unregister(fd)
            except KeyError:
                pass

    def close_input(self):
        if self.process.stdin is not None:
            self.process.stdin.close()

    def signal(self, signum):
        try:
            os.killpg(self.pgid, signum)
            self._event("signal", signal=int(signum))
        except ProcessLookupError:
            self._event("signal_group_already_gone", signal=int(signum))

    def wait(self, timeout=10.0, *, phase="run"):
        deadline = time.monotonic() + _seconds(timeout)
        while self.process.poll() is None:
            self._check_output()
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                self._timeout(phase)
            self._pump(min(remaining, 0.05))
        self._pump(0)
        self._check_output()
        return self.process.returncode

    def shutdown(self, signum=None, timeout=3.0):
        self.signal(signal.SIGTERM if signum is None else signum)
        return self.wait(timeout, phase="shutdown")

    def _reap_adopted(self):
        reaped = self.record["cleanup"].setdefault("adopted_children_reaped", [])
        self.process.poll()  # Popen alone owns the direct child's wait status.
        for member in group_members(self.procfs_pgid):
            if member["pid"] != self.process.pid and member["parent_is_testlab"]:
                try:
                    pid, status = os.waitpid(member["pid"], os.WNOHANG)
                    if pid:
                        reaped.append({"pid": pid, "returncode": os.waitstatus_to_exitcode(status)})
                except ChildProcessError:
                    pass

    def _drain_until(self, deadline):
        while time.monotonic() < deadline:
            before = sum(c["bytes_seen"] for c in self.channels.values())
            self._pump(min(0.02, deadline-time.monotonic()))
            self._reap_adopted()
            if self.process.poll() is not None and not group_members(self.procfs_pgid) and all(c["eof"] or c["borrowed"]
                                                   for c in self.channels.values()) and before == sum(
                                                       c["bytes_seen"] for c in self.channels.values()):
                return

    def close(self):
        if self.closed:
            return self.record
        errors = []
        try:
            if self.process is not None:
                self.process.poll()
                if self.process.poll() is None or group_members(self.procfs_pgid):
                    if self.failure is None:
                        self._fail("process_still_running_at_cleanup")
                    self.signal(signal.SIGTERM)
                    self._drain_until(time.monotonic()+self.grace)
                if self.procfs_pgid is None or self.process.poll() is None or group_members(self.procfs_pgid):
                    self.signal(signal.SIGKILL)
                self._drain_until(time.monotonic()+self.cleanup_timeout)
                self.process.poll()
                remaining = group_members(self.procfs_pgid)
                self.record.update(returncode=self.process.returncode,
                    signal=-self.process.returncode if self.process.returncode is not None
                           and self.process.returncode < 0 else None)
                self.record["cleanup"].update(leader_reaped=self.process.returncode is not None,
                                              group_gone=not remaining, remaining_members=remaining)
                if remaining or self.process.returncode is None:
                    errors.append("Process group could not be completely collected")
                if self.procfs_pgid is None:
                    self.record["cleanup"]["group_gone"] = False
                    errors.append("Process group inspection was unavailable")
            else:
                self.record["cleanup"].update(leader_reaped=True, group_gone=True, remaining_members=[])
        except Exception as exc:
            errors.append(str(exc))
            # I/O failure must not prevent process cleanup. Fall back to killing
            # the owned group and reaping it without touching the broken reader.
            if self.process is not None:
                try:
                    self.signal(signal.SIGKILL)
                    deadline = time.monotonic()+self.cleanup_timeout
                    while time.monotonic() < deadline:
                        self._reap_adopted()
                        if self.process.poll() is not None and not group_members(self.procfs_pgid):
                            break
                        time.sleep(0.01)
                    remaining = group_members(self.procfs_pgid)
                    code = self.process.poll()
                    self.record.update(returncode=code, signal=-code if code is not None and code < 0 else None,
                                       capture_interrupted=True)
                    self.record["cleanup"].update(leader_reaped=code is not None,
                                                  group_gone=self.procfs_pgid is not None and not remaining,
                                                  remaining_members=remaining)
                except Exception as fallback:
                    errors.append(f"Emergency process cleanup: {fallback}")
        finally:
            self.selector.close()
            for stream in self.owned_streams:
                stream.close()
            for fd, flags in self.borrowed_flags.items():
                try:
                    fcntl.fcntl(fd, fcntl.F_SETFL, flags)
                except OSError as exc:
                    errors.append(f"Borrowed descriptor restore: {exc}")
            for name, channel in self.channels.items():
                channel["file"].close()
                self.record["channels"][name] = {
                    "log": str(self.log_dir/f"{name}.log"), "bytes_seen": channel["bytes_seen"],
                    "bytes_saved": len(channel["buffer"]),
                    "truncated": channel["bytes_seen"] > len(channel["buffer"]),
                    "borrowed": channel["borrowed"], "eof": channel["eof"]}
            self.record["cleanup"].update(selector_closed=True,
                owned_pipe_fds_closed=all(s.closed for s in self.owned_streams))
            if self.reaper_lease:
                try:
                    self.record["cleanup"]["subreaper_release"] = _release_reaper()
                except OSError as exc:
                    errors.append(f"Subreaper restore: {exc}")
                self.reaper_lease = False
            self.closed = True
        if errors:
            self.record.update(status="error", cleanup_errors=errors)
        elif self.failure:
            self.record["status"] = "error" if self.failure["reason"] == "start_error" else "failed"
        elif self.record["returncode"] not in self.expected:
            self.record["status"] = "failed"
            self._fail("unexpected_exit", expected=list(self.expected))
        else:
            self.record["status"] = "passed"
        self.record.update(failure=self.failure, finished_at=_utc(),
                           elapsed_seconds=round(time.monotonic()-self.started, 6))
        (self.log_dir/"process.json").write_text(json.dumps(self.record, indent=2)+"\n")
        if errors:
            raise CleanupError("; ".join(errors))
        return self.record


def run_process(argv, *, log_dir, timeout=10.0, **kwargs):
    _seconds(timeout)
    process = ManagedProcess(argv, log_dir=log_dir, **kwargs)
    try:
        with process:
            process.close_input()
            process.wait(timeout)
    except (ProcessStartError, ProcessTimeout, OutputLimitExceeded):
        pass  # The failure remains in process.json and in the returned record.
    return process.record
