#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Optional Linux-guest probe for hosts that forbid SocketCAN/vcan operations.

The guest is an ordinary x86 Linux kernel, not a Gemstone/AM67A emulator.
--guest-root is a directory containing extracted Ubuntu QEMU/kernel/BusyBox packages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone

from wp01 import verify_sources

BASE = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpio_newc(entries):
    output = bytearray()
    for inode, (name, mode, data, rdevmajor, rdevminor) in enumerate(entries, 1):
        fields = [inode, mode, 0, 0, 1, 0, len(data), 0, 0,
                  rdevmajor, rdevminor, len(name.encode()) + 1, 0]
        header = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
        output.extend(header)
        output.extend(name.encode() + b"\0")
        output.extend(b"\0" * (-len(output) % 4))
        output.extend(data)
        output.extend(b"\0" * (-len(output) % 4))
    name = "TRAILER!!!"
    fields = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name) + 1, 0]
    output.extend(b"070701" + b"".join(f"{value:08x}".encode() for value in fields))
    output.extend(name.encode() + b"\0")
    output.extend(b"\0" * (-len(output) % 512))
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guest-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    root = args.guest_root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    lock = verify_sources()
    started_at = datetime.now(timezone.utc).isoformat()
    kernel = sorted((root / "boot").glob("vmlinuz-*"))[-1]
    version = kernel.name.removeprefix("vmlinuz-")
    qemu = root / "usr/bin/qemu-system-x86_64"
    busybox = root / "usr/bin/busybox"
    if not busybox.exists():
        busybox = root / "bin/busybox"
    build = BASE / "build" / "host-vm-static" / "can"
    build.mkdir(parents=True, exist_ok=True)
    commands = [
        ["make", "-C", str(BASE / "upstream/examples/canbus/c/sender"),
         f"PROJDIR={BASE / 'upstream/examples'}", f"BUILDDIR={build}",
         "CC=gcc", "LDFLAGS=-static"],
        ["gcc", "-D_DEFAULT_SOURCE", "-std=c11", "-Wall", "-Wextra", "-Werror",
         "-O2", "-static", str(BASE / "tools/can_reference.c"),
         "-o", str(build / "can-reference")],
    ]
    for index, command in enumerate(commands):
        result = subprocess.run(command, capture_output=True, timeout=60)
        (out / f"build-{index}.log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Static build failed; see build-{index}.log")

    module_files = {}
    for path in (root / "lib/modules" / version).rglob("*.ko*"):
        name = path.name.split(".ko", 1)[0].replace("_", "-")
        module_files[name] = path
    loaded = []
    payloads = {}

    def add_module(name):
        if name in loaded:
            return
        path = module_files[name]
        if path.suffix == ".zst":
            data = subprocess.run(["zstd", "-d", "-c", str(path)],
                                  capture_output=True, check=True).stdout
        elif path.suffix == ".xz":
            import lzma
            data = lzma.decompress(path.read_bytes())
        else:
            data = path.read_bytes()
        match = re.search(rb"(?:^|\0)depends=([^\0]*)", data)
        dependencies = match.group(1).decode().split(",") if match else []
        for dep in dependencies:
            if dep:
                add_module(dep.replace("_", "-"))
        payloads[name] = data
        loaded.append(name)

    for module in ("can", "can-raw", "vcan"):
        add_module(module)
    init = """#!/bin/sh
export PATH=/bin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
created=0
finish() {
    rc=$?
    trap - EXIT
    if [ "$created" = 1 ]; then
        ip link del dev vcan0 || rc=1
        if ip link show dev vcan0 >/dev/null 2>&1; then
            rc=1
        else
            echo 'WP01_GUEST_CLEANUP {"interface_removed":true}'
        fi
    fi
    echo "WP01_GUEST_EXIT $rc"
    poweroff -f
}
trap finish EXIT
set -eu
echo "WP01_GUEST_KERNEL $(uname -r)"
"""
    for name in loaded:
        init += f"insmod /modules/{name}.ko\n"
    init += """ip link add dev vcan0 type vcan
created=1
ip link set dev vcan0 up
ip link show dev vcan0
/can-reference vcan0 /canbus-sender /tmp/sender.log
cat /tmp/sender.log
"""
    entries = []
    for directory in ("bin", "dev", "proc", "sys", "tmp", "modules"):
        entries.append((directory, stat.S_IFDIR | 0o755, b"", 0, 0))
    entries.append(("dev/console", stat.S_IFCHR | 0o600, b"", 5, 1))
    entries.append(("bin/busybox", stat.S_IFREG | 0o755, busybox.read_bytes(), 0, 0))
    for applet in ("sh", "mount", "ip", "insmod", "cat", "uname", "poweroff"):
        entries.append((f"bin/{applet}", stat.S_IFLNK | 0o777, b"busybox", 0, 0))
    entries.append(("init", stat.S_IFREG | 0o755, init.encode(), 0, 0))
    entries.append(("canbus-sender", stat.S_IFREG | 0o755,
                    (build / "canbus-sender").read_bytes(), 0, 0))
    entries.append(("can-reference", stat.S_IFREG | 0o755,
                    (build / "can-reference").read_bytes(), 0, 0))
    for name in loaded:
        entries.append((f"modules/{name}.ko", stat.S_IFREG | 0o644, payloads[name], 0, 0))
    initrd = out / "probe-initramfs.cpio"
    initrd.write_bytes(cpio_newc(entries))
    (out / "guest-init.sh").write_text(init)
    command = [
        str(qemu), "-L", str(root / "usr/share/qemu"),
        "-bios", str(root / "usr/share/seabios/bios-256k.bin"), "-machine", "pc",
        "-accel", "tcg,thread=single", "-cpu", "max", "-m", "512M", "-smp", "1",
        "-nodefaults", "-display", "none", "-serial", "stdio", "-monitor", "none",
        "-no-reboot", "-kernel", str(kernel), "-initrd", str(initrd),
        "-append", "console=ttyS0 rdinit=/init panic=1 loglevel=3",
    ]
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = str(root / "usr/lib/x86_64-linux-gnu")
    env["QEMU_MODULE_DIR"] = str(root / "usr/lib/x86_64-linux-gnu/qemu")
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(command, env=env, capture_output=True, timeout=args.timeout)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        result = subprocess.CompletedProcess(command, 124, exc.stdout or b"", exc.stderr or b"")
    elapsed = time.monotonic() - started
    log = result.stdout + result.stderr
    (out / "guest-console.log").write_bytes(log)
    text = log.decode("utf-8", errors="replace").replace("\r", "")
    match = re.search(r"WP01_CAN_RESULT (\{[^\n]*\})", text)
    oracle = json.loads(match.group(1)) if match else None
    frames = [json.loads(item) for item in re.findall(r"WP01_CAN_FRAME (\{[^\n]*\})", text)]
    exit_match = re.search(r"WP01_GUEST_EXIT (\d+)", text)
    guest_exit = int(exit_match.group(1)) if exit_match else None
    cleanup_match = re.search(r"WP01_GUEST_CLEANUP (\{[^\n]*\})", text)
    cleanup = json.loads(cleanup_match.group(1)) if cleanup_match else {}
    passed = (result.returncode == 0 and guest_exit == 0 and oracle
              and oracle["status"] == "passed" and cleanup.get("interface_removed"))
    report = {
        "schema_version": 1, "name": "can_linux_guest",
        "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "backend": "qemu_tcg_x86_linux_vcan", "network": "none",
        "source_revision": "2619a7584d39203a057abc08ab7c6698dc476868",
        "source_files_verified": len(lock["files"]),
        "source_lock_sha256": sha256(BASE / "source.lock.json"),
        "guest_kernel": version, "kernel_sha256": sha256(kernel),
        "initramfs_sha256": sha256(initrd),
        "sender_binary_sha256": sha256(build / "canbus-sender"),
        "reference_binary_sha256": sha256(build / "can-reference"),
        "qemu_returncode": result.returncode, "guest_exit": guest_exit,
        "timed_out": timed_out, "cleanup": cleanup,
        "elapsed_seconds": round(elapsed, 3), "modules": loaded,
        "frames": frames, "oracle": oracle, "command": command,
        "board_runtime": "not_run", "github_hosted_runner": "not_executed",
        "scope_note": "Real Linux vcan in an x86 guest. Does not emulate AM67A, R5 or physical CAN.",
    }
    (out / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

