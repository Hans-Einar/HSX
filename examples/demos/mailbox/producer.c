#include "hsx_mailbox.h"
#include "hsx_stdio.h"

#define STDIN_TIMEOUT HSX_MBX_TIMEOUT_INFINITE
#define BUFFER_SIZE 192

static const char kMailboxTarget[] = "app:demos.echo";
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

int main(void) {
    int handle = hsx_mailbox_open(kMailboxTarget, HSX_MBX_MODE_WRONLY);
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox producer: failed to open target mailbox");
        return -handle;
    }

    hsx_stdio_puts("mailbox producer ready: send data via shell stdin");

    while (1) {
        int length = hsx_stdio_read_basic(g_buffer, BUFFER_SIZE - 1, STDIN_TIMEOUT);
        if (length < 0) {
            hsx_stdio_puts_err("mailbox producer: stdin read error");
            continue;
        }
        if (length == 0) {
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
