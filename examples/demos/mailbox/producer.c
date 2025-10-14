#include "hsx_mailbox.h"
#include "hsx_stdio.h"

#define BUFFER_SIZE 192

static char g_buffer[BUFFER_SIZE];
static int g_stdin_info_raw[(sizeof(hsx_mailbox_recv_info) + sizeof(int) - 1) / sizeof(int)];

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

int main(void) {
    int stdin_handle = hsx_mailbox_open_stdin();
    if (stdin_handle < 0) {
        hsx_stdio_puts_err("mailbox producer: failed to open stdin mailbox");
        return -stdin_handle;
    }

    int handle = hsx_mailbox_open_app_demo();
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox producer: failed to open target mailbox");
        hsx_mailbox_close(stdin_handle);
        return -handle;
    }

    hsx_stdio_puts("mailbox producer ready: send data via shell stdin");

    hsx_mailbox_recv_info* stdin_info = (hsx_mailbox_recv_info*)g_stdin_info_raw;

    while (1) {
        int status = hsx_mailbox_recv(stdin_handle, g_buffer, BUFFER_SIZE - 1,
                                      HSX_MBX_TIMEOUT_INFINITE, stdin_info);
        if (status < 0) {
            hsx_stdio_puts_err("mailbox producer: stdin read error");
            continue;
        }
        int length = stdin_info->length;
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
        }
    }

    return 0;
}
