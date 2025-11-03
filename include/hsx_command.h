#ifndef HSX_COMMAND_H
#define HSX_COMMAND_H

#include <stdint.h>

/*
 * HSX command module (SVC 0x08) shared constants between the C executive and
 * Python prototype. The Python tooling scrapes these #define values to stay in
 * sync, so keep the simple literal forms.
 */

#define HSX_CMD_MODULE_ID 0x08

/* Command SVC function IDs */
#define HSX_CMD_FN_REGISTER     0x00
#define HSX_CMD_FN_LOOKUP       0x01
#define HSX_CMD_FN_CALL         0x02
#define HSX_CMD_FN_CALL_ASYNC   0x03
#define HSX_CMD_FN_HELP         0x04

/* Command status codes */
#define HSX_CMD_STATUS_OK         0x0000
#define HSX_CMD_STATUS_ENOENT     0x0001  /* Command not found */
#define HSX_CMD_STATUS_EPERM      0x0002  /* Permission denied */
#define HSX_CMD_STATUS_ENOSPC     0x0003  /* Registry exhausted */
#define HSX_CMD_STATUS_EINVAL     0x0004  /* Invalid parameter */
#define HSX_CMD_STATUS_EEXIST     0x0005  /* Command already exists */
#define HSX_CMD_STATUS_ENOASYNC   0x0006  /* Async not allowed */
#define HSX_CMD_STATUS_EFAIL      0x0007  /* Command execution failed */

/* Command flags */
#define HSX_CMD_FLAG_PIN          0x01    /* Command requires PIN auth */
#define HSX_CMD_FLAG_ASYNC        0x02    /* Command allows async invocation */

/* Authorization levels (same as values) */
#define HSX_CMD_AUTH_PUBLIC       0x00    /* No auth required */
#define HSX_CMD_AUTH_USER         0x01    /* User-level auth */
#define HSX_CMD_AUTH_ADMIN        0x02    /* Admin-level auth */
#define HSX_CMD_AUTH_FACTORY      0x03    /* Factory-level auth */

/* Registry size limits */
#define HSX_CMD_MAX_COMMANDS      256     /* Maximum command entries */

#define HSX_CMD_DESC_NAME         0x10    /* Command name/help descriptor */
#define HSX_CMD_DESC_INVALID      0xFFFF

/*
 * Compact command entry stored in the executive registry.
 * Handler references and descriptor chains are addressed via 16-bit offsets.
 */
#pragma pack(push, 1)
typedef struct hsx_cmd_entry {
    uint8_t  group_id;
    uint8_t  cmd_id;
    uint8_t  flags;
    uint8_t  auth_level;
    uint16_t owner_pid;
    uint16_t handler_ref;    /* Offset or index to handler entry (implementation-defined) */
    uint16_t desc_head;      /* Offset to first descriptor or HSX_CMD_DESC_INVALID */
} hsx_cmd_entry_t;

typedef struct hsx_cmd_name_desc {
    uint8_t  desc_type;      /* HSX_CMD_DESC_NAME */
    uint8_t  reserved;
    uint16_t next;
    uint16_t name_offset;    /* Offset into string table */
    uint16_t help_offset;    /* Offset into string table */
} hsx_cmd_name_desc_t;
#pragma pack(pop)

_Static_assert(sizeof(hsx_cmd_entry_t) == 10, "hsx_cmd_entry_t must remain packed (10 bytes)");

/*
 * COMMAND SVC calling convention (ABI summary)
 *
 * All command traps use SVC module 0x08.
 *   R0 : status result (0 == HSX_CMD_STATUS_OK on success)
 *   R1..R4 : arguments in order (see table below)
 *   Caller-saved registers (R0..R5) may be clobbered by the trap handler.
 *
 * ---------------------------------------------------------------------------
 *  Call                 R1          R2          R3          R4
 * ---------------------------------------------------------------------------
 *  CMD_REGISTER         group_id    cmd_id      flags       desc_ptr
 *  CMD_LOOKUP           group_id    cmd_id      (unused)    (unused)
 *  CMD_CALL             oid         token_ptr   flags       (unused)
 *  CMD_CALL_ASYNC       oid         token_ptr   mbox_ptr    (unused)
 *  CMD_HELP             oid         out_ptr     max_len     (unused)
 * ---------------------------------------------------------------------------
 *
 * Notes:
 * - OID (Object ID) = (group_id << 8) | cmd_id
 * - CMD_REGISTER returns OID in R1 on success
 * - CMD_CALL returns command result in R1 on success
 * - CMD_HELP returns bytes written in R1 on success
 */

#endif /* HSX_COMMAND_H */
