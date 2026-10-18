# Test results and known limits

The first full passing GitHub Actions run was on 18 October 2026:
[run #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890),
commit `b26d6eddb6da44d16dc0ab2dfe5af85c98166042`.
All five jobs passed. The downloaded reports were also checked locally.

| Check | Result |
| --- | --- |
| Host tests | 66 passed; six C/C++ programs built |
| Serial tests | 45 passed with Linux PTYs |
| CAN tests | 36 passed with Linux SocketCAN/vcan |
| ARM64 builds | Six AArch64 ELF files built with Gemstone SDK v1.0.6 |
| Final report check | All four groups used matching source, test code, and commit |

The serial and CAN tests used copies with the proposed fixes. The 27 original
files in `upstream/examples/` were not changed. Their source version is
`t3gemstone/examples@2619a7584d39203a057abc08ab7c6698dc476868`.

## Bugs and fixes

| Fix | Problem found in the saved source version |
| --- | --- |
| 01 | The C CAN sender uses an interface index after the lookup fails |
| 02 | The C/C++ serial programs change received CR bytes to LF |
| 03 | The C/C++ serial programs accept a baud value such as `9600oops` |
| 04 | The Python serial program can leave input waiting in a buffer |
| 05 | The Python serial program returns a failure code for `--help` |

Each patch was checked on its own. Across these checks, 12 selected test cases
failed before the fixes and passed after them. These are selected cases from
the full suite, not 12 extra tests. The original serial code failed 11 of the
45 serial tests.

The tests were also checked with deliberately broken data. A changed CAN
message length and a changed serial byte both caused test failures.
See the [patch list and draft descriptions](contributions/README.md).

## CI setup and fixes

[Run #1](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155256787)
failed because the runner was missing the `vcan` module. The report upload also
left out a hidden file that the final check needed.

The workflow now installs the matching kernel modules when needed and includes
hidden files from the test output folders. The tests were kept in place.
[Run #3](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155974896)
also passed all five jobs.

## Limits and next checks

The CAN and serial results are Linux software tests. There has been no O1 board
test, physical CAN/UART test, or ARM64 program run. The ten full runs in a row
are still planned. The fixes also need a check against the latest Gemstone code
before they are sent upstream.

## Records

- [GitHub Actions records](docs/ci-runs/README.md), including job and report IDs
- [Release checklist](docs/RELEASE_READINESS.md)
- [Earlier development notes in Turkish](docs/DEVELOPMENT_LOG.md)

Raw GitHub Actions reports are kept for 14 days. The small JSON summaries stay
in this repository. Older local report paths in the development notes belong
to the earlier full ZIP, not to this Git checkout.
