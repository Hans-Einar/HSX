/*
 * Utility module - Helper functions
 */

// In a real application, this would output to console
// For HSX, we'll just store the value
static int last_result = 0;

void print_result(int value) {
    last_result = value;
    // Would normally print here
}

int get_last_result() {
    return last_result;
}
