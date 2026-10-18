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

import select
import sys
import termios
import tty
from typing import Optional

import serial


class SerialPort:
    SUPPORTED_BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

    def __init__(self):
        self._serial_connection: Optional[serial.Serial] = None

    def __del__(self):
        self.close()

    def configure(self, device: str, baud_rate: int) -> int:
        if baud_rate not in self.SUPPORTED_BAUD_RATES:
            print(f"Unsupported baud rate: {baud_rate}")
            print(f"Supported rates: {', '.join(map(str, self.SUPPORTED_BAUD_RATES))}")
            return 1

        try:
            self._serial_connection = serial.Serial(
                port=device,
                baudrate=baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.5,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
            return 0
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            return 1

    def close(self) -> None:
        if self._serial_connection and self._serial_connection.is_open:
            self._serial_connection.close()
            self._serial_connection = None

    def is_open(self) -> bool:
        return self._serial_connection is not None and self._serial_connection.is_open

    def get_fd(self) -> int:
        if self._serial_connection:
            return self._serial_connection.fileno()
        return -1

    def read(self, size: int = 1) -> bytes:
        if self._serial_connection:
            return self._serial_connection.read(size)
        return b""

    def write(self, data: bytes) -> int:
        if self._serial_connection:
            return self._serial_connection.write(data)
        return 0


class Terminal:
    def __init__(self):
        self._original_termios = None
        self.m_is_configured = False

    def __del__(self):
        self.restore()

    def configure(self) -> int:
        try:
            self._original_termios = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
            self.m_is_configured = True
            return 0
        except (termios.error, OSError) as e:
            print(f"Error setting terminal to raw mode: {e}")
            return 1

    def restore(self) -> None:
        if self.m_is_configured and self._original_termios:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, self._original_termios)
                self.m_is_configured = False
            except (termios.error, OSError):
                pass


class SerialTerminal:
    def __init__(self):
        self.m_serial_port = SerialPort()
        self.m_terminal = Terminal()
        self.m_is_running = False

    def __del__(self):
        self.m_serial_port.close()
        self.m_terminal.restore()
        print("\nShutting down...")

    def initialize(self, device: str, baud_rate: int) -> int:
        if self.m_serial_port.configure(device, baud_rate):
            return 1

        print("=" * 46)
        print(f"port is     : {device}")
        print(f"baudrate is : {baud_rate}")
        print()
        print("Serial terminal started. Press Ctrl+C to exit.")
        print("=" * 46)

        if self.m_terminal.configure():
            return 1

        return 0

    def run(self) -> None:
        if not self.m_serial_port.is_open():
            return

        self.m_is_running = True
        serial_fd = self.m_serial_port.get_fd()
        stdin_fd = sys.stdin.fileno()

        while self.m_is_running:
            try:
                # Wait for input from either keyboard or serial port
                ready, _, _ = select.select([stdin_fd, serial_fd], [], [])

                # Handle keyboard input
                if stdin_fd in ready:
                    try:
                        data = sys.stdin.buffer.read(1)
                        if data:
                            # Check for Ctrl+C (ASCII 3)
                            if b"\x03" in data:
                                self.m_is_running = False
                                return

                            # Send to serial port
                            self.m_serial_port.write(data)
                    except (OSError, IOError):
                        print("error")
                        break

                # Handle serial port input
                if serial_fd in ready:
                    try:
                        data = self.m_serial_port.read(1)
                        if data:
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                    except (OSError, IOError):
                        break

            except KeyboardInterrupt:
                self.m_is_running = False
                break
            except select.error:
                break

    def stop(self) -> None:
        self.m_is_running = False
