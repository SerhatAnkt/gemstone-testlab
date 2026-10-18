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

#include "can_receiver.h"
#include <cstring>
#include <iostream>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

CanReceiver::CanReceiver(std::string_view interface_name) : m_interface_name {interface_name} {}

CanReceiver::~CanReceiver()
{
    if (m_socket >= 0)
    {
        close(m_socket);
        m_socket = -1;
    }
}

int CanReceiver::initialize()
{
    std::cout << "CAN Receiver starting on interface: " << m_interface_name << std::endl;
    std::cout << "Press Ctrl+C to exit.\n" << std::endl;

    if (setup_socket())
    {
        return 1;
    }

    if (bind_socket())
    {
        return 1;
    }

    return 0;
}

int CanReceiver::setup_socket()
{
    m_socket = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (m_socket < 0)
    {
        perror("Error while opening socket");
        return 1;
    }

    return 0;
}

int CanReceiver::bind_socket()
{
    struct ifreq ifr;
    struct sockaddr_can addr;

    std::strcpy(ifr.ifr_name, m_interface_name.c_str());
    if (ioctl(m_socket, SIOCGIFINDEX, &ifr) < 0)
    {
        perror("Error getting interface index");
        return 1;
    }

    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    std::cout << "Interface " << m_interface_name << " at index " << ifr.ifr_ifindex << std::endl;

    if (bind(m_socket, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0)
    {
        perror("Error in socket bind");
        return 1;
    }

    return 0;
}

void CanReceiver::run()
{
    m_is_running = true;

    while (m_is_running)
    {
        can_frame frame;
        ssize_t nbytes = read(m_socket, &frame, sizeof(can_frame));

        if (nbytes < 0)
        {
            perror("Error reading CAN frame");
            break;
        }

        if (nbytes < static_cast<ssize_t>(sizeof(can_frame)))
        {
            std::cout << "Warning: incomplete CAN frame received" << std::endl;
            continue;
        }

        process_frame(frame);

        if (is_end_message(frame))
        {
            std::cout << "Received END message, stopping receiver" << std::endl;
            break;
        }
    }
}

void CanReceiver::stop()
{
    m_is_running = false;
}

void CanReceiver::process_frame(const can_frame& frame)
{
    print_frame(frame);
}

void CanReceiver::print_frame(const can_frame& frame)
{
    std::cout << "Received: ID=0x" << std::hex << std::uppercase << frame.can_id << std::dec
              << ", DLC=" << static_cast<int>(frame.can_dlc) << ", Data=";

    // Print hex data
    for (int i = 0; i < frame.can_dlc; i++)
    {
        printf("%02X ", frame.data[i]);
    }

    // Print as string if printable
    std::cout << "('";
    for (int i = 0; i < frame.can_dlc; i++)
    {
        if (frame.data[i] >= 32 && frame.data[i] <= 126)
        {
            std::cout << static_cast<char>(frame.data[i]);
        }
        else
        {
            std::cout << ".";
        }
    }
    std::cout << "')" << std::endl;
}

bool CanReceiver::is_end_message(const can_frame& frame)
{
    return (frame.can_id == 0x124 && frame.can_dlc >= 3 &&
            std::strncmp(reinterpret_cast<const char*>(frame.data), "END", 3) == 0);
}
