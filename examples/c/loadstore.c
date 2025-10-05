#include <stdint.h>

int main(void) {
    volatile int *ptr = (int *)100;  // peker til adresse 100
    volatile int val = 99;           // verdi som skal lagres
    *ptr = val;                      // skriv verdien til RAM
    int tmp = *ptr;                  // les tilbake
    return tmp;                      // returner det som ble lest
}
