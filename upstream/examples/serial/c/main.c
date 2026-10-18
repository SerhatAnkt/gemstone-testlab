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

#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

// Global variables
static int g_serial_fd = -1;
static struct termios g_original_termios;
static int g_is_terminal_configured = 0;

void signal_handler(__attribute__((unused)) int sig)
{
    printf("\nShutting down...\n");
    // Trigger cleanup
    exit(0);
}

void cleanup()
{
    if (g_serial_fd >= 0)
    {
        close(g_serial_fd);
    }
    if (g_is_terminal_configured)
    {
        tcsetattr(STDIN_FILENO, TCSANOW, &g_original_termios);
    }
}

speed_t get_baud_rate(int baud)
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
        printf("Unsupported baud rate: %d\n", baud);
        printf("Supported rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600\n");
        return B0;
    }
}

int configure_serial(const char* device, int baud_rate)
{
    struct termios tty;
    speed_t speed;

    speed = get_baud_rate(baud_rate);
    if (speed == B0)
    {
        return -1;
    }

    g_serial_fd = open(device, O_RDWR | O_NOCTTY | O_SYNC);
    if (g_serial_fd < 0)
    {
        perror("Error opening serial port");
        return -1;
    }

    if (tcgetattr(g_serial_fd, &tty) != 0)
    {
        perror("Error getting serial port attributes");
        close(g_serial_fd);
        return -1;
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

    if (tcsetattr(g_serial_fd, TCSANOW, &tty) != 0)
    {
        perror("Error setting serial port attributes");
        close(g_serial_fd);
        return -1;
    }

    return 0;
}

int configure_terminal()
{
    struct termios raw;

    if (tcgetattr(STDIN_FILENO, &g_original_termios) == -1)
    {
        perror("Error getting terminal attributes");
        return -1;
    }
    g_is_terminal_configured = 1;

    raw = g_original_termios;
    raw.c_lflag &= ~(ECHO | ICANON | IEXTEN | ISIG);
    raw.c_iflag &= ~(BRKINT | ICRNL | INPCK | ISTRIP | IXON);
    raw.c_cflag |= CS8;
    raw.c_oflag &= ~OPOST;
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 1;

    if (tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw) == -1)
    {
        perror("Error setting terminal to raw mode");
        return -1;
    }

    return 0;
}

void print_usage(const char* program_name)
{
    printf("Usage: %s [OPTIONS]\n", program_name);
    printf("Options:\n");
    printf("  -d, --device DEVICE    Serial device\n");
    printf("  -b, --baud RATE        Baud rate\n");
    printf("  -h, --help             Show this help message\n");
    printf("\nSupported baud rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600\n");
    printf("\nExample: %s -d /dev/ttyUSB0 -b 9600\n", program_name);
}

void run_terminal()
{
    fd_set read_fds;
    int max_fd;
    char buffer[256];
    ssize_t bytes_read;

    max_fd = (g_serial_fd > STDIN_FILENO) ? g_serial_fd : STDIN_FILENO;

    while (1)
    {
        FD_ZERO(&read_fds);
        FD_SET(STDIN_FILENO, &read_fds);
        FD_SET(g_serial_fd, &read_fds);

        // Wait for input from either keyboard or serial port
        if (select(max_fd + 1, &read_fds, NULL, NULL, NULL) < 0)
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
                        return;
                    }
                }

                // Send to serial port
                if (write(g_serial_fd, buffer, bytes_read) != bytes_read)
                {
                    break;
                }
            }
        }

        // Handle serial port input
        if (FD_ISSET(g_serial_fd, &read_fds))
        {
            bytes_read = read(g_serial_fd, buffer, sizeof(buffer) - 1);
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

int main(int argc, char* argv[])
{
    const char* device = NULL;
    int baud_rate = -1;
    int opt;
    static struct option long_options[] = {{"device", required_argument, 0, 'd'},
                                           {"baud", required_argument, 0, 'b'},
                                           {"help", no_argument, 0, 'h'},
                                           {0, 0, 0, 0}};

    atexit(cleanup);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    while ((opt = getopt_long(argc, argv, "d:b:h", long_options, NULL)) != -1)
    {
        switch (opt)
        {
        case 'd':
            device = optarg;
            break;
        case 'b':
            baud_rate = atoi(optarg);
            if (baud_rate <= 0)
            {
                printf("Invalid baud rate: %s\n", optarg);
                return EXIT_FAILURE;
            }
            else if (get_baud_rate(baud_rate) == B0)
            {
                return EXIT_FAILURE;
            }
            break;
        case 'h':
            print_usage(argv[0]);
            return EXIT_SUCCESS;
        default:
            print_usage(argv[0]);
            return EXIT_FAILURE;
        }
    }

    if (device == NULL || baud_rate == -1)
    {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    if (configure_serial(device, baud_rate) < 0)
    {
        return EXIT_FAILURE;
    }

    printf("==============================================\n");
    printf("port is     : %s\n", device);
    printf("baudrate is : %d\n\n", baud_rate);
    printf("Serial terminal started. Press Ctrl+C to exit.\n");
    printf("==============================================\n");

    if (configure_terminal() < 0)
    {
        return EXIT_FAILURE;
    }

    run_terminal();

    return EXIT_SUCCESS;
}
