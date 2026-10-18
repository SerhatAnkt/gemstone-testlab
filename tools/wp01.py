#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""WP-01: small, dependency-free probes against unmodified upstream C examples."""
from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import pty
import selectors
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time
import tty
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parents[1]
UPSTREAM = BASE / "upstream" / "examples"
REVISION = "2619a7584d39203a057abc08ab7c6698dc476868"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources():
    manifest = json.loads((BASE / "source.lock.json").read_text())
    if manifest["revision"] != REVISION:
        raise RuntimeError("Source lock revision differs from the selected WP-01 revision")
    for name, item in manifest["files"].items():
        path = UPSTREAM / name
        if digest(path) != item["sha256"]:
            raise RuntimeError(f"Upstream source changed: {name}")
    return manifest


def build(name, report_dir):
    target = {
        "can": ("canbus/c/sender", "canbus-sender"),
        "serial": ("serial/c", "serial"),
    }[name]
    build_dir = BASE / "build" / "host" / name
    build_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "make", "-C", str(UPSTREAM / target[0]),
        f"PROJDIR={UPSTREAM}", f"BUILDDIR={build_dir}", "CC=gcc",
    ]
    result = subprocess.run(command, capture_output=True, timeout=60)
    log = report_dir / f"build-{name}.log"
    log.write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"{name} build failed; see {log.name}")
    binary = build_dir / target[1]
    return binary, {
        "name": f"build_{name}", "status": "passed", "command": command,
        "returncode": result.returncode, "binary_sha256": digest(binary),
        "log": log.name,
    }


def environment():
    info = {
        "platform": platform.platform(), "kernel": platform.release(),
        "machine": platform.machine(), "python": sys.version,
        "uid": os.getuid(), "tools": {
            name: shutil.which(name) for name in ["gcc", "make", "ip", "modprobe"]
        },
    }
    try:
        master, slave = pty.openpty()
        os.close(master)
        os.close(slave)
        info["pty"] = {"available": True}
    except OSError as exc:
        info["pty"] = {"available": False, "error": str(exc)}
    try:
        with socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW):
            pass
        info["can_socket"] = {"available": True}
    except OSError as exc:
        info["can_socket"] = {"available": False, "errno": exc.errno, "error": str(exc)}
    if Path("/proc/self/status").exists():
        info["capabilities"] = {
            line.split(":", 1)[0]: line.split(":", 1)[1].strip()
            for line in Path("/proc/self/status").read_text().splitlines()
            if line.startswith(("CapEff:", "CapBnd:", "NoNewPrivs:", "Seccomp:"))
        }
    return info


def read_until(fd, expected, timeout=5.0):
    data = bytearray()
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while expected not in data:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Expected {expected!r}; observed {bytes(data)!r}")
            if not selector.select(remaining):
                continue
            chunk = os.read(fd, 4096)
            if not chunk:
                raise EOFError("PTY closed before expected data arrived")
            data.extend(chunk)
            if len(data) > 1024 * 1024:
                raise RuntimeError("Unexpectedly large PTY output")
    return bytes(data)


def read_exact(fd, size, timeout=5.0):
    data = bytearray()
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        selector.register(fd, selectors.EVENT_READ)
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Expected {size} bytes; observed {bytes(data)!r}")
            if not selector.select(remaining):
                continue
            chunk = os.read(fd, size - len(data))
            if not chunk:
                raise EOFError("PTY closed early")
            data.extend(chunk)
    return bytes(data)


def force_stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def serial_probe(binary, report_dir):
    fds = []
    process = None
    transcript = bytearray()
    events = []
    result = {"name": "serial_pty", "backend": "host_pty", "status": "failed"}
    try:
        device_master, device_slave = pty.openpty()
        console_master, console_slave = pty.openpty()
        fds.extend([device_master, device_slave, console_master, console_slave])
        tty.setraw(device_slave)
        tty.setraw(console_slave)
        device_path = os.ttyname(device_slave)
        command = [str(binary), "--device", device_path, "--baud", "115200"]
        result["command"] = command
        process = subprocess.Popen(
            command, stdin=console_slave, stdout=console_slave,
            stderr=subprocess.PIPE, start_new_session=True,
        )
        os.close(console_slave)
        fds.remove(console_slave)

        ready = b"WP01_READY_7f193a\n"
        os.write(device_master, ready)
        transcript.extend(read_until(console_master, ready))
        events.append({"event": "ready", "data_hex": ready.hex()})

        rx = b"SERIAL_RX_WP01_012345\n"
        os.write(device_master, rx)
        observed_rx = read_exact(console_master, len(rx))
        transcript.extend(observed_rx)
        if observed_rx != rx:
            raise AssertionError(f"Serial-to-console mismatch: {observed_rx!r}")
        events.append({"event": "serial_to_console", "expected_hex": rx.hex(),
                       "actual_hex": observed_rx.hex()})

        tx = b"SERIAL_TX_WP01_987654\n"
        os.write(console_master, tx)
        observed_tx = read_exact(device_master, len(tx))
        if observed_tx != tx:
            raise AssertionError(f"Console-to-serial mismatch: {observed_tx!r}")
        events.append({"event": "console_to_serial", "expected_hex": tx.hex(),
                       "actual_hex": observed_tx.hex()})

        os.write(console_master, b"\x03")
        _, errors = process.communicate(timeout=3)
        (report_dir / "serial.stderr.log").write_bytes(errors or b"")
        if process.returncode != 0:
            raise AssertionError(f"Serial program exit code: {process.returncode}")
        events.append({"event": "ctrl_c_exit", "returncode": process.returncode})
        result.update(status="passed", returncode=process.returncode, events=events)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), events=events)
    finally:
        try:
            force_stop(process)
            if process and process.stderr and not process.stderr.closed:
                (report_dir / "serial.stderr.log").write_bytes(process.stderr.read())
                process.stderr.close()
        except Exception as exc:
            result.update(status="failed", cleanup_error=str(exc))
        for fd in reversed(fds):
            try:
                os.close(fd)
            except OSError:
                pass
        (report_dir / "serial.console.bin").write_bytes(transcript)
        (report_dir / "serial.console.log").write_text(
            transcript.decode("utf-8", errors="backslashreplace"))
        result["cleanup"] = {
            "process_collected": process is None or process.poll() is not None,
            "owned_pty_fds_closed": all(_fd_closed(fd) for fd in fds),
        }
    return result


def _fd_closed(fd):
    try:
        os.fstat(fd)
        return False
    except OSError as exc:
        return exc.errno == errno.EBADF


def can_probe(binary, interface, report_dir):
    result = {"name": "can_vcan", "backend": "host_socketcan",
              "interface": interface, "status": "failed"}
    process = None
    frames = []
    try:
        if not interface:
            result.update(status="blocked", error="A prepared vcan interface is required. "
                          "Use tools/run-linux-wp01.sh on a capable Linux host.")
            return result
        with socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as observer:
            observer.settimeout(5)
            observer.bind((interface,))
            process = subprocess.Popen(
                [str(binary), interface], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, start_new_session=True,
            )
            raw = observer.recv(16)
            if len(raw) != 16:
                raise AssertionError(f"Unexpected CAN frame size: {len(raw)}")
            can_id, length, payload = struct.unpack("=IB3x8s", raw)
            frames.append({"can_id": can_id, "length": length,
                           "data_hex": payload[:length].hex()})
            if (can_id, length, payload[:length]) != (0x123, 8, b"MSG_000\x00"):
                raise AssertionError(f"First CAN frame mismatch: {frames[-1]}")

            os.killpg(process.pid, signal.SIGINT)
            for _ in range(8):
                raw = observer.recv(16)
                can_id, length, payload = struct.unpack("=IB3x8s", raw)
                frames.append({"can_id": can_id, "length": length,
                               "data_hex": payload[:length].hex()})
                if can_id == 0x124 and length == 3 and payload[:3] == b"END":
                    break
            else:
                raise AssertionError("END frame not observed")
            stdout, stderr = process.communicate(timeout=3)
            (report_dir / "can.stdout.log").write_bytes(stdout)
            (report_dir / "can.stderr.log").write_bytes(stderr)
            if process.returncode != 0:
                raise AssertionError(f"CAN sender exit code: {process.returncode}")
            result.update(status="passed", returncode=0)
    except PermissionError as exc:
        result.update(status="blocked", error=str(exc), errno=exc.errno)
    except OSError as exc:
        result.update(status="blocked" if exc.errno in
                      (errno.EPERM, errno.EACCES, errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT)
                      else "failed", error=str(exc), errno=exc.errno)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc))
    finally:
        try:
            force_stop(process)
            if process and process.stdout and not process.stdout.closed:
                stdout, stderr = process.communicate(timeout=2)
                (report_dir / "can.stdout.log").write_bytes(stdout)
                (report_dir / "can.stderr.log").write_bytes(stderr)
        except Exception as exc:
            result.update(status="failed", cleanup_error=str(exc))
        result["frames"] = frames
        result["process_collected"] = process is None or process.poll() is not None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=["doctor", "build", "serial", "can", "all"])
    parser.add_argument("--interface", default=os.environ.get("TESTLAB_CAN_IFACE"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_dir = (args.output or BASE / "artifacts" / f"wp01-{stamp}").resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": 1, "started_at": utc_now(),
        "scope": "WP-01 technical feasibility probes",
        "source_revision": REVISION, "environment": environment(),
        "checks": [], "github_hosted_runner": "not_executed",
        "board_runtime": "not_run",
    }
    try:
        lock = verify_sources()
        report["source_files_verified"] = len(lock["files"])
        report["source_lock_sha256"] = digest(BASE / "source.lock.json")
        if args.check == "doctor":
            missing = [name for name in ("gcc", "make", "ip")
                       if not report["environment"]["tools"][name]]
            ready = (not missing and report["environment"]["pty"]["available"]
                     and report["environment"]["can_socket"]["available"])
            report["checks"].append({
                "name": "host_preflight", "status": "passed" if ready else "blocked",
                "missing_tools": missing,
                "note": "vcan creation privileges and module availability are exercised "
                        "by run-linux-wp01.sh, not inferred from uid.",
            })
        if args.check in ("build", "serial", "can", "all"):
            needed = ["can", "serial"] if args.check in ("build", "all") else [args.check]
            binaries = {}
            for name in needed:
                binaries[name], item = build(name, report_dir)
                report["checks"].append(item)
            if args.check in ("serial", "all"):
                report["checks"].append(serial_probe(binaries["serial"], report_dir))
            if args.check in ("can", "all"):
                report["checks"].append(
                    can_probe(binaries["can"], args.interface, report_dir))
    except Exception as exc:
        report["checks"].append({"name": "setup", "status": "failed",
                                 "error_type": type(exc).__name__, "error": str(exc)})
    statuses = [item["status"] for item in report["checks"]]
    report["status"] = ("failed" if "failed" in statuses else
                        "blocked" if "blocked" in statuses else "passed")
    report["finished_at"] = utc_now()
    save_json(report_dir / "run.json", report)
    print(json.dumps({
        "status": report["status"], "checks": [
            {"name": item["name"], "status": item["status"]} for item in report["checks"]],
        "report": str(report_dir / "run.json"),
        "can_socket_available": report["environment"]["can_socket"]["available"],
    }, ensure_ascii=False, indent=2))
    return 1 if report["status"] == "failed" else 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())

