# Gemstone TestLab

[![Tests](https://github.com/SerhatAnkt/gemstone-testlab/actions/workflows/testlab.yml/badge.svg)](https://github.com/SerhatAnkt/gemstone-testlab/actions/workflows/testlab.yml)

CAN and serial tests for the T3 Gemstone Linux examples.

Gemstone TestLab helps developers check the examples on a Linux computer before
testing them on an O1 board. It builds the programs, sends test data, and checks
the output. The tests cover examples written in C, C++, and Python.

The goal is to find software bugs early and make changes easier to test.
Developers can check a fix, compare results, and share logs without needing the
board for every step. GitHub Actions runs the checks on each push and pull
request.

## Test coverage

| Group | What it checks | Tests or builds |
| --- | --- | --- |
| Host | Build tools, process control, reports, and error handling | 66 tests |
| Serial | Data sent and received, input errors, and program exit | 45 tests |
| CAN | Message IDs, data length, data bytes, and error cases | 36 tests |
| ARM64 | C/C++ builds with the Gemstone SDK and ELF file checks | 6 builds |

Serial tests use Linux PTYs, which provide terminal connections in software.
CAN tests use `vcan`, a virtual CAN interface supported by Linux SocketCAN.
Both let the real example programs send and receive data on the test computer.

## Test workflow

1. Build the selected examples in a separate output folder.
2. Start the programs with a PTY or a temporary vcan interface.
3. Send known data and compare the response with the expected bytes.
4. Save logs and JSON/JUnit reports, then close the test processes and interfaces.
5. Check that the four CI groups used the same source, test code, and commit.

For example, a serial test sends data containing both CR and LF bytes. It
checks that the program keeps those bytes unchanged. This test found an input
setting that changed CR to LF in the saved C and C++ examples. A separate patch
fixes the setting, and the same test checks the result.

Failed tests also save a command to run the same case again. This helps when
checking a bug or reviewing a proposed fix.

## Getting started

Use Ubuntu 24.04 and Python 3.12. Start with the
[setup guide](QUICKSTART.md), then run the host tests:

```sh
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/first-host
```

The host command builds six C/C++ programs and runs the host tests. It needs no
board or CAN access. Use a new output folder each time. The setup guide also
has commands for serial, CAN, ARM64, and a full run.

## Results and limits

All 147 tests and six ARM64 builds passed in a
[full GitHub Actions run](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890).
The CAN and serial groups use separate copies with the proposed fixes. The
original files in `upstream/examples/` stay unchanged. Five patches and their
before/after checks are listed in [proposed fixes](contributions/README.md).

These are Linux software tests. PTYs and vcan do not check wiring, voltage,
physical baud rate, or CAN bus timing. The ARM64 programs have been built but
have not been run on the O1 board. See [test results](RESULTS.md) for the full
scope and CI records.

## Planned work

- Run the full test suite ten times in a row and check the results.
- Check the five proposed fixes against the latest Gemstone examples.
- Submit the fixes as small pull requests after those checks.
- Add tests on a real O1 board when one is available.

## Documentation

- [Setup and commands](QUICKSTART.md)
- [Contributing](CONTRIBUTING.md) and [proposed fixes](contributions/README.md)
- [Test results](RESULTS.md) and [earlier notes in Turkish](docs/DEVELOPMENT_LOG.md)
- [Original examples](https://github.com/t3gemstone/examples/tree/2619a7584d39203a057abc08ab7c6698dc476868)

This is an independent project. It is not an official T3 Gemstone tool.
License: [Apache-2.0](LICENSE). Source credits are in [NOTICE](NOTICE).
