# SPDX-License-Identifier: Apache-2.0
"""Controlled reporting regressions, selected explicitly; not device integration."""
from pathlib import Path
import pytest


@pytest.fixture
def setup_error():
    raise RuntimeError('controlled setup failure')


@pytest.fixture
def teardown_error():
    yield
    raise RuntimeError('controlled teardown failure')


def test_pass():
    assert 2+2 == 4


def test_call_failure():
    raise AssertionError('controlled call failure')


def test_setup_failure(setup_error):
    raise AssertionError('unreachable call')


def test_teardown_failure(teardown_error):
    assert True


@pytest.mark.serial
def test_required_skip():
    pytest.skip('controlled missing prerequisite')


def test_input_change(request):
    root = request.config.getoption('--source-root')
    assert root is not None
    path = Path(root)/'common.mk'
    path.write_bytes(path.read_bytes()+b'\n# controlled private input change\n')
