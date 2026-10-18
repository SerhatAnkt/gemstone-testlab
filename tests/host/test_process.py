# SPDX-License-Identifier: Apache-2.0
import fcntl
import json
import os
from pathlib import Path
import pty
import signal
import sys
import tempfile
import unittest
import tty

from tests.testlab.build import PROJECT, build_targets
from tests.testlab.process import (ManagedProcess, OutputLimitExceeded, ProcessError,
                                   ProcessStartError, ProcessTimeout, group_members, run_process, subreaper_state)

HELPER = PROJECT / "tests/fixtures/process_helper.py"


class ProcessTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get("TESTLAB_EVIDENCE_ROOT")
        if evidence:
            root = Path(evidence).resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName+"-", dir=root))
        else:
            temporary = tempfile.TemporaryDirectory(prefix="testlab-process-")
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.reaper_before = subreaper_state()

    def tearDown(self):
        self.assertEqual(subreaper_state(), self.reaper_before)

    def process(self, mode, name=None, **kwargs):
        return ManagedProcess([sys.executable, "-u", str(HELPER), mode],
            log_dir=self.root/(name or mode), terminate_grace=0.08, cleanup_timeout=1.5, **kwargs)

    def clean(self, process):
        record = process.record
        self.assertTrue(record["cleanup"]["leader_reaped"])
        self.assertTrue(record["cleanup"]["group_gone"])
        self.assertTrue(record["cleanup"]["owned_pipe_fds_closed"])
        self.assertTrue(record["cleanup"]["selector_closed"])
        self.assertEqual(group_members(process.procfs_pgid), [])
        saved = json.loads((process.log_dir/"process.json").read_text())
        self.assertEqual(saved["status"], record["status"])

    def test_normal_binary_output_and_graceful_shutdown(self):
        process = self.process("normal")
        with process:
            self.assertEqual(process.wait(2), 0)
        self.assertEqual(process.output(), b"OUT\x00WP03\n")
        self.assertEqual(process.output("stderr"), b"ERR\x00WP03\n")
        self.assertEqual(process.record["status"], "passed")
        self.clean(process)
        graceful = self.process("graceful")
        with graceful:
            graceful.expect(b"READY\n", timeout=2)
            self.assertEqual(graceful.shutdown(timeout=1), 0)
        self.assertIn(b"BYE\n", graceful.output())
        self.assertEqual(graceful.record["status"], "passed")
        self.clean(graceful)

    def test_exit_codes_and_signals_are_preserved(self):
        error = self.process("error")
        with error:
            self.assertEqual(error.wait(2), 7)
        self.assertEqual(error.record["status"], "failed")
        self.clean(error)
        terminated = self.process("hang")
        with terminated:
            terminated.expect(b"READY\n", timeout=2)
            terminated.signal(signal.SIGUSR1)
            self.assertEqual(terminated.wait(1), -signal.SIGUSR1)
        self.assertEqual(terminated.record["signal"], signal.SIGUSR1)
        self.assertEqual(terminated.record["status"], "failed")
        self.clean(terminated)

    def test_start_failure_closes_resources(self):
        result = run_process([str(self.root/"missing-executable")], log_dir=self.root/"missing")
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["pid"])
        self.assertTrue(result["cleanup"]["selector_closed"])
        self.assertEqual(result["failure"]["reason"], "start_error")

    def test_fragmented_ready_marker_crosses_read_boundaries(self):
        process = self.process("fragment")
        with process:
            process.expect(b"FIRST_PART_WRITTEN\n", channel="stderr", timeout=2)
            process.send(b"G")
            self.assertEqual(process.expect(b"READY_\x00WP03\n", timeout=2), b"READY_\x00WP03\n")
            self.assertEqual(process.wait(2), 0)
        self.clean(process)

    def test_partial_start_failure_still_collects_spawned_process(self):
        with (self.root/"not-a-pollable-tty").open("w+b") as borrowed:
            process = self.process("hang", readers={"invalid_peer": borrowed.fileno()})
            with self.assertRaises(ProcessStartError):
                with process:
                    self.fail("A regular file must not register as a PTY capture")
            self.assertEqual(process.record["status"], "error")
            os.fstat(borrowed.fileno())
            self.clean(process)

    def test_large_bidirectional_io_cannot_fill_pipe_and_deadlock(self):
        payload = bytes(range(256))*1024
        process = self.process("duplex", max_output_bytes=2*1024*1024)
        with process:
            process.expect(b"READY\n", timeout=2)
            process.send(payload, timeout=3)
            process.close_input()
            self.assertEqual(process.read_exact(len(payload), timeout=3), payload)
            self.assertEqual(process.wait(2), 0)
        self.assertEqual(process.output("stderr"), b"E"*(256*1024)+payload)
        self.assertEqual(process.record["status"], "passed")
        self.clean(process)

    def test_ready_timeout_and_early_eof_are_distinct(self):
        hanging = self.process("hang")
        with self.assertRaises(ProcessTimeout):
            with hanging:
                hanging.expect(b"READY\n", timeout=2)
                hanging.expect(b"NEVER\n", timeout=0.06)
        self.assertEqual(hanging.record["failure"]["phase"], "ready")
        self.clean(hanging)
        early = self.process("normal")
        with self.assertRaises(ProcessError):
            with early:
                early.expect(b"NEVER\n", timeout=2)
        self.assertEqual(early.record["failure"]["reason"], "unexpected_eof")
        self.clean(early)

    def test_run_timeout_stops_process_and_is_not_success(self):
        process = self.process("hang")
        with self.assertRaises(ProcessTimeout):
            with process:
                process.expect(b"READY\n", timeout=2)
                process.wait(0.06)
        self.assertEqual(process.record["failure"]["phase"], "run")
        self.assertEqual(process.record["status"], "failed")
        self.clean(process)

    def test_input_backpressure_has_a_write_deadline(self):
        process = self.process("hang")
        with self.assertRaises(ProcessTimeout):
            with process:
                process.expect(b"READY\n", timeout=2)
                process.send(b"X"*(1024*1024), timeout=0.06)
        self.assertEqual(process.record["failure"]["phase"], "write")
        self.assertEqual(process.record["status"], "failed")
        self.clean(process)

    def test_ignored_sigterm_escalates_to_sigkill(self):
        process = self.process("ignore_term")
        with self.assertRaises(ProcessTimeout):
            with process:
                process.expect(b"READY\n", timeout=2)
                process.shutdown(timeout=0.06)
        signals = [e["signal"] for e in process.record["events"] if e["action"] == "signal"]
        self.assertIn(signal.SIGKILL, signals)
        self.assertEqual(process.record["returncode"], -signal.SIGKILL)
        self.assertEqual(process.record["failure"]["phase"], "shutdown")
        self.clean(process)

    def test_forked_child_is_killed_and_reaped(self):
        process = self.process("tree")
        with self.assertRaises(ProcessTimeout):
            with process:
                process.expect(b"READY\n", timeout=2)
                process.wait(0.06)
        child = int(process.output().splitlines()[0].split()[1])
        self.assertIn(child, [r["pid"] for r in process.record["cleanup"]["adopted_children_reaped"]])
        self.assertEqual(process.record["status"], "failed")
        self.clean(process)

    def test_zero_exit_with_orphan_child_is_not_a_clean_success(self):
        process = self.process("orphan")
        with process:
            process.expect(b"READY\n", timeout=2)
            self.assertEqual(process.wait(2), 0)
        self.assertEqual(process.record["returncode"], 0)
        self.assertEqual(process.record["status"], "failed")
        self.assertTrue(process.record["cleanup"]["adopted_children_reaped"])
        self.clean(process)

    def test_scenario_exception_still_cleans_the_group(self):
        process = self.process("ignore_term")
        with self.assertRaisesRegex(ValueError, "controlled scenario failure"):
            with process:
                process.expect(b"READY\n", timeout=2)
                raise ValueError("controlled scenario failure")
        self.assertEqual(process.record["failure"]["reason"], "context_exception")
        self.clean(process)

    def test_real_c_serial_over_borrowed_ptys(self):
        report = build_targets(target_ids=["serial.c"], build_root=self.root/"binaries",
                               output_root=self.root/"build-reports")
        self.assertEqual(report["status"], "passed")
        binary = report["targets"][0]["binary"]["path"]
        device_master, device_slave = pty.openpty()
        console_master, console_slave = pty.openpty()
        fds = (device_master, device_slave, console_master, console_slave)
        for fd in (device_slave, console_slave):
            tty.setraw(fd)
        flags = {fd: fcntl.fcntl(fd, fcntl.F_GETFL) for fd in (device_master, console_master)}
        process = ManagedProcess([binary, "--device", os.ttyname(device_slave), "--baud", "115200"],
            log_dir=self.root/"c-serial", stdin=console_slave, stdout=console_slave,
            readers={"console": console_master, "device": device_master})
        try:
            with process:
                process.send(b"WP03_SERIAL_READY\n", fd=device_master)
                process.expect(b"WP03_SERIAL_READY\n", channel="console", timeout=2)
                process.send(b"RX\x00DATA\n", fd=device_master)
                self.assertEqual(process.read_exact(8, channel="console", timeout=2), b"RX\x00DATA\n")
                process.send(b"TX\x00DATA\n", fd=console_master)
                self.assertEqual(process.read_exact(8, channel="device", timeout=2), b"TX\x00DATA\n")
                process.send(b"\x03", fd=console_master)
                self.assertEqual(process.wait(2), 0)
            self.assertEqual(process.record["status"], "passed")
            self.clean(process)
            for fd, old in flags.items():
                self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL), old)
            for fd in fds:
                os.fstat(fd)  # Process manager must not close fixture-owned PTYs.
        finally:
            for fd in fds:
                os.close(fd)

    def test_output_budget_is_bounded_and_never_silent_success(self):
        process = self.process("overflow", max_output_bytes=4096)
        with self.assertRaises(OutputLimitExceeded):
            with process:
                process.wait(2)
        self.assertEqual(process.record["status"], "failed")
        self.assertEqual(len(process.output()), 4096)
        self.assertTrue(process.record["channels"]["stdout"]["truncated"])
        self.clean(process)

    def test_two_owned_groups_are_isolated(self):
        first = self.process("graceful", "first")
        second = self.process("graceful", "second")
        with first:
            first.expect(b"READY\n", timeout=2)
            with second:
                second.expect(b"READY\n", timeout=2)
                self.assertEqual(first.shutdown(timeout=1), 0)
                first.close()
                self.assertIsNone(second.process.poll())
                self.assertEqual(second.shutdown(timeout=1), 0)
        self.clean(first)
        self.clean(second)

    def test_repeated_runs_do_not_leak_file_descriptors(self):
        before = set(os.listdir("/proc/self/fd"))
        for index in range(10):
            process = self.process("normal", f"repeat-{index}")
            with process:
                self.assertEqual(process.wait(2), 0)
            self.clean(process)
        self.assertEqual(set(os.listdir("/proc/self/fd")), before)
