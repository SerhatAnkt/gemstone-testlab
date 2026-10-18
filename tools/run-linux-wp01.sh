#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Use an ordinary Linux host/VM. Only module/link operations use sudo.
set -eu
BASE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=${1:-"$BASE/artifacts/linux-wp01"}
mkdir -p "$OUT"
OUT=$(CDPATH= cd -- "$OUT" && pwd)
exec >"$OUT/runner.log" 2>&1
created=0
iface="gtl$$"
privileged() {
    if [ "$(id -u)" = 0 ]; then
        "$@"
    else
        sudo -n "$@"
    fi
}
finish() {
    rc=$?
    trap - EXIT
    removed=true
    if [ "$created" = 1 ]; then
        if ! privileged ip link del dev "$iface"; then
            removed=false
            rc=1
        elif ip link show dev "$iface" >/dev/null 2>&1; then
            removed=false
            rc=1
        fi
    fi
    printf '{"exit_code":%s,"interface":"%s","interface_created":%s,"interface_removed":%s}\n' \
        "$rc" "$iface" "$([ "$created" = 1 ] && echo true || echo false)" "$removed" \
        >"$OUT/runner-cleanup.json"
    printf 'WP-01 exit=%s; report directory: %s\n' "$rc" "$OUT"
    exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

for tool in python3 gcc make ip id; do
    command -v "$tool" >/dev/null 2>&1 || { echo "Missing prerequisite: $tool"; exit 2; }
done
if [ "$(id -u)" != 0 ]; then
    command -v sudo >/dev/null 2>&1 || { echo 'Missing prerequisite: sudo'; exit 2; }
    sudo -n true || { echo 'vcan setup needs noninteractive sudo on this runner'; exit 2; }
fi
uname -a
gcc --version
make --version
python3 --version

# First try built-in/already loaded vcan; never alter an existing interface.
if ! privileged ip link add dev "$iface" type vcan; then
    command -v modprobe >/dev/null 2>&1 || { echo 'vcan unavailable and modprobe missing'; exit 2; }
    privileged modprobe vcan || { echo 'Could not load vcan; inspect kernel modules/capabilities'; exit 2; }
    privileged ip link add dev "$iface" type vcan || { echo 'Could not create vcan; CAP_NET_ADMIN is required'; exit 2; }
fi
created=1
privileged ip link set dev "$iface" up
ip -details link show dev "$iface"
python3 "$BASE/tools/wp01.py" doctor --output "$OUT/preflight"
python3 "$BASE/tools/wp01.py" all --interface "$iface" --output "$OUT/probes"
