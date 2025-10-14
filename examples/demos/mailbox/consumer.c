#include "hsx_mailbox.h"
#include "hsx_stdio.h"

#define BUFFER_SIZE 192

static const char kMailboxTarget[] = "app:demos.echo";
static char g_buffer[BUFFER_SIZE];

int main(void) {
    int handle = hsx_mailbox_open(kMailboxTarget, HSX_MBX_MODE_RDONLY);
    if (handle < 0) {
        hsx_stdio_puts_err("mailbox consumer: failed to open target mailbox");
        return -handle;
    }

    hsx_stdio_puts("mailbox consumer listening on app:demos.echo");

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
    }

    return 0;
}
