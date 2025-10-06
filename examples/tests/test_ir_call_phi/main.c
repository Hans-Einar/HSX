int helper(int value) {
    return value + 5;
}

static int phi_select(int cond, int a, int b) {
    return cond ? a : b;
}

int main(int cond) {
    int baseline = phi_select(cond, 3, 7);
    return helper(baseline + 2);
}