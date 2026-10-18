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

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

// Global variables
static int g_sock;

void signal_handler(__attribute__((unused)) int sig)
{
    printf("\nShutting down...\n");
    // Trigger cleanup
    exit(0);
}

void cleanup()
{
    close(g_sock);
}

void print_usage(const char* program_name)
{
    printf("Usage: %s [OPTIONS]\n", program_name);
    printf("Options:\n");
    printf("  DEVICE    CAN bus interface name\n");
    printf("\nExample: %s vcan0\n", program_name);
}

int main(int argc, char* argv[])
{
    ssize_t nbytes;
    struct sockaddr_can addr;
    struct can_frame frame;
    struct ifreq ifr;
    const char* ifname;

    atexit(cleanup);
    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    if (argc < 2)
    {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }
    ifname = argv[1];

    printf("CAN Receiver starting on interface: %s\n", ifname);
    printf("Press Ctrl+C to exit.\n\n");

    if ((g_sock = socket(PF_CAN, SOCK_RAW, CAN_RAW)) < 0)
    {
        perror("Error while opening socket");
        return EXIT_FAILURE;
    }

    strcpy(ifr.ifr_name, ifname);
    if (ioctl(g_sock, SIOCGIFINDEX, &ifr) < 0)
    {
        perror("Error getting interface index");
        return EXIT_FAILURE;
    }

    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;

    printf("Interface %s at index %d\n", ifname, ifr.ifr_ifindex);

    if (bind(g_sock, (struct sockaddr*)&addr, sizeof(addr)) < 0)
    {
        perror("Error in socket bind");
        return EXIT_FAILURE;
    }

    while (1)
    {
        nbytes = read(g_sock, &frame, sizeof(struct can_frame));

        if (nbytes < 0)
        {
            perror("Error reading CAN frame");
            break;
        }

        if (nbytes < (ssize_t)sizeof(struct can_frame))
        {
            printf("Warning: incomplete CAN frame received\n");
            continue;
        }

        printf("Received: ID=0x%03X, DLC=%d, Data=", frame.can_id, frame.can_dlc);

        for (int i = 0; i < frame.can_dlc; i++)
        {
            printf("%02X ", frame.data[i]);
        }

        // Also try to print as string if printable
        printf("('");
        for (int i = 0; i < frame.can_dlc; i++)
        {
            if (frame.data[i] >= 32 && frame.data[i] <= 126)
            {
                printf("%c", frame.data[i]);
            }
            else
            {
                printf(".");
            }
        }
        printf("')\n");

        // Check for END message
        if (frame.can_id == 0x124 && frame.can_dlc >= 3 && strncmp((char*)frame.data, "END", 3) == 0)
        {
            printf("Received END message, stopping receiver\n");
            break;
        }
    }

    return EXIT_SUCCESS;
}
