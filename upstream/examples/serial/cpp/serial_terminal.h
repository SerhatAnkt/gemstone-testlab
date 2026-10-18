// Copyright (c) 2025 by T3 Foundation. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//     https://docs.t3gemstone.org/en/license
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//
// SPDX-License-Identifier: Apache-2.0

#ifndef SERIAL_TERMINAL_H
#define SERIAL_TERMINAL_H

#include <string>
#include <termios.h>

class SerialPort
{
  public:
    SerialPort();
    ~SerialPort();

    SerialPort(const SerialPort&) = delete;
    SerialPort& operator=(const SerialPort&) = delete;

    int configure(const std::string& device, int baud_rate);
    bool is_open() const;
    int get_fd() const;

  private:
    speed_t get_baud_rate(int baud) const;

    int m_serial_fd {-1};
};

class Terminal
{
  public:
    Terminal();
    ~Terminal();

    Terminal(const Terminal&) = delete;
    Terminal& operator=(const Terminal&) = delete;

    int configure();
    void restore();

  private:
    struct termios m_original_termios
    {
    };
    bool m_is_configured {};
};

class SerialTerminal
{
  public:
    SerialTerminal();
    ~SerialTerminal();

    SerialTerminal(const SerialTerminal&) = delete;
    SerialTerminal& operator=(const SerialTerminal&) = delete;

    int initialize(const std::string& device, int baud_rate);
    void run();
    void stop();

  private:
    SerialPort m_serial_port {};
    Terminal m_terminal {};
    bool m_is_running {};
};

#endif // SERIAL_TERMINAL_H
