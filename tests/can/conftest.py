# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import sys
import pytest

from tests.testlab.build import build_targets, default_source_root, sha256, source_snapshot
from tests.testlab.targets import select_targets
from tests.testlab.can import VCanLease


@pytest.fixture(scope="session", autouse=True)
def nonroot_can_runner():
    if os.geteuid() == 0:
        pytest.fail("CAN pytest must run as a normal user; delegate only ip operations via sudo -n")


@pytest.fixture(scope="session")
def source_root(request):
    return (request.config.getoption("--source-root") or default_source_root()).resolve()


@pytest.fixture(scope="session")
def can_programs(request, source_root, evidence_root):
    ids = ["can.c.sender", "can.cpp.sender", "can.c.receiver", "can.cpp.receiver"]
    prebuilt = request.config.getoption("--can-prebuilt")
    if prebuilt:
        report = json.loads(prebuilt.read_text())
        actual = source_snapshot(source_root, select_targets(ids))["digest"]
        assert report["source_digest"] == actual, "Prebuilt binaries belong to different sources"
        binaries = report["binaries"]
        for name in ids:
            assert sha256(Path(binaries[name]["path"])) == binaries[name]["sha256"]
    else:
        report = build_targets(source_root=source_root, target_ids=ids, output_root=evidence_root/"builds")
        assert report["status"] == "passed", report
        binaries = {t["id"]: t["binary"] for t in report["targets"]}
    main = source_root/"canbus/python/sender/main.py"
    receiver = source_root/"canbus/python/receiver/main.py"
    python_files = (main, main.with_name("can_sender.py"), receiver, receiver.with_name("can_receiver.py"))
    assert all(p.is_file() for p in python_files)
    return {"argv": {"c": [binaries[ids[0]]["path"]], "cpp": [binaries[ids[1]]["path"]],
                     "python": [sys.executable, "-u", str(main)]},
            "receiver_argv": {"c": [binaries[ids[2]]["path"]], "cpp": [binaries[ids[3]]["path"]],
                              "python": [sys.executable, "-u", str(receiver)]},
            "python_sources": {str(p.relative_to(source_root)): sha256(p) for p in python_files}}


@pytest.fixture
def case_dir(case_evidence_dir):
    return case_evidence_dir


@pytest.fixture
def vcan(case_dir):
    with VCanLease(log_dir=case_dir/"vcan") as lease:
        yield lease
