/* SPDX-License-Identifier: Apache-2.0
 * Independent WP-01 SocketCAN observer. Does not link Gemstone application code.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static void print_frame(const struct can_frame *frame)
{
    printf("WP01_CAN_FRAME {\"can_id\":%u,\"length\":%u,\"data_hex\":\"",
           frame->can_id, frame->can_dlc);
    for (unsigned int i = 0; i < frame->can_dlc && i < CAN_MAX_DLEN; ++i)
        printf("%02x", frame->data[i]);
    puts("\"}");
    fflush(stdout);
}

static int receive_frame(int fd, struct can_frame *frame)
{
    ssize_t n = read(fd, frame, sizeof(*frame));
    if (n != (ssize_t)sizeof(*frame)) {
        perror("CAN receive");
        return -1;
    }
    print_frame(frame);
    return 0;
}

static int collect_child(pid_t child, int *status)
{
    const struct timespec delay = {.tv_sec = 0, .tv_nsec = 10000000};
    for (int i = 0; i < 300; ++i) {
        pid_t r = waitpid(child, status, WNOHANG);
        if (r == child)
            return 0;
        if (r < 0)
            return -1;
        nanosleep(&delay, NULL);
    }
    return -1;
}

int main(int argc, char **argv)
{
    int fd = -1;
    pid_t child = -1;
    int child_status = 0;
    const char *failure = NULL;
    bool first_ok = false, end_ok = false;
    struct can_frame frame = {0};
    const unsigned char expected_first[8] = {'M','S','G','_','0','0','0',0};
    if (argc != 4 || strlen(argv[1]) >= IFNAMSIZ) {
        fprintf(stderr, "Usage: %s INTERFACE SENDER_BINARY SENDER_LOG\n", argv[0]);
        return 2;
    }
    fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (fd < 0) {failure = "socket_open"; goto finish;}
    struct timeval timeout = {.tv_sec = 5, .tv_usec = 0};
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout))) {
        failure = "socket_timeout"; goto finish;
    }
    unsigned int index = if_nametoindex(argv[1]);
    if (!index) {failure = "interface_lookup"; goto finish;}
    struct sockaddr_can address = {.can_family = AF_CAN, .can_ifindex = (int)index};
    if (bind(fd, (struct sockaddr *)&address, sizeof(address))) {
        failure = "socket_bind"; goto finish;
    }
    child = fork();
    if (child < 0) {failure = "fork"; goto finish;}
    if (child == 0) {
        close(fd);
        int log_fd = open(argv[3], O_WRONLY | O_CREAT | O_TRUNC, 0600);
        if (log_fd < 0 || dup2(log_fd, STDOUT_FILENO) < 0 ||
            dup2(log_fd, STDERR_FILENO) < 0)
            _exit(126);
        close(log_fd);
        execl(argv[2], argv[2], argv[1], (char *)NULL);
        _exit(127);
    }
    if (receive_frame(fd, &frame)) {failure = "first_frame_timeout"; goto finish;}
    first_ok = frame.can_id == 0x123 && frame.can_dlc == 8 &&
               memcmp(frame.data, expected_first, 8) == 0;
    if (!first_ok) {failure = "first_frame_mismatch"; goto finish;}
    if (kill(child, SIGINT)) {failure = "sender_signal"; goto finish;}
    for (int i = 0; i < 8; ++i) {
        if (receive_frame(fd, &frame)) {failure = "end_frame_timeout"; goto finish;}
        if (frame.can_id == 0x124 && frame.can_dlc == 3 &&
            memcmp(frame.data, "END", 3) == 0) {
            end_ok = true;
            break;
        }
    }
    if (!end_ok) {failure = "end_frame_mismatch"; goto finish;}
    if (collect_child(child, &child_status)) {failure = "sender_exit_timeout"; goto finish;}
    child = -1;
    if (!WIFEXITED(child_status) || WEXITSTATUS(child_status) != 0) {
        failure = "sender_exit_status"; goto finish;
    }
finish:
    if (child > 0) {
        kill(child, SIGKILL);
        waitpid(child, &child_status, 0);
    }
    if (fd >= 0)
        close(fd);
    if (failure)
        printf("WP01_CAN_RESULT {\"status\":\"failed\",\"error\":\"%s\","
               "\"first_frame_verified\":%s,\"end_frame_verified\":%s}\n",
               failure, first_ok ? "true" : "false", end_ok ? "true" : "false");
    else
        puts("WP01_CAN_RESULT {\"status\":\"passed\",\"first_frame_verified\":true,"
             "\"end_frame_verified\":true,\"sender_exit_code\":0,\"observer_socket_closed\":true,"
             "\"sender_collected\":true}");
    return failure ? 1 : 0;
}

