// examples/c/hello.c — tiny C to LLVM IR demo for HSX pipeline
#include <stdint.h>
int add2(int a, int b) { return a + b; }
int main(void) {
    int x = 40, y = 2;
    int z = add2(x, y);
    return z; // expect 42
}
