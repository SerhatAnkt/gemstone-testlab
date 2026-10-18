# Contributing

Follow the [installation guide](QUICKSTART.md) and run the host and serial tests
before making changes. Keep each contribution focused on one problem. Include
a short description of the change and the test results.

## Report a bug

Include the command, what you expected, and what happened. Add your Linux and
Python versions, the source commit, and the relevant logs. Say whether you used
PTYs, vcan, an ARM64 build, or a real board.

## Change the test code

- Add a test for the behavior you changed.
- Keep logs, source hashes, and cleanup checks.
- Only remove processes and interfaces created by the test.
- Keep SDK files, wheels, binaries, and generated reports out of Git.
- Keep the SPDX license header in code files.

The required tests are listed in `tests/ci-contract.json`. If you rename or
remove one, update that list and explain why. Do not skip a required test to
get a green result.

Use `working-tree` to test your source changes. Use `proposed-fixes` when you
want the tools to apply the existing patches to a separate copy. If those
patches become part of the source, the CI setting will need to change too.

## Check a proposed fix

There are [five separate fixes](contributions/README.md). Each has a patch,
tests, and a draft pull request description. No pull request has been sent to
the Gemstone repository yet.

For example, check fix 02:

```sh
.venv-testlab/bin/python tools/check_contributions.py --entry 02 --output artifacts/fix02-first
```

This runs four selected tests on the original code, where they should fail.
It then applies only fix 02 to a copy and runs the tests again. All four should
pass. The original files stay unchanged.

To check all five fixes, with CAN access ready:

```sh
.venv-testlab/bin/python tools/check_contributions.py --output artifacts/fixes-first
```

Use a new output folder. The result is in `contributions.json`, with logs and
test reports. A setup error does not count as proof of a bug.

## Send a fix to Gemstone

First check that the bug still exists in the latest Gemstone code. The current
patches were tested on commit `2619a7584d39203a057abc08ab7c6698dc476868`.
Update the patch if needed, then run the tests again.

Keep each fix small. Include the command and the before/after results in the
pull request. Only claim board testing if you have tested it on a real board.

This project uses the [Apache-2.0 license](LICENSE). It is independent of the
official Gemstone project.
