#ifndef HSX_STDIO_API_H
#define HSX_STDIO_API_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int hsx_stdio_write(const void* data, int length, unsigned flags, unsigned channel);
int hsx_stdio_write_err(const void* data, int length, unsigned flags, unsigned channel);
int hsx_stdio_puts(const char* text);
int hsx_stdio_puts_err(const char* text);
int hsx_stdio_read_basic(void* buffer, int max_length, unsigned timeout);
int hsx_stdio_read(void* buffer, int max_length, unsigned timeout, int* out_length);

#ifdef __cplusplus
}
#endif

#endif /* HSX_STDIO_API_H */
