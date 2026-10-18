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

#include "serial_terminal.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <errno.h>
#include <fcntl.h>
#include <iostream>
#include <sys/select.h>
#include <unistd.h>

SerialPort::SerialPort() {}

SerialPort::~SerialPort()
{
    if (m_serial_fd >= 0)
    {
        ::close(m_serial_fd);
        m_serial_fd = -1;
    }
}

int SerialPort::configure(const std::string& device, int baud_rate)
{
    struct termios tty;
    speed_t speed;

    speed = get_baud_rate(baud_rate);
    if (speed == B0)
    {
        return 1;
    }

    m_serial_fd = ::open(device.c_str(), O_RDWR | O_NOCTTY | O_SYNC);
    if (m_serial_fd < 0)
    {
        perror("Error opening serial port");
        return 1;
    }

    if (tcgetattr(m_serial_fd, &tty) != 0)
    {
        perror("Error getting serial port attributes");
        ::close(m_serial_fd);
        m_serial_fd = -1;
        return 1;
    }

    cfsetospeed(&tty, speed);
    cfsetispeed(&tty, speed);

    // Configure 8N1 (8 data bits, no parity, 1 stop bit)
    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8; // 8-bit chars
    tty.c_iflag &= ~IGNBRK;                     // disable break processing
    tty.c_lflag = 0;                            // no signaling chars, no echo,
                                                // no canonical processing
    tty.c_oflag = 0;                            // no remapping, no delays
    tty.c_cc[VMIN] = 0;                         // read doesn't block
    tty.c_cc[VTIME] = 5;                        // 0.5 seconds read timeout

    tty.c_iflag &= ~(IXON | IXOFF | IXANY); // shut off xon/xoff ctrl
    tty.c_cflag |= (CLOCAL | CREAD);        // ignore modem controls,
                                            // enable reading
    tty.c_cflag &= ~(PARENB | PARODD);      // shut off parity
    tty.c_cflag &= ~CSTOPB;                 // clear stop field
    tty.c_cflag &= ~CRTSCTS;                // no hardware flow control

    if (tcsetattr(m_serial_fd, TCSANOW, &tty) != 0)
    {
        perror("Error setting serial port attributes");
        ::close(m_serial_fd);
        m_serial_fd = -1;
        return 1;
    }

    return 0;
}

bool SerialPort::is_open() const
{
    return m_serial_fd >= 0;
}

int SerialPort::get_fd() const
{
    return m_serial_fd;
}

speed_t SerialPort::get_baud_rate(int baud) const
{
    switch (baud)
    {
    case 9600:
        return B9600;
    case 19200:
        return B19200;
    case 38400:
        return B38400;
    case 57600:
        return B57600;
    case 115200:
        return B115200;
    case 230400:
        return B230400;
    case 460800:
        return B460800;
    case 921600:
        return B921600;
    default:
        std::cout << "Unsupported baud rate: " << baud << std::endl;
        std::cout << "Supported rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600" << std::endl;
        return B0;
    }
}

Terminal::Terminal() {}

Terminal::~Terminal()
{
    restore();
}

int Terminal::configure()
{
    struct termios raw;

    if (tcgetattr(STDIN_FILENO, &m_original_termios) == -1)
    {
        perror("Error getting terminal attributes");
        return 1;
    }
    m_is_configured = true;

    raw = m_original_termios;
    raw.c_lflag &= ~(ECHO | ICANON | IEXTEN | ISIG);
    raw.c_iflag &= ~(BRKINT | ICRNL | INPCK | ISTRIP | IXON);
    raw.c_cflag |= CS8;
    raw.c_oflag &= ~OPOST;
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 1;

    if (tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw) == -1)
    {
        perror("Error setting terminal to raw mode");
        return 1;
    }

    return 0;
}

void Terminal::restore()
{
    if (m_is_configured)
    {
        tcsetattr(STDIN_FILENO, TCSANOW, &m_original_termios);
        m_is_configured = false;
    }
}

SerialTerminal::SerialTerminal()
{
}

SerialTerminal::~SerialTerminal()
{
    m_terminal.restore();
}

int SerialTerminal::initialize(const std::string& device, int baud_rate)
{
    if (m_serial_port.configure(device, baud_rate))
    {
        return 1;
    }

    std::cout << "==============================================" << std::endl;
    std::cout << "port is     : " << device << std::endl;
    std::cout << "baudrate is : " << baud_rate << std::endl << std::endl;
    std::cout << "Serial terminal started. Press Ctrl+C to exit." << std::endl;
    std::cout << "==============================================" << std::endl;

    if (m_terminal.configure())
    {
        return 1;
    }

    return 0;
}

void SerialTerminal::run()
{
    fd_set read_fds;
    int max_fd;
    char buffer[256];
    ssize_t bytes_read;

    if (!m_serial_port.is_open())
    {
        return;
    }

    m_is_running = true;
    max_fd = (m_serial_port.get_fd() > STDIN_FILENO) ? m_serial_port.get_fd() : STDIN_FILENO;

    while (m_is_running)
    {
        FD_ZERO(&read_fds);
        FD_SET(STDIN_FILENO, &read_fds);
        FD_SET(m_serial_port.get_fd(), &read_fds);

        // Wait for input from either keyboard or serial port
        if (select(max_fd + 1, &read_fds, nullptr, nullptr, nullptr) < 0)
        {
            if (errno == EINTR)
            {
                continue;
            }
            break;
        }

        // Handle keyboard input
        if (FD_ISSET(STDIN_FILENO, &read_fds))
        {
            bytes_read = read(STDIN_FILENO, buffer, sizeof(buffer) - 1);
            if (bytes_read > 0)
            {
                // Check for Ctrl+C (ASCII 3)
                for (int i = 0; i < bytes_read; i++)
                {
                    if (buffer[i] == 3)
                    {
                        m_is_running = false;
                        return;
                    }
                }

                // Send to serial port
                if (write(m_serial_port.get_fd(), buffer, bytes_read) != bytes_read)
                {
                    break;
                }
            }
        }

        // Handle serial port input
        if (FD_ISSET(m_serial_port.get_fd(), &read_fds))
        {
            bytes_read = read(m_serial_port.get_fd(), buffer, sizeof(buffer) - 1);
            if (bytes_read > 0)
            {
                if (write(STDOUT_FILENO, buffer, bytes_read) != bytes_read)
                {
                    break;
                }
            }
            else if (bytes_read < 0 && errno != EAGAIN)
            {
                break;
            }
        }
    }
}

void SerialTerminal::stop()
{
    m_is_running = false;
}
