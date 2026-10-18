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
#include <cstdio>
#include <cstring>
#include <iostream>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

CanSender::CanSender(std::string_view interface_name) : m_interface_name {interface_name} {}

CanSender::~CanSender()
{
    if (m_socket >= 0)
    {
        close(m_socket);
        m_socket = -1;
    }
}

int CanSender::initialize()
{
    std::cout << "CAN Sender starting on interface: " << m_interface_name << std::endl;
    std::cout << "Press Ctrl+C to exit.\n" << std::endl;

    if (setup_socket() || bind_socket())
    {
        return 1;
    }

    return 0;
}

int CanSender::setup_socket()
{
    m_socket = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (m_socket < 0)
    {
        perror("Error while opening socket");
        return 1;
    }

    return 0;
}

int CanSender::bind_socket()
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

void CanSender::run()
{
    m_is_running = true;

    while (m_is_running)
    {
        send_data_frame();

        // Prevent overflow
        if (++m_frame_index > 999)
        {
            m_frame_index = 0;
        }

        sleep(1);
    }

    send_end_frame();
}

void CanSender::stop()
{
    m_is_running = false;
}

void CanSender::send_data_frame()
{
    can_frame frame;
    frame.can_id = 0x123;
    frame.can_dlc = 8;

    std::snprintf(reinterpret_cast<char*>(frame.data), sizeof(frame.data), "MSG_%03d", m_frame_index);

    std::cout << "Sending: ID=0x" << std::hex << std::uppercase << frame.can_id << std::dec
              << ", DLC=" << static_cast<int>(frame.can_dlc) << ", Data='" << reinterpret_cast<char*>(frame.data) << "'"
              << std::endl;

    if (send_frame(frame))
    {
        std::cerr << "Failed to send data frame" << std::endl;
    }
}

void CanSender::send_end_frame()
{
    can_frame frame;
    frame.can_id = 0x124;
    frame.can_dlc = 3;
    std::strcpy(reinterpret_cast<char*>(frame.data), "END");

    std::cout << "Sending END message: ID=0x" << std::hex << std::uppercase << frame.can_id << std::dec << ", Data='"
              << reinterpret_cast<char*>(frame.data) << "'" << std::endl;

    send_frame(frame);
}

int CanSender::send_frame(const can_frame& frame)
{
    ssize_t nbytes = write(m_socket, &frame, sizeof(can_frame));

    if (nbytes < 0)
    {
        perror("Error sending CAN frame");
        return 1;
    }

    if (nbytes < static_cast<ssize_t>(sizeof(can_frame)))
    {
        std::cout << "Warning: incomplete CAN frame sent" << std::endl;
        return 1;
    }

    return 0;
}
