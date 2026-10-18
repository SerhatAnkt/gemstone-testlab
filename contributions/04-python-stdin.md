# serial/python: read stdin without buffering in the select loop

Burst console input can remain in Python's buffered stdin reader. `select`
monitors the kernel descriptor, while `sys.stdin.buffer.read(1)` can read ahead
into a userspace buffer. After the first byte, the next `select` may wait for
new descriptor activity even though buffered bytes remain. Real PTY burst and
fragmented-transfer cases reach their software deadline with partial output.

Read from the same descriptor with `os.read(stdin_fd, 1)`. This preserves the
existing byte-at-a-time processing without adding threads or a protocol.
Only `serial/python/serial_terminal.py` changes in
`patches/0004-serial-python-read-unbuffered-stdin.patch`.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 04 --output artifacts/pr04-first
```

Validation scope: three focused baseline call failures, then three passes
with this patch alone. Attach real before/after JSON/JUnit, partial byte logs,
and timeout records. The application was already launched with `-u`; that
option did not resolve the observed stdin buffering issue. The scenario
deadline is a test bound, not a real-time performance claim.

Base: `2619a7584d39203a057abc08ab7c6698dc476868`. Verify against the target branch
before submission. This draft has not been submitted. No O1 runtime claim is made.
