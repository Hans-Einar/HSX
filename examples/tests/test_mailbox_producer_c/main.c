#include "hsx_mailbox.h"

static const char kTargetMailbox[] = "app:procon";
static const char kMessage[] = "ping from producer";

int main(void) {
    int handle = hsx_mailbox_open(kTargetMailbox, 0);
    if (handle < 0) {
        return -handle;
    }

    int rc = hsx_mailbox_send_basic(handle, kMessage, (int)(sizeof(kMessage) - 1));
    if (rc < 0) {
        hsx_mailbox_close(handle);
        return -rc;
    }

    int close_rc = hsx_mailbox_close(handle);
    if (close_rc < 0) {
        return -close_rc;
    }

    return 0;
}
