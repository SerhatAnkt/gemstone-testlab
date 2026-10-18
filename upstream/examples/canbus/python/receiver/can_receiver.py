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

import socket
import struct
from typing import Optional

# Constants
CAN_RAW = 1
CAN_MTU = 16
CAN_MAX_DLEN = 8


class CanReceiver:

    def __init__(self, interface_name: str):
        self.m_interface_name = interface_name
        self._socket: Optional[socket.socket] = None
        self._is_running = False

    def __del__(self):
        if self._socket:
            self._socket.close()

    def initialize(self) -> int:
        print(f"CAN Receiver starting on interface: {self.m_interface_name}")
        print("Press Ctrl+C to exit.\n")

        if self._setup_socket():
            return 1

        if self._bind_socket():
            return 1

        return 0

    def _setup_socket(self) -> int:
        try:
            self._socket = socket.socket(socket.PF_CAN, socket.SOCK_RAW, CAN_RAW)
            return 0
        except OSError as e:
            print(f"Error while opening socket: {e}")
            return 1

    def _bind_socket(self) -> int:
        try:
            interface_index = socket.if_nametoindex(self.m_interface_name)
            print(f"Interface {self.m_interface_name} at index {interface_index}")

            self._socket.bind((self.m_interface_name,))
            return 0
        except OSError as e:
            print(f"Error in socket bind: {e}")
            return 1

    def run(self):
        self._is_running = True

        while self._is_running:
            try:
                frame_data = self._socket.recv(CAN_MTU)

                if len(frame_data) < CAN_MTU:
                    print("Warning: incomplete CAN frame received")
                    continue

                can_id, data_len, data = struct.unpack("=IB3x8s", frame_data)
                actual_data = data[:data_len]

                self._process_frame(can_id, actual_data)

                if self._is_end_message(can_id, actual_data):
                    print("Received END message, stopping receiver")
                    break

            except OSError as e:
                print(f"Error reading CAN frame: {e}")
                break

    def stop(self):
        self._is_running = False

    def _process_frame(self, can_id: int, data: bytes):
        self._print_frame(can_id, data)

    def _print_frame(self, can_id: int, data: bytes):
        data_len = len(data)

        print(f"Received: ID=0x{can_id:X}, DLC={data_len}, Data=", end="")

        for byte in data:
            print(f"{byte:02X} ", end="")

        # Print as string if printable
        print("('", end="")
        for byte in data:
            if 32 <= byte <= 126:
                print(chr(byte), end="")
            else:
                print(".", end="")
        print("')")

    def _is_end_message(self, can_id: int, data: bytes) -> bool:
        return can_id == 0x124 and len(data) >= 3 and data[:3] == b"END"
