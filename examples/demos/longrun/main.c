#include <stdint.h>

int main(void) {
    volatile uint32_t counter = 0;
    while (1) {
        counter++;
        if (counter == 0) {
            counter = 1;
        }
    }
}
