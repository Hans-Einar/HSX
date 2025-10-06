int classify(int a, int b) {
    if (a < b) {
        return -1;
    }
    if (a == b) {
        return 0;
    }
    return 1;
}

int main(void) {
    return classify(2, 3);
}