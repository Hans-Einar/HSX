#include <stdint.h>

int phi_test(int cond, int a, int b) {
    if (cond) {
        return a;
    } else {
        return b;
    }
}
