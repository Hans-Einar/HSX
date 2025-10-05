#include <stdint.h>

int main(void) {
    int a = 5;
    int b = 3;
    int eq = (a == b);
    int gt = (a > b);
    int lt = (a < b);
    return eq + (gt + gt) + (lt + lt + lt + lt);
}
