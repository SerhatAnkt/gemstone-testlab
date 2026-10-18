#!.venv/bin/python3

# Copyright (c) 2025 by T3 Foundation. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#     https://docs.t3gemstone.org/en/license
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import argparse
import signal
import sys
from typing import Optional

from serial_terminal import SerialTerminal

g_serial_terminal: Optional["SerialTerminal"] = None


def signal_handler(sig, frame) -> None:
    global g_serial_terminal

    if g_serial_terminal:
        g_serial_terminal.stop()


def main():
    global g_serial_terminal

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        prog="serial.py",
        description="Serial Terminal Application",
        epilog="Supported baud rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600\n"
        "\nExample: serial.py -d /dev/ttyUSB0 -b 9600\n",
    )
    parser.add_argument("-d", "--device", required=True, help="Serial device path")
    parser.add_argument("-b", "--baud", type=int, required=True, help="Baud rate")

    parser.format_help()

    try:
        args = parser.parse_args()
    except SystemExit:
        return 1

    if args.baud <= 0:
        print(f"Invalid baud rate: {args.baud}")
        return 1

    g_serial_terminal = SerialTerminal()

    if g_serial_terminal.initialize(args.device, args.baud):
        return 1

    g_serial_terminal.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
