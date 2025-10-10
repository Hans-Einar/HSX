#include <stdint.h>

typedef __fp16 hsx_half_t;

static int convert(const hsx_half_t* value) {
    return (int)(*value);
}

int main(void) {
    hsx_half_t sample = (hsx_half_t)(-3.75f);
    return convert(&sample);
}
