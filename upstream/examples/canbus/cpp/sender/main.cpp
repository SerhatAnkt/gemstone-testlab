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

#include "can_sender.h"
#include <iostream>
#include <memory>
#include <signal.h>

// Global variables
static std::unique_ptr<CanSender> g_sender;

void signal_handler([[maybe_unused]] int sig)
{
    std::cout << "\nShutting down..." << std::endl;
    if (g_sender)
    {
        g_sender->stop();
    }
}

void print_usage(std::string_view program_name)
{
    std::cout << "Usage: " << program_name << " [OPTIONS]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  DEVICE    CAN bus interface name" << std::endl;
    std::cout << std::endl << "Example: " << program_name << " vcan0" << std::endl;
}

int main(int argc, char* argv[])
{
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    if (argc < 2)
    {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    std::string_view interface_name = argv[1];
    g_sender = std::make_unique<CanSender>(interface_name);

    if (g_sender->initialize())
    {
        std::cerr << "Failed to initialize CAN sender" << std::endl;
        return EXIT_FAILURE;
    }

    g_sender->run();

    return EXIT_SUCCESS;
}
