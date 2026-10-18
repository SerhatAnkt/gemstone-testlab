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

#ifndef CAN_SENDER_H
#define CAN_SENDER_H

#include <linux/can.h>
#include <linux/can/raw.h>
#include <string>

class CanSender
{
  public:
    CanSender(std::string_view interface_name);
    ~CanSender();

    int initialize();
    void run();
    void stop();

  private:
    std::string m_interface_name {};
    int m_socket {-1};
    volatile bool m_is_running {false};
    unsigned int m_frame_index {0};

    int setup_socket();
    int bind_socket();
    int send_frame(const can_frame& frame);
    void send_data_frame();
    void send_end_frame();
};

#endif // CAN_SENDER_H
