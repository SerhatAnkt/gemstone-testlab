# Gemstone TestLab

[![Tests](https://github.com/SerhatAnkt/gemstone-testlab/actions/workflows/testlab.yml/badge.svg)](https://github.com/SerhatAnkt/gemstone-testlab/actions/workflows/testlab.yml)

Tests for the T3 Gemstone Linux examples, without an O1 board.

I started this project because I wanted to work on Gemstone before getting the
board. The idea is simple: run the examples on a Linux computer, send data to
them, and check the result. This helps find software bugs early.

## What it does

- Builds the C and C++ examples.
- Tests CAN messages with `vcan`, a virtual CAN interface in Linux.
- Tests serial data with PTYs, which act like serial ports in software.
- Checks bad input, timeouts, and program exit.
- Saves logs and test reports. Failed tests can be run again from a report.
- Builds ARM64 programs with the Gemstone SDK.

The tests cover the C, C++, and Python CAN and serial examples. GitHub Actions
runs them on each push and pull request.

## Try it

Use Ubuntu 24.04 and Python 3.12. Start with the
[setup guide](QUICKSTART.md), then run the host tests:

```sh
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/first-host
```

This builds six programs and runs 66 tests. It does not need a board or CAN
access. Use a new output folder each time.

## Test results

| Group | Passed |
| --- | --- |
| Host tests | 66 |
| Serial tests | 45 |
| CAN tests | 36 |
| ARM64 builds | 6 |

These results come from a [successful GitHub Actions run](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890).
The CAN and serial tests use copies with the proposed fixes. The original
example files stay unchanged. See [test results](RESULTS.md) for details.

## What still needs a board

PTY and vcan tests check software behavior. They do not check wires, voltage,
real baud rate, or CAN bus timing. The ARM64 programs have been built, but have
not been run on an O1 board.

## Next steps

- Run the full test suite ten times in a row and check the results.
- Check the five proposed fixes against the latest Gemstone examples.
- Prepare small pull requests for the fixes.
- Add tests on a real O1 board when one is available.

## More

- [Setup and commands](QUICKSTART.md)
- [Contributing](CONTRIBUTING.md) and [proposed fixes](contributions/README.md)
- [Test results](RESULTS.md) and [earlier notes in Turkish](docs/DEVELOPMENT_LOG.md)
- [Original examples](https://github.com/t3gemstone/examples/tree/2619a7584d39203a057abc08ab7c6698dc476868)

This is an independent project. It is not an official T3 Gemstone tool.
License: [Apache-2.0](LICENSE). Source credits are in [NOTICE](NOTICE).
