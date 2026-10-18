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

#include <cstdlib>
#include <getopt.h>
#include <iostream>
#include <memory>
#include <signal.h>
#include <string>

// Global variables
static std::unique_ptr<SerialTerminal> g_serial_terminal {};

void signal_handler([[maybe_unused]] int sig)
{
    std::cout << "\nShutting down..." << std::endl;
    if (g_serial_terminal)
    {
        g_serial_terminal->stop();
    }
}

void print_usage(std::string_view program_name)
{
    std::cout << "Usage: " << program_name << " [OPTIONS]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -d, --device DEVICE    Serial device" << std::endl;
    std::cout << "  -b, --baud RATE        Baud rate" << std::endl;
    std::cout << "  -h, --help             Show this help message" << std::endl;
    std::cout << std::endl
              << "Supported baud rates: 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600" << std::endl;
    std::cout << std::endl << "Example: " << program_name << " -d /dev/ttyUSB0 -b 9600" << std::endl;
}

int main(int argc, char* argv[])
{
    std::string device;
    int baud_rate = -1;
    int opt;
    static struct option long_options[] = {{"device", required_argument, 0, 'd'},
                                           {"baud", required_argument, 0, 'b'},
                                           {"help", no_argument, 0, 'h'},
                                           {0, 0, 0, 0}};

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    while ((opt = getopt_long(argc, argv, "d:b:h", long_options, nullptr)) != -1)
    {
        switch (opt)
        {
        case 'd':
            device = optarg;
            break;
        case 'b':
            baud_rate = std::atoi(optarg);
            if (baud_rate <= 0)
            {
                std::cerr << "Invalid baud rate: " << optarg << std::endl;
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

    if (device.empty() || baud_rate == -1)
    {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    g_serial_terminal = std::make_unique<SerialTerminal>();

    if (g_serial_terminal->initialize(device, baud_rate))
    {
        return EXIT_FAILURE;
    }

    g_serial_terminal->run();

    return EXIT_SUCCESS;
}
