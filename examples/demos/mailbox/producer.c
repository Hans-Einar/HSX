#include "hsx_mailbox.h"
#include "hsx_stdio.h"
#include "procon.h"

#define BUFFER_SIZE 192

static char g_buffer[BUFFER_SIZE];

static int trim_line(char* buffer, int length) {
    int trimmed = length;
    while (trimmed > 0) {
        char ch = buffer[trimmed - 1];
        if (ch == '\n' || ch == '\r' || ch == '\0') {
            --trimmed;
            continue;
        }
        break;
    }
    buffer[trimmed] = '\0';
    return trimmed;
}

static int is_exit_command(const char* data, int length) {
    static const char kExit[] = "exit";
    if (length != 4) {
        return 0;
    }
    for (int i = 0; i < 4; ++i) {
        if (data[i] != kExit[i]) {
            return 0;
        }
    }
    return 1;
}

int main(void) {
    int stdin_handle = hsx_mailbox_open_stdin();
    if (stdin_handle < 0) {
        hsx_stdio_puts_err("mailbox producer: failed to open stdin mailbox");
        return -stdin_handle;
    }

    int handle = hsx_mailbox_open(PROCON_MAILBOX_TARGET, 0);
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox producer: failed to open target mailbox");
        hsx_mailbox_close(stdin_handle);
        return -handle;
    }

    hsx_stdio_puts("mailbox producer ready: send data via shell stdin");

    while (1) {
        int length = hsx_mailbox_recv_basic(stdin_handle, g_buffer, BUFFER_SIZE - 1);
        if (length < 0) {
            hsx_stdio_puts_err("mailbox producer: stdin read error");
            continue;
        }
        if (length <= 0) {
            continue;
        }
        if (length >= BUFFER_SIZE) {
            length = BUFFER_SIZE - 1;
        }
        g_buffer[length] = '\0';
        int payload_length = trim_line(g_buffer, length);
        if (payload_length == 0) {
            continue;
        }
        int rc = hsx_mailbox_send_basic(handle, g_buffer, payload_length);
        if (rc < 0) {
            hsx_stdio_puts_err("mailbox producer: send failed");
            continue;
        }
        if (is_exit_command(g_buffer, payload_length)) {
            hsx_stdio_puts("mailbox producer: exit requested");
            break;
        }
    }

    hsx_mailbox_close(handle);
    hsx_mailbox_close(stdin_handle);
    return 0;
}
