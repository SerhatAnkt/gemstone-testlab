# GitHub Actions records

| Run | Result | Notes |
| --- | --- | --- |
| [#1](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155256787) | Failed | Missing vcan module and a hidden file in the uploaded reports. [JSON record](39155256787.json) |
| [#2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) | All five jobs passed | 66 host, 45 serial, and 36 CAN tests; six ARM64 builds. Downloaded reports were also checked locally. [JSON record](39155570890.json) |
| [#3](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155974896) | All five jobs passed | A second passing run after the result notes were added. |

The JSON records save commit, job, and report IDs. Raw reports on GitHub are
kept for 14 days. These runs do not include tests on an O1 board.
