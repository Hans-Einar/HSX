#include "hsx_mailbox.h"
#include "hsx_stdio.h"
#include "procon.h"

#define BUFFER_SIZE 192

static char g_buffer[BUFFER_SIZE];

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
    int bind_status = hsx_mailbox_bind(PROCON_MAILBOX_TARGET, PROCON_MAILBOX_CAPACITY, HSX_MBX_MODE_RDWR);
    if (bind_status < 0) {
        hsx_stdio_puts_err("mailbox consumer: failed to bind target mailbox");
        return -bind_status;
    }

    int handle = hsx_mailbox_open(PROCON_MAILBOX_TARGET, 0);
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox consumer: failed to open target mailbox");
        return -handle;
    }

    hsx_stdio_puts("mailbox consumer listening on " PROCON_MAILBOX_TARGET);

    while (1) {
        int length = hsx_mailbox_recv_basic(handle, g_buffer, BUFFER_SIZE - 1);
        if (length < 0) {
            hsx_stdio_puts_err("mailbox consumer: receive error");
            continue;
        }
        if (length == 0) {
            continue;
        }
        if (length >= BUFFER_SIZE) {
            length = BUFFER_SIZE - 1;
        }
        g_buffer[length] = '\0';
        hsx_stdio_puts(g_buffer);
        if (is_exit_command(g_buffer, length)) {
            hsx_stdio_puts("mailbox consumer: exit requested");
            break;
        }
    }

    hsx_mailbox_close(handle);
    return 0;
}
