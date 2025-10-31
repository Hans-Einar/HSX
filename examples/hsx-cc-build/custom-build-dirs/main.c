/*
 * Custom Build Directory Example
 * Demonstrates organizing build outputs in custom locations
 *
 * Debug build:
 *   python3 ../../../python/hsx-cc-build.py --debug main.c -b output/debug -o app.hxe
 *
 * Release build:
 *   python3 ../../../python/hsx-cc-build.py main.c -b output/release -o app.hxe
 */

int calculate(int x, int y) {
    return (x * 2) + y;
}

int main() {
    int result = calculate(10, 5);
    return result;
}
