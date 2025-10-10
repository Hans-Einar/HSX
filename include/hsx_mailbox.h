#ifndef HSX_MAILBOX_H
#define HSX_MAILBOX_H

#include <stdint.h>

/*
 * HSX mailbox module (SVC 0x05) shared constants between the C executive and
 * Python prototype. The Python tooling scrapes these #define values to stay in
 * sync, so keep the simple literal forms.
 */

#define HSX_MBX_MODULE_ID 0x05

#define HSX_MBX_MAX_NAME_BYTES 32
#define HSX_MBX_DEFAULT_RING_CAPACITY 64
#define HSX_MBX_MAX_PREFIX_BYTES 8

#define HSX_MBX_TIMEOUT_POLL 0x0000
#define HSX_MBX_TIMEOUT_INFINITE 0xFFFF

#define HSX_MBX_NAMESPACE_PID 0x00
#define HSX_MBX_NAMESPACE_SVC 0x01
#define HSX_MBX_NAMESPACE_APP 0x02
#define HSX_MBX_NAMESPACE_SHARED 0x03

#define HSX_MBX_MODE_RDONLY 0x01
#define HSX_MBX_MODE_WRONLY 0x02
#define HSX_MBX_MODE_RDWR 0x03
#define HSX_MBX_MODE_TAP 0x04
#define HSX_MBX_MODE_FANOUT 0x08
#define HSX_MBX_MODE_FANOUT_DROP 0x10
#define HSX_MBX_MODE_FANOUT_BLOCK 0x20

#define HSX_MBX_FLAG_STDOUT 0x0001
#define HSX_MBX_FLAG_STDERR 0x0002
#define HSX_MBX_FLAG_OOB 0x0004
#define HSX_MBX_FLAG_OVERRUN 0x0008

#define HSX_MBX_PREFIX_PID "pid:"
#define HSX_MBX_PREFIX_SVC "svc:"
#define HSX_MBX_PREFIX_APP "app:"
#define HSX_MBX_PREFIX_SHARED "shared:"

#define HSX_MBX_STDIO_IN "svc:stdio.in"
#define HSX_MBX_STDIO_OUT "svc:stdio.out"
#define HSX_MBX_STDIO_ERR "svc:stdio.err"

#define HSX_MBX_TRACE_FLAG_ENABLED 0x01

#define HSX_MBX_FN_OPEN 0x00
#define HSX_MBX_FN_BIND 0x01
#define HSX_MBX_FN_SEND 0x02
#define HSX_MBX_FN_RECV 0x03
#define HSX_MBX_FN_PEEK 0x04
#define HSX_MBX_FN_TAP 0x05
#define HSX_MBX_FN_CLOSE 0x06

#define HSX_MBX_STATUS_OK 0x0000
#define HSX_MBX_STATUS_WOULDBLOCK 0x0001
#define HSX_MBX_STATUS_INVALID_HANDLE 0x0002
#define HSX_MBX_STATUS_NO_DATA 0x0003
#define HSX_MBX_STATUS_MSG_TOO_LARGE 0x0004
#define HSX_MBX_STATUS_INTERNAL_ERROR 0x00FF

typedef struct hsx_mbx_msg_header {
    uint16_t len;       /* payload bytes following this header */
    uint16_t flags;     /* HSX_MBX_FLAG_* bits */
    uint16_t src_pid;   /* sender PID */
    uint16_t channel;   /* logical channel identifier */
} hsx_mbx_msg_header_t;

typedef struct hsx_mbx_bind_config {
    uint16_t capacity;  /* ring buffer capacity in bytes */
    uint16_t mode;      /* HSX_MBX_MODE_* access mask */
    uint16_t reserved0; /* future: priority / tap slots */
    uint16_t reserved1;
} hsx_mbx_bind_config_t;

typedef struct hsx_mbx_trace_event {
    uint32_t timestamp_lo;
    uint16_t timestamp_hi;
    uint16_t src_pid;
    uint16_t dst_handle;
    uint16_t flags;
    uint16_t length;
} hsx_mbx_trace_event_t;

#endif /* HSX_MAILBOX_H */
