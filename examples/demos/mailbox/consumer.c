#include "hsx_mailbox.h"
#include "hsx_stdio.h"

#define BUFFER_SIZE 192

static char g_buffer[BUFFER_SIZE];
static int g_recv_info_raw[(sizeof(hsx_mailbox_recv_info) + sizeof(int) - 1) / sizeof(int)];

int main(void) {
    int handle = hsx_mailbox_open_app_demo();
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox consumer: failed to open target mailbox");
        return -handle;
    }

    hsx_stdio_puts("mailbox consumer listening on app:demo");

    hsx_mailbox_recv_info* info = (hsx_mailbox_recv_info*)g_recv_info_raw;

    while (1) {
        int status = hsx_mailbox_recv(handle, g_buffer, BUFFER_SIZE - 1,
                                      HSX_MBX_TIMEOUT_INFINITE, info);
        if (status < 0) {
            hsx_stdio_puts_err("mailbox consumer: receive error");
            continue;
        }
        int length = info->length;
        if (length == 0) {
            continue;
        }
        if (length >= BUFFER_SIZE) {
            length = BUFFER_SIZE - 1;
        }
        g_buffer[length] = '\0';
        hsx_stdio_puts(g_buffer);
    }

    return 0;
}
