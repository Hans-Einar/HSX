#include <stdint.h>

static int use_val(int x) {
    return x + 1;
}

int half_ops(_Float16 a, _Float16 b) {
    _Float16 sum = a + b;
    _Float16 prod = a * b;
    _Float16 mix = sum + prod;
    return use_val((int)mix);
}
