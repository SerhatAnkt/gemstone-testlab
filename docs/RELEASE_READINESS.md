# Release status

This table tracks the checks for the first release. The code is on GitHub;
a tagged release has not been published yet.

| Item | Status |
| --- | --- |
| Host, serial, CAN, and ARM64 checks | Passed locally |
| GitHub Actions | All five jobs passed in [run #2](https://github.com/SerhatAnkt/gemstone-testlab/actions/runs/39155570890) |
| Clean source ZIP setup | Passed with a new Python environment and SDK |
| Ten full runs in a row | Still to do |
| Five fixes checked on the latest Gemstone code | Still to do |
| Fixes sent upstream | Not sent; drafts are ready |
| ARM64 programs run on a target device | Not done |
| Physical O1 and CAN/UART tests | Not done; need hardware |

Before the first release, complete the repeated runs and check the patches
against the latest Gemstone code. Board tests are a separate next step.

CAN and serial CI currently use `proposed-fixes`. If the fixes become part of
the source, change that setting to `working-tree` and run the tests again.

See [test results](../RESULTS.md) and [CI records](ci-runs/README.md).
