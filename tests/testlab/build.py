# SPDX-License-Identifier: Apache-2.0
"""Build the current example tree with its own Makefiles, without caching binaries."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import uuid

from .targets import select_targets
from .process import run_process

PROJECT = Path(__file__).resolve().parents[2]
# Upstream Makefile flags stay in control of the host profile.
CLEARED_ENV = ("MAKEFLAGS", "GNUMAKEFLAGS", "MFLAGS", "MAKEOVERRIDES", "MAKEFILES",
               "CC", "CXX", "CFLAGS", "CXXFLAGS", "CPPFLAGS", "LDFLAGS")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_source_root():
    if (PROJECT / "common.mk").is_file() and (PROJECT / "canbus").is_dir():
        return PROJECT
    return PROJECT / "upstream/examples"


def source_snapshot(root, targets):
    names = {"common.mk"}
    for target in targets:
        names.update(target.inputs)
        # Include newly added source/header files, not just the original snapshot.
        for path in (root / target.directory).rglob("*"):
            if path.is_file() and path.suffix in (".c", ".cpp", ".h", ".hpp", ".mk"):
                names.add(path.relative_to(root).as_posix())
    names.update(path.name for path in root.glob("*.mk") if path.is_file())
    files = []
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            files.append({"path": name, "status": "missing"})
        else:
            files.append({"path": name, "status": "present", "sha256": sha256(path),
                          "size_bytes": path.stat().st_size})
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"files": files, "digest": digest}


def reference_state(snapshot):
    path = PROJECT / "source.lock.json"
    if not path.is_file():
        return None
    lock = json.loads(path.read_text())
    differences = [item["path"] for item in snapshot["files"]
                   if item.get("sha256") != lock["files"].get(item["path"], {}).get("sha256")
                   or item["status"] != "present"]
    return {"repository": lock["repository"], "revision": lock["revision"],
            "selected_inputs_match": not differences, "differences": differences,
            "note": "Reference comparison only; modified working files are built as supplied."}


def git_state(root):
    if not shutil.which("git"):
        return {"available": False, "commit": None, "dirty": None}
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                                timeout=5, text=True)
        return result.stdout.strip() if result.returncode == 0 else None
    commit = git("rev-parse", "HEAD")
    if commit is None:
        return {"available": False, "commit": None, "dirty": None}
    status = git("status", "--porcelain", "--untracked-files=normal", "--", ".")
    return {"available": True, "commit": commit,
            "dirty": bool(status) if status is not None else None,
            "scope": "Selected source root; content hashes are also recorded."}


def run_logged(argv, cwd, log, timeout, env):
    process_dir = log.with_suffix(".process")
    result = run_process(argv, cwd=cwd, env=env, log_dir=process_dir, timeout=timeout,
                         stderr=subprocess.STDOUT, max_output_bytes=8*1024*1024)
    output = process_dir / "stdout.log"
    log.write_bytes(output.read_bytes() if output.exists() else
                    (str(result.get("failure")) + "\n").encode())
    record = {key: result[key] for key in ("argv", "cwd", "started_at", "finished_at",
                                         "elapsed_seconds", "returncode", "timed_out")}
    record.update(log=str(log), process_status=result["status"],
                  process_report=str(process_dir / "process.json"))
    if result["status"] == "error" or (result["status"] != "passed" and result["returncode"] == 0):
        record["error"] = str(result.get("cleanup_errors") or result.get("failure"))
    return record


def elf_info(path, *, expected_machine=None, expected_bits=None, expected_byte_order=None):
    with path.open("rb") as stream:
        data = stream.read(64)
    if len(data) < 52 or data[:4] != b"\x7fELF" or data[4] not in (1, 2) or data[5] not in (1, 2) or data[6] != 1:
        raise ValueError("Build output is not a supported ELF binary")
    bits, order = {1:32,2:64}[data[4]], "little" if data[5] == 1 else "big"
    endian = "<" if data[5] == 1 else ">"
    header_size = 64 if bits == 64 else 52
    if len(data) < header_size:
        raise ValueError("Truncated ELF header")
    fields = struct.unpack_from(endian+("HHIQQQIHHHHHH" if bits == 64 else "HHIIIIIHHHHHH"),data,16)
    kind,machine,version,_,phoff,shoff,_,ehsize,phentsize,phnum,shentsize,shnum,_ = fields
    expected = expected_machine if expected_machine is not None else {"x86_64": 62, "amd64": 62, "aarch64": 183, "arm64": 183,
                "i386": 3, "i686": 3, "armv7l": 40}.get(platform.machine().lower())
    if expected is None or machine != expected:
        raise ValueError(f"ELF machine mismatch: got {machine}, expected {expected}")
    if bits != (expected_bits or struct.calcsize('P')*8) or order != (expected_byte_order or sys.byteorder):
        raise ValueError("ELF class or byte order mismatch")
    size = path.stat().st_size
    if kind not in (2,3) or version != 1 or ehsize != header_size or phnum == 0 or phentsize != (56 if bits == 64 else 32):
        raise ValueError("Invalid ELF executable header")
    if phoff < header_size or phoff+phnum*phentsize > size or (shnum and (shoff < header_size or shoff+shnum*shentsize > size)):
        raise ValueError("ELF header tables extend outside the artifact")
    loads,interpreter = 0,None
    with path.open('rb') as stream:
        for index in range(phnum):
            stream.seek(phoff+index*phentsize)
            segment = struct.unpack(endian+('IIQQQQQQ' if bits == 64 else 'IIIIIIII'),stream.read(phentsize))
            segment_type = segment[0]
            offset,length = (segment[2],segment[5]) if bits == 64 else (segment[1],segment[4])
            if offset+length > size:
                raise ValueError('ELF segment extends outside the artifact')
            loads += segment_type == 1
            if segment_type == 3:
                if not 1 < length <= 4096:
                    raise ValueError('Invalid ELF interpreter segment')
                stream.seek(offset)
                value = stream.read(length)
                if not value.endswith(b'\0'):
                    raise ValueError('ELF interpreter is not terminated')
                interpreter = value[:-1].decode('ascii')
    if not loads:
        raise ValueError('ELF artifact has no loadable segments')
    if not os.access(path, os.X_OK):
        raise ValueError("Build output is not executable")
    return {"class_bits": bits, "machine": machine,"byte_order": order,
            "type":kind,"load_segments":loads,"interpreter":interpreter}


def build_targets(*, source_root=None, target_ids=None, build_root=None,
                  output_root=None, cc=None, cxx=None, timeout=60.0,
                  profile="host", toolchain_root=None):
    if profile == 'aarch64':
        from .cross_build import cross_build_targets
        return cross_build_targets(source_root=source_root,target_ids=target_ids,
            build_root=build_root,output_root=output_root,cc=cc,cxx=cxx,
            timeout=timeout,toolchain_root=toolchain_root)
    if profile != 'host' or toolchain_root is not None:
        raise ValueError('Select host or aarch64; --toolchain-root belongs to aarch64')
    cc,cxx = cc or 'gcc',cxx or 'g++'
    targets = select_targets(target_ids)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Build timeout must be finite and positive")
    source = Path(source_root or default_source_root()).resolve()
    if not source.is_dir():
        raise ValueError(f"Source root is not a directory: {source}")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = Path(output_root or PROJECT / "artifacts/testlab").resolve() / run_id
    out.mkdir(parents=True, exist_ok=False)
    logs = out / "build"
    logs.mkdir()
    builds = Path(build_root or PROJECT / "build/testlab").resolve()
    env = os.environ.copy()
    for key in CLEARED_ENV:
        env.pop(key, None)
    before = source_snapshot(source, targets)
    report = {
        "schema_version": 1, "work_package": "WP-02", "run_id": run_id,
        "started_at": now(), "profile": "host", "stage": "build", "status": "error",
        "source": {"root": str(source), "selection": "explicit_working_tree" if source_root
                   else "default_working_tree", "git": git_state(source),
                   "inputs": before, "reference": reference_state(before)},
        "environment": {"platform": platform.platform(), "python": sys.version,
                        "inherited_make_flag_variables_removed": list(CLEARED_ENV)},
        "tools": {}, "targets": [], "report_directory": str(out),
        "execution": {"host_runtime": "not_run", "arm64_build": "not_run",
                      "board_runtime": "not_run", "github_hosted_runner": "not_executed"},
    }
    commands = []
    requested_tools = {"make": "make"}
    if any(t.language == "c" for t in targets):
        requested_tools["cc"] = cc
    if any(t.language == "cpp" for t in targets):
        requested_tools["cxx"] = cxx
    for key, executable in requested_tools.items():
        resolved = shutil.which(executable)
        item = {"requested": executable, "path": resolved, "status": "error"}
        if resolved:
            command = run_logged([resolved, "--version"], source, logs / f"tool-{key}.log", 5, env)
            commands.append(command)
            item["command"] = command
            if command["returncode"] == 0 and not command["timed_out"]:
                lines = (logs / f"tool-{key}.log").read_text(errors="replace").splitlines()
                if lines and command["process_status"] == "passed":
                    item.update(status="passed", version=lines[0])
        else:
            item["error"] = f"Executable not found: {executable}"
        report["tools"][key] = item
    for target in targets:
        directory = builds / "host" / target.id / run_id
        directory.mkdir(parents=True, exist_ok=False)
        binary = directory / target.binary
        item = {"id": target.id, "language": target.language, "source_directory": target.directory,
                "profile": "host", "build_directory": str(directory), "status": "error",
                "expected_binary": str(binary), "binary": None, "command": None}
        needed = ["make", "cc" if target.language == "c" else "cxx"]
        missing = [name for name in ("common.mk", *target.inputs) if not (source / name).is_file()]
        if missing:
            item["error"] = f"Missing source inputs: {', '.join(missing)}"
        elif any(report["tools"][name]["status"] != "passed" for name in needed):
            item["error"] = "Required build tool is unavailable; see tools in this report"
        else:
            compiler_key = "cc" if target.language == "c" else "cxx"
            argv = [report["tools"]["make"]["path"], "-C", str(source / target.directory),
                    f"PROJDIR={source}", f"BUILDDIR={directory}",
                    ("CC=" if target.language == "c" else "CXX=") + report["tools"][compiler_key]["path"]]
            command = run_logged(argv, source, logs / f"{target.id}.log", timeout, env)
            commands.append(command)
            item.update(command=command, compiler=compiler_key)
            if command.get("error"):
                item["error"] = command["error"]
            elif command["timed_out"] or command["returncode"] != 0:
                item.update(status="failed", error="Build timed out" if command["timed_out"]
                            else "Make returned a nonzero exit code")
            else:
                try:
                    item["binary"] = {"path": str(binary), "sha256": sha256(binary),
                                      "size_bytes": binary.stat().st_size, "elf": elf_info(binary)}
                    item["status"] = "passed"
                except (OSError, ValueError) as exc:
                    item.update(status="failed", error=f"Build artifact validation: {exc}")
        if item["command"] is None:
            (logs / f"{target.id}.log").write_text(item["error"] + "\n")
        report["targets"].append(item)
    after = source_snapshot(source, targets)
    report["source"]["inputs_unchanged_during_build"] = before == after
    if before != after:
        report["source"]["inputs_after_build"] = after
    statuses = [item["status"] for item in report["targets"]]
    report["status"] = ("error" if before != after or "error" in statuses else
                        "failed" if "failed" in statuses else "passed")
    report["finished_at"] = now()
    (out / "run.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "commands.jsonl").write_text("".join(json.dumps(c) + "\n" for c in commands))
    return report
