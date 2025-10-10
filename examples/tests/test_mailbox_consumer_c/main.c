#include "hsx_mailbox.h"
#include "hsx_stdio.h"

static char inbox_buffer[64];

static void clear_buffer(void) {
    for (int i = 0; i < (int)sizeof(inbox_buffer); ++i) {
        inbox_buffer[i] = '\0';
    }
}

int main(void) {
    clear_buffer();

    int handle = hsx_mailbox_open_app_demo();
    if (handle < 0) {
        return -handle;
    }

    int length = hsx_mailbox_recv_basic(handle, inbox_buffer, (int)(sizeof(inbox_buffer) - 1));
    if (length < 0) {
        hsx_mailbox_close(handle);
        return -length;
    }

    if (length >= (int)(sizeof(inbox_buffer))) {
        length = (int)sizeof(inbox_buffer) - 1;
    }
    inbox_buffer[length] = '\0';

    hsx_stdio_puts("mailbox consumer received:");
    hsx_stdio_puts(inbox_buffer);

    int close_rc = hsx_mailbox_close(handle);
    if (close_rc < 0) {
        return -close_rc;
    }

    return 0;
}
