/*
 * Simple Hello World Example
 * Demonstrates basic hsx-cc-build.py usage with a single source file
 *
 * Build:
 *   python3 ../../../python/hsx-cc-build.py --debug main.c -o hello.hxe
 *
 * Expected outputs:
 *   build/debug/hello.hxe - Executable
 *   build/debug/hello.sym - Debug symbols
 *   build/debug/sources.json - Source mappings
 */

int main() {
    // Simple program that returns 42
    int result = 40 + 2;
    return result;
}
