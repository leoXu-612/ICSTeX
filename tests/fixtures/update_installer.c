// A local test process only: never linked into the shipped application.
#include <unistd.h>
int main(void) { char byte; while (read(0, &byte, 1) > 0) {} return 0; }
