# serial/python: preserve argparse exit codes for help

The Python serial entry point catches every `SystemExit` from argument parsing
and returns 1. Consequently, both `-h` and `--help` print usage but report
failure. Invalid arguments must still return argparse's nonzero status.

Return `exc.code` from the caught `SystemExit`. Only `serial/python/main.py`
changes in `patches/0005-serial-python-preserve-argparse-exit-code.patch`.

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 05 --output artifacts/pr05-first
```

Validation scope: two focused baseline call failures, then two passes with
this patch alone. The tests require exit zero and usage/device/baud text.
Malformed and missing argument cases are checked separately by the full serial
suite. Attach the actual before/after JSON/JUnit and CLI stdout/stderr.

Base: `2619a7584d39203a057abc08ab7c6698dc476868`. Verify against the target branch
before submission. This draft has not been submitted. This is a host CLI
behavior correction; no board execution is required or claimed.
