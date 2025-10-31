/*
 * Makefile Project Example - Main
 */

extern int module1_func();
extern int module2_func();

int main() {
    int result1 = module1_func();
    int result2 = module2_func();
    return result1 + result2;
}
