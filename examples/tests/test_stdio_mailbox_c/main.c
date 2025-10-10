#include "hsx_mailbox.h"
#include "hsx_stdio.h"

#define STDIO_TIMEOUT HSX_MBX_TIMEOUT_INFINITE

static const char kHello[] = "hello from hsx stdio";
static const char kPrefix[] = "echo: ";
static char stdin_buffer[64];

int main(void) {
    hsx_stdio_puts(kHello);

    int length = hsx_stdio_read_basic(stdin_buffer, (int)(sizeof(stdin_buffer) - 1), STDIO_TIMEOUT);
    if (length < 0) {
        return -length;
    }

    if (length >= (int)(sizeof(stdin_buffer))) {
        length = (int)(sizeof(stdin_buffer) - 1);
    }
    stdin_buffer[length] = '\0';

    hsx_stdio_puts(kPrefix);
    hsx_stdio_puts(stdin_buffer);

    return 0;
}
