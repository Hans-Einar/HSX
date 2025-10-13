#include "hsx_stdio.h"
#include "hsx_mailbox.h"

#define STDIO_READ_ATTEMPTS 3
#define STDIO_TIMEOUT_MS 10

static const char kHello[] = "hello from hsx stdio";
static const char kPrefix[] = "echo: ";
static char stdin_buffer[128];
static char stdout_buffer[(sizeof(kPrefix) - 1) + 128 + 1];

static void build_echo_line(int message_length) {
    int offset = 0;
    for (int i = 0; i < (int)(sizeof(kPrefix) - 1) && offset < (int)sizeof(stdout_buffer) - 1; ++i) {
        stdout_buffer[offset++] = kPrefix[i];
    }
    for (int i = 0; i < message_length && offset < (int)sizeof(stdout_buffer) - 1; ++i) {
        stdout_buffer[offset++] = stdin_buffer[i];
    }
    stdout_buffer[offset] = '\0';
}

int main(void) {
    hsx_stdio_puts(kHello);

    for (int attempt = 0; attempt < STDIO_READ_ATTEMPTS; ++attempt) {
        int length = hsx_stdio_read_basic(stdin_buffer, (int)(sizeof(stdin_buffer) - 1), STDIO_TIMEOUT_MS);
        if (length < 0) {
            hsx_stdio_puts_err("stdin read error");
            return -length;
        }
        if (length == 0) {
            continue;
        }
        if (length >= (int)sizeof(stdin_buffer)) {
            length = (int)sizeof(stdin_buffer) - 1;
        }
        stdin_buffer[length] = '\0';

        build_echo_line(length);
        hsx_stdio_puts(stdout_buffer);
        break;
    }

    return 0;
}
