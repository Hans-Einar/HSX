/*
 * Multi-File Project Example - Main
 * Demonstrates building multiple source files together
 *
 * Build:
 *   python3 ../../../python/hsx-cc-build.py --debug main.c math.c utils.c -o calculator.hxe
 */

// External function declarations
extern int add(int a, int b);
extern int multiply(int a, int b);
extern void print_result(int value);

int main() {
    int x = 10;
    int y = 5;
    
    // Test addition
    int sum = add(x, y);
    print_result(sum);
    
    // Test multiplication
    int product = multiply(x, y);
    print_result(product);
    
    return 0;
}
