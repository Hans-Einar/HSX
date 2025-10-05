#include <stdint.h>

static int callee(int a, int b) {
    return a + b;
}

int caller(int x) {
    return callee(x, 5);
}
