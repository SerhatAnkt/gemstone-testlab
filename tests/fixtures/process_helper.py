#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Small real processes for observable lifecycle and I/O regression tests."""
import os
import signal
import sys


def emit(channel, data):
    view = memoryview(data)
    while view:
        view = view[os.write(channel, view):]


mode = sys.argv[1]
if mode == "normal":
    emit(1, b"OUT\x00WP03\n")
    emit(2, b"ERR\x00WP03\n")
elif mode == "error":
    emit(2, b"intentional exit seven\n")
    sys.exit(7)
elif mode == "fragment":
    emit(1, b"READY_")
    emit(2, b"FIRST_PART_WRITTEN\n")
    assert os.read(0, 1) == b"G"
    emit(1, b"\x00WP03\n")
elif mode == "duplex":
    emit(2, b"E" * (256*1024))
    emit(1, b"READY\n")
    while True:
        data = os.read(0, 32768)
        if not data:
            break
        emit(1, data)
        emit(2, data)
elif mode == "overflow":
    emit(1, b"X" * (512*1024))
elif mode == "can_ready_after_trigger":
    assert os.read(0, 1) == b"G"
    emit(1, b"Received: ID=0x321, DLC=8, Data=47 54 4C 52 45 41 44 59 ('GTLREADY')\n")
elif mode in ("hang", "ignore_term", "graceful"):
    if mode == "ignore_term":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    elif mode == "graceful":
        def stop(signum, frame):
            emit(1, b"BYE\n")
            sys.exit(0)
        signal.signal(signal.SIGTERM, stop)
    emit(1, b"READY\n")
    while True:
        signal.pause()
elif mode in ("tree", "orphan"):
    ready_r, ready_w = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(ready_r)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        emit(ready_w, b"R")
        os.close(ready_w)
        while True:
            signal.pause()
    os.close(ready_w)
    assert os.read(ready_r, 1) == b"R"
    os.close(ready_r)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    emit(1, f"CHILD {child}\nREADY\n".encode())
    if mode == "orphan":
        sys.exit(0)
    while True:
        signal.pause()
else:
    raise SystemExit("Unknown helper mode")
