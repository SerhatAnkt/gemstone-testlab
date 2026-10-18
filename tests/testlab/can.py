# SPDX-License-Identifier: Apache-2.0
"""Owned Linux vcan leases and independent SocketCAN observers."""
import json
import os
from pathlib import Path
import re
import select
import shutil
import socket
import time
import uuid

from .contracts import decode_classic_frame, encode_classic_frame
from .process import run_process


class VCanError(RuntimeError):
    pass


class VCanCleanupError(VCanError):
    pass


def validate_interface_name(name):
    if not re.fullmatch(r"gtl[0-9a-f]{10}", name):
        raise ValueError("TestLab-owned interfaces require gtl plus ten lowercase hex characters")
    return name


class VCanLease:
    def __init__(self, *, log_dir, name=None):
        self.name = validate_interface_name(name or "gtl"+uuid.uuid4().hex[:10])
        self.alias = "testlab:"+uuid.uuid4().hex
        self.log_dir = Path(log_dir).resolve()
        self.log_dir.mkdir(parents=True, exist_ok=False)
        self.ip = shutil.which("ip")
        self.prefix = [] if os.geteuid() == 0 else [shutil.which("sudo") or "sudo", "-n"]
        self.created = False
        self.closed = False
        self.index = None
        self.alias_set = False
        self.serial = 0
        self.record = {"schema_version": 1, "interface": self.name, "alias": self.alias,
            "owned": False, "runner_uid": os.getuid(), "status": "setting_up", "operations": []}

    def _save(self):
        (self.log_dir/"lease.json").write_text(json.dumps(self.record, indent=2)+"\n")

    def _run(self, args, privileged=False):
        if not self.ip:
            raise VCanError("iproute2 is required")
        directory = self.log_dir/f"op-{self.serial:02d}"
        self.serial += 1
        result = run_process([*(self.prefix if privileged else []), self.ip, *args],
                             log_dir=directory, timeout=5, max_output_bytes=1024*1024)
        self.record["operations"].append({"argv": result["argv"], "status": result["status"],
            "returncode": result["returncode"], "process_report": str(directory/"process.json")})
        self._save()
        if result["status"] != "passed":
            error = (directory/"stderr.log").read_text(errors="replace") if (directory/"stderr.log").exists() else str(result.get("failure"))
            raise VCanError(f"ip operation failed; vcan/module/CAP_NET_ADMIN or sudo may be unavailable: {error}")
        return (directory/"stdout.log").read_bytes()

    def _links(self):
        return json.loads(self._run(["-details", "-json", "link", "show"]))

    def inspect(self):
        return next((link for link in self._links() if link["ifname"] == self.name), None)

    def __enter__(self):
        try:
            if self.inspect() is not None:
                raise VCanError("Interface already exists; it is not owned by this lease")
            self._run(["link", "add", "dev", self.name, "type", "vcan"], privileged=True)
            self.created = True
            self.record["owned"] = True
            # Remember the index immediately, before any later setup can fail.
            info = self.inspect()
            if info is None or info.get("linkinfo", {}).get("info_kind") != "vcan":
                raise VCanError("New interface could not be verified as vcan")
            self.index = info["ifindex"]
            self.record["ifindex"] = self.index
            self._run(["link", "set", "dev", self.name, "alias", self.alias], privileged=True)
            self.alias_set = True
            self._run(["link", "set", "dev", self.name, "up"], privileged=True)
            info = self.inspect()
            if info.get("ifalias") != self.alias or "UP" not in info["flags"]:
                raise VCanError("Owned interface alias/UP state was not verified")
            self.record.update(status="ready", ready=info)
            self._save()
            return self
        except BaseException as exc:
            self.record.update(status="error", setup_error=str(exc))
            self.close()
            raise

    def close(self):
        if self.closed:
            return self.record
        try:
            if self.created:
                links = self._links()
                current = next((link for link in links if link["ifname"] == self.name), None)
                if current is None and any(link["ifindex"] == self.index or link.get("ifalias") == self.alias
                                           for link in links):
                    raise VCanCleanupError("Owned interface was renamed; refusing cleanup by a stale name")
                if current is not None:
                    if (current["ifindex"] != self.index or
                        current.get("linkinfo", {}).get("info_kind") != "vcan" or
                        current.get("ifalias", "") != (self.alias if self.alias_set else "")):
                        raise VCanCleanupError("Interface identity changed; refusing to delete a foreign resource")
                    self._run(["link", "del", "dev", self.name], privileged=True)
                if self.inspect() is not None:
                    raise VCanCleanupError("Owned interface remains after deletion")
            self.record["cleanup"] = {"owned_interface_removed": self.created,
                                      "foreign_interface_touched": False}
            self.closed = True
            if self.record["status"] == "ready":
                self.record["status"] = "closed"
        except BaseException as exc:
            self.record.update(status="error", cleanup_error=str(exc))
            raise
        finally:
            self._save()
        return self.record

    def __exit__(self, exc_type, exc, traceback):
        if exc is not None:
            self.record["scenario_exception"] = {"type": exc_type.__name__, "error": str(exc)}
        self.close()
        return False


class CanObserver:
    def __init__(self, interface):
        self.socket = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        try:
            self.socket.bind((interface,))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.frames = []
        self.closed = False

    def receive(self, process, timeout=5):
        deadline = time.monotonic()+timeout
        while True:
            process.service_io()
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Independent SocketCAN observer timed out")
            ready, _, _ = select.select([self.socket], [], [], min(remaining, 0.05))
            if ready:
                frame = decode_classic_frame(self.socket.recv(72))
                self.frames.append(frame.evidence())
                return frame
            if process.process.poll() is not None:
                raise RuntimeError(f"Sender exited before the expected frame: {process.process.returncode}")

    def close(self):
        self.socket.close()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()


class CanPublisher:
    """Independent reference sender; never imports an upstream implementation."""
    def __init__(self, interface):
        self.socket = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
        self.closed = False
        self.frames = []
        try:
            self.socket.bind((interface,))
            self.socket.settimeout(1)
        except BaseException:
            self.close()
            raise

    def send(self, frame):
        raw = encode_classic_frame(frame)
        if self.socket.send(raw) != len(raw):
            raise VCanError("Reference sender wrote an incomplete Linux CAN frame")
        self.frames.append(frame.evidence())

    def close(self):
        self.socket.close()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
