#include <stdint.h>

extern int half_ops(_Float16 a, _Float16 b);

int main(void) {
    _Float16 a = (_Float16)1.5;
    _Float16 b = (_Float16)2.25;
    int r = half_ops(a, b);
    return r;
}
