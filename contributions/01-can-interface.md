# canbus/c: check SIOCGIFINDEX before binding the sender

When the requested CAN interface does not exist, the C sender ignores the
failed `SIOCGIFINDEX` call and uses an uninitialized interface index. In the
recorded Linux run it printed index zero, entered the transmit path, and
failed while writing a frame. The value of that uninitialized field is not
expected to be stable across environments.

Check the ioctl result, report the lookup error, close the socket, and return
`EXIT_FAILURE` before binding. The change is limited to
`canbus/c/sender/main.c` in
`patches/0001-can-c-sender-check-interface-index.patch`.

The focused regression requests an absent interface and requires rejection
before the index or send loop is used. The independent normal sender/receiver
contract is covered separately by the full CAN suite.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 01 --output artifacts/pr01-first
```

Validation scope: one focused baseline failure, followed by one passing case
with this patch alone; Linux x86_64, runner UID 1000. For a host without CAN
privileges, use the documented `--can-backend vm` options. Attach the actual
`contributions.json`, baseline/fixed JSON/JUnit, and relevant logs. Full local
CI evidence is separate from this focused check.

Base: `2619a7584d39203a057abc08ab7c6698dc476868`. Verify against the target branch
before submission. This draft has not been submitted. No physical CAN, O1, or
ARM64 runtime validation is claimed.
