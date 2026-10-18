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

import signal
import sys

from can_receiver import CanReceiver


def signal_handler(sig, frame):
    print("\nShutting down...")
    sys.exit(0)


def print_usage(program_name: str):
    print(f"Usage: {program_name} [OPTIONS]")
    print("Options:")
    print("  DEVICE    CAN bus interface name")
    print(f"\nExample: {program_name} vcan0")


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if len(sys.argv) < 2:
        print_usage(sys.argv[0])
        return 1

    interface_name = sys.argv[1]

    receiver = CanReceiver(interface_name)

    if receiver.initialize():
        print("Failed to initialize CAN receiver", file=sys.stderr)
        return 1

    receiver.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
