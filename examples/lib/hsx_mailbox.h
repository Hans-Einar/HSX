#ifndef HSX_MAILBOX_API_H
#define HSX_MAILBOX_API_H

#include "../../include/hsx_mailbox.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct hsx_mailbox_recv_info {
    int status;     /* raw status code from SVC */
    int length;     /* bytes copied into caller buffer */
    unsigned flags; /* mailbox flags from sender */
    unsigned channel;
    unsigned src_pid;
} hsx_mailbox_recv_info;

int hsx_mailbox_open(const char* target, unsigned flags);
int hsx_mailbox_close(int handle);
int hsx_mailbox_send(int handle, const void* data, int length, unsigned flags, unsigned channel);
int hsx_mailbox_recv(int handle, void* buffer, int max_len, unsigned timeout, hsx_mailbox_recv_info* out);
int hsx_mailbox_open_stdout(void);
int hsx_mailbox_open_stdin(void);
int hsx_mailbox_open_app_demo(void);
int hsx_mailbox_send_basic(int handle, const void* data, int length);
int hsx_mailbox_recv_basic(int handle, void* buffer, int max_len);

#ifdef __cplusplus
}
#endif

#endif /* HSX_MAILBOX_API_H */
