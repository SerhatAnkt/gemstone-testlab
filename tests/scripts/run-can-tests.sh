#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
testlab_python=${TESTLAB_PYTHON:-python3}
if [ "$(id -u)" = 0 ]; then
    echo 'Run CAN pytest as a normal user; only ip/modprobe operations use sudo.' >&2
    exit 2
fi
sudo -n modprobe vcan
cd "$BASE"
exec "$testlab_python" -m pytest tests/can "$@"
