# SPDX-License-Identifier: Apache-2.0
import math
from pathlib import Path
import pytest

pytest_plugins = ['tests.testlab.pytest_report']


def pytest_addoption(parser):
    group = parser.getgroup("testlab")
    group.addoption("--source-root", type=Path)
    group.addoption("--can-prebuilt", type=Path, help="Verified native binaries prepared by the VM host")
    group.addoption("--evidence-root", type=Path, default=Path("artifacts/pytest"))
    group.addoption("--timeout-scale", type=float, default=1.0,
                    help="Positive software-test budget multiplier; native Linux defaults to 1")


@pytest.fixture(scope="session")
def can_timeout_scale(request):
    value = request.config.getoption("--timeout-scale")
    if not math.isfinite(value) or value <= 0:
        pytest.fail("--timeout-scale must be finite and positive")
    return value


@pytest.fixture(scope="session")
def evidence_root(request):
    return request.config._testlab_reporter.root


@pytest.fixture
def case_evidence_dir(request):
    path = request.config._testlab_reporter.case_directory(request.node.nodeid)/'evidence'
    path.mkdir(parents=True, exist_ok=False)
    return path
