#include <stdint.h>

static const char msg[] = "OK";
volatile int idx = 0;

static int fetch_char(int offset) {
    return (int)(unsigned char)msg[offset];
}

int main(void) {
    int val = fetch_char(idx);
    return val;
}