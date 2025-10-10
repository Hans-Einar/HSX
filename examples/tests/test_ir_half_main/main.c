#include <stdint.h>

typedef __fp16 hsx_half_t;

typedef union {
    hsx_half_t value;
    uint16_t bits;
} hsx_half_bits_t;

int main(void) {
    hsx_half_t x = (hsx_half_t)1.5f;
    hsx_half_t y = (hsx_half_t)2.0f;
    hsx_half_bits_t out;
    out.value = (hsx_half_t)(((float)x) + ((float)y));
    return (int)out.bits;
}
