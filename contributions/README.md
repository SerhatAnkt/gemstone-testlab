# Proposed fixes

These five fixes are for Gemstone examples at commit
`2619a7584d39203a057abc08ab7c6698dc476868`.
They have not been sent upstream. Each patch works on its own.

| Fix | Problem | Selected tests | Draft description |
| --- | --- | --- | --- |
| 01 | C CAN sender does not check a failed interface lookup | 1 | [CAN interface](01-can-interface.md) |
| 02 | C/C++ serial programs change CR bytes to LF | 4 | [Raw serial input](02-serial-raw-input.md) |
| 03 | C/C++ serial programs accept `9600oops` as a baud value | 2 | [Baud input](03-serial-baud.md) |
| 04 | Python serial input can stay in a buffer | 3 | [Python input](04-python-stdin.md) |
| 05 | Python `--help` returns a failure code | 2 | [Help exit code](05-python-help.md) |

The patch files are in [patches/](../patches). Exact file names and test cases
are listed in [series.json](series.json).

The before/after check runs each patch separately: first on the original code,
then on a copy with that one fix. The selected tests must fail before the fix
and pass after it. Setup or cleanup errors do not count as proof of a bug.
The full CAN and serial suites also run with all the relevant fixes together.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for commands. Before opening a pull
request, check the latest Gemstone code and add the real test reports to the
draft description.
