#include <stdint.h>

static int convert(_Float16 value) {
    return (int)value;
}

int main(void) {
    _Float16 sample = (_Float16)(-3.75f);
    return convert(sample);
}