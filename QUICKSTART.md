# Installation and testing

The tested system is Ubuntu 24.04 x86_64 with Python 3.12. An O1 board is not
required for these checks. Run the commands from the project folder.

## 1. Get the project

```sh
git clone https://github.com/SerhatAnkt/gemstone-testlab.git
cd gemstone-testlab
```

If you already have the project, open its folder and start at step 2.

## 2. Install the tools

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends -y build-essential python3 python3-venv git iproute2 kmod sudo ca-certificates
python3 --version
python3 -m venv .venv-testlab
.venv-testlab/bin/python -m pip install --require-hashes -r tests/requirements-serial.txt
```

Check that Python is version 3.12. The requirements file includes the packages
for all tests. Package versions and file hashes are fixed in the lock files.

## 3. Run the host and serial tests

```sh
.venv-testlab/bin/python -m tests.testlab ci --profile host --output artifacts/first-host
.venv-testlab/bin/python -m tests.testlab ci --profile serial --source-profile proposed-fixes --output artifacts/first-serial
```

The expected result is 66 host tests and 45 serial tests passing. Neither
command needs `sudo`.

`proposed-fixes` applies the fixes to a separate copy of the examples. It does
not change `upstream/examples/`. Testing the original serial code with
`--source-profile working-tree` is expected to fail 11 tests.

Use a new output folder for every run. The tools will not overwrite an old
report. Each folder has `ci.json`, `junit.xml`, and logs.

## 4. Run the CAN tests

CAN tests need the Linux `vcan` module and permission to create network
interfaces. Run the tests as your normal user. Only the network setup uses
`sudo`.

```sh
sudo -v
sudo -n modprobe vcan
.venv-testlab/bin/python -m tests.testlab ci --profile can --source-profile proposed-fixes --output artifacts/first-can
```

The expected result is 36 passing tests. The tests create their own temporary
interfaces and remove them when done. You do not need to create `vcan0`.
Your sudo session must stay valid while the tests run.

If `modprobe` says the module is missing, install the modules for your exact
kernel version. On Ubuntu, `vcan` may be in the matching
`linux-modules-extra-$(uname -r)` package. A container may also block network
setup. Installing Python packages will not fix that permission issue.

There is also a [Linux VM option](docs/VM_REPRODUCTION.md). The full VM test
runner works from a source ZIP, not from a Git checkout. For a Git checkout,
use native Linux CAN tests or GitHub Actions.

## 5. Build for ARM64

```sh
python3 -m tests.testlab toolchain --output build/gemstone-sdk
python3 -m tests.testlab ci --profile aarch64 --toolchain-root build/gemstone-sdk --output artifacts/first-aarch64
```

The first command downloads the official Gemstone SDK v1.0.6, about 299 MB.
It checks the file size and hash before setup. Keep a few GB of free disk space.
Install the SDK once, then reuse the same folder for later builds.

The second command builds six ARM64 programs and checks their ELF files.
It does not run the programs. See the [cross-build notes](docs/WP08_CROSS_BUILD.md)
for more detail.

## Run all four groups

After setup, the SDK, and CAN access are ready:

```sh
sudo -v
.venv-testlab/bin/python tools/run_release.py --source-profile proposed-fixes --toolchain-root build/gemstone-sdk --output artifacts/release-first
```

This runs host, serial, CAN, and ARM64 checks. It then checks that their reports
use the same source and test code. Missing tools, skipped required tests, or
changed reports cause a failure.

The final result is in `release.json` and `acceptance.json` inside the output
folder. Exit codes are `0` for success, `1` for a failed check, and `2` for a
setup or tool error.

## When a test fails

Read the logs in the output folder. A failed test prints a `TestLab reproduce:`
command. Use it in the same Python environment and with the same test code to
run that case again. See the [report notes](docs/WP07_REPORTING.md).

For small fixes and before/after checks, see [CONTRIBUTING.md](CONTRIBUTING.md).
You can also [export a source ZIP](docs/WP10_DELIVERY.md).
