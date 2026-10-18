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
import sys
import time
from typing import Optional

# Constants
CAN_RAW = 1
CAN_MTU = 16
CAN_MAX_DLEN = 8


class CanSender:
    def __init__(self, interface_name: str):
        self.m_interface_name = interface_name
        self._socket: Optional[socket.socket] = None
        self._is_running = False
        self.m_frame_index = 0

    def __del__(self):
        if self._socket:
            self._socket.close()

    def initialize(self) -> int:
        print(f"CAN Sender starting on interface: {self.m_interface_name}")
        print("Press Ctrl+C to exit.\n")

        if self._setup_socket() or self._bind_socket():
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
            # Get interface index
            interface_index = socket.if_nametoindex(self.m_interface_name)
            print(f"Interface {self.m_interface_name} at index {interface_index}")

            # Bind socket to CAN interface
            self._socket.bind((self.m_interface_name,))
            return 0
        except OSError as e:
            print(f"Error in socket bind: {e}")
            return 1

    def run(self):
        self._is_running = True

        while self._is_running:
            self._send_data_frame()

            # Prevent overflow
            self.m_frame_index += 1
            if self.m_frame_index > 999:
                self.m_frame_index = 0

            time.sleep(1)

        self._send_end_frame()

    def stop(self):
        self._is_running = False

    def _send_data_frame(self):
        can_id = 0x123
        data = f"MSG_{self.m_frame_index:03d}".encode("utf-8")
        data_len = len(data)

        print(f"Sending: ID=0x{can_id:X}, DLC={data_len}, Data='{data.decode()}'")

        if self._send_frame(can_id, data):
            print("Failed to send data frame", file=sys.stderr)

    def _send_end_frame(self):
        can_id = 0x124
        data = b"END"

        print(f"Sending END message: ID=0x{can_id:X}, Data='{data.decode()}'")
        self._send_frame(can_id, data)

    def _send_frame(self, can_id: int, data: bytes) -> int:
        try:
            # Pack CAN frame: ID (4 bytes) + DLC (1 byte) + padding (3 bytes) + data (8 bytes)
            data_len = len(data)
            padded_data = data.ljust(8, b"\x00")  # Pad data to 8 bytes

            frame = struct.pack("=IB3x8s", can_id, data_len, padded_data)

            bytes_sent = self._socket.send(frame)

            if bytes_sent < len(frame):
                print("Warning: incomplete CAN frame sent")
                return 1

            return 0
        except OSError as e:
            print(f"Error sending CAN frame: {e}")
            return 1
