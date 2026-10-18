# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import signal
import time
import pytest

from tests.testlab.can import CanObserver, VCanCleanupError, VCanError, VCanLease
from tests.testlab.contracts import CONTRACT, END, FIRST, require_frame
from tests.testlab.process import ManagedProcess

pytestmark = pytest.mark.can


@pytest.mark.parametrize("variant", ["c", "cpp", "python"])
def test_first_frame_and_controlled_shutdown(variant, can_programs, vcan, case_dir, can_timeout_scale):
    evidence = {"contract": CONTRACT, "kind": "sender", "scenarios": ["CAN-TX-01", "CAN-TX-02"],
                "variant": variant, "runner_uid": os.getuid(),
                "timeout_scale": can_timeout_scale,
                "expected_first": FIRST[variant].evidence(), "expected_end": END.evidence(),
                "python_sources": can_programs["python_sources"], "status": "failed"}
    observer = None
    try:
        observer = CanObserver(vcan.name)  # Bound BEFORE the sender starts.
        with observer:
            process = ManagedProcess([*can_programs["argv"][variant], vcan.name], log_dir=case_dir/"sender")
            with process:
                first = observer.receive(process, timeout=5*can_timeout_scale)
                require_frame(first, FIRST[variant])
                status = Path(f"/proc/{process.record['procfs_pgid']}/status").read_text()
                uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
                evidence["target_uids"] = [int(v) for v in uid_line.split()[1:]]
                assert evidence["target_uids"] == [os.getuid()]*4
                process.signal(signal.SIGINT)
                deadline = time.monotonic()+3*can_timeout_scale
                for _ in range(16):
                    frame = observer.receive(process, timeout=max(0.001, deadline-time.monotonic()))
                    if frame.can_id == END.can_id:
                        require_frame(frame, END)
                        break
                    assert frame.can_id == 0x123
                else:
                    raise AssertionError("END frame not received")
                assert process.wait(3*can_timeout_scale, phase="shutdown") == 0
            assert process.record["status"] == "passed", process.record
        evidence["status"] = "passed"
    finally:
        if observer is not None:
            observer.close()
        evidence.update(frames=observer.frames if observer else [], observer_closed=observer.closed if observer else True,
                        process_report=str(case_dir/"sender/process.json"))
        (case_dir/"case.json").write_text(json.dumps(evidence, indent=2)+"\n")


def test_owned_interface_is_removed_after_scenario_exception(case_dir):
    lease = VCanLease(log_dir=case_dir/"exception-lease")
    with pytest.raises(RuntimeError, match="controlled fixture failure"):
        with lease:
            raise RuntimeError("controlled fixture failure")
    assert lease.record["cleanup"]["owned_interface_removed"]
    assert lease.inspect() is None


def test_existing_interface_is_never_deleted_by_failed_lease(case_dir):
    with VCanLease(log_dir=case_dir/"owner") as owner:
        other = VCanLease(log_dir=case_dir/"non-owner", name=owner.name)
        with pytest.raises(VCanError, match="already exists"):
            with other:
                raise AssertionError("Must not adopt an existing interface")
        assert other.record["owned"] is False
        current = owner.inspect()
        assert current["ifindex"] == owner.index
        assert current["ifalias"] == owner.alias


def test_changed_ownership_token_prevents_deletion(case_dir):
    lease = VCanLease(log_dir=case_dir/"changed-owner")
    lease.__enter__()
    try:
        lease._run(["link", "set", "dev", lease.name, "alias", "external-owner"], privileged=True)
        with pytest.raises(VCanCleanupError, match="identity changed"):
            lease.close()
        assert lease.inspect()["ifalias"] == "external-owner"
        assert not lease.closed
    finally:
        # The test deliberately changed this token. Restore its own lease before
        # final cleanup; retain the initial refusal in the evidence record.
        lease._run(["link", "set", "dev", lease.name, "alias", lease.alias], privileged=True)
        lease.close()
    assert lease.record["cleanup"]["owned_interface_removed"]
    assert "identity changed" in lease.record["cleanup_error"]
