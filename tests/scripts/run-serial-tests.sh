#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
testlab_python=${TESTLAB_PYTHON:-python3}
cd "$BASE"
exec "$testlab_python" -W error::ResourceWarning -m pytest tests/serial "$@"
