#include <stdint.h>

static _Float16 accumulate(_Float16 a, _Float16 b) {
    return a + b;
}

int main(void) {
    _Float16 x = (_Float16)1.5;
    _Float16 y = (_Float16)2.0;
    _Float16 z = accumulate(x, y);
    return (int)z;
}