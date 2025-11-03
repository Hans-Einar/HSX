#ifndef HSX_VALUE_H
#define HSX_VALUE_H

#include <stdint.h>

/*
 * HSX value module (SVC 0x07) shared constants between the C executive and
 * Python prototype. The Python tooling scrapes these #define values to stay in
 * sync, so keep the simple literal forms.
 */

#define HSX_VAL_MODULE_ID 0x07

/* Value SVC function IDs */
#define HSX_VAL_FN_REGISTER 0x00
#define HSX_VAL_FN_LOOKUP   0x01
#define HSX_VAL_FN_GET      0x02
#define HSX_VAL_FN_SET      0x03
#define HSX_VAL_FN_LIST     0x04
#define HSX_VAL_FN_SUB      0x05
#define HSX_VAL_FN_PERSIST  0x06

/* Value status codes */
#define HSX_VAL_STATUS_OK         0x0000
#define HSX_VAL_STATUS_ENOENT     0x0001  /* Value not found */
#define HSX_VAL_STATUS_EPERM      0x0002  /* Permission denied */
#define HSX_VAL_STATUS_ENOSPC     0x0003  /* Registry exhausted */
#define HSX_VAL_STATUS_EINVAL     0x0004  /* Invalid parameter */
#define HSX_VAL_STATUS_EEXIST     0x0005  /* Value already exists */
#define HSX_VAL_STATUS_EBUSY      0x0006  /* Value busy/rate limited */

/* Value flags */
#define HSX_VAL_FLAG_RO           0x01    /* Read-only value */
#define HSX_VAL_FLAG_PERSIST      0x02    /* Value persists across reboots */
#define HSX_VAL_FLAG_STICKY       0x04    /* Value sticky (reserved) */
#define HSX_VAL_FLAG_PIN          0x08    /* Value requires PIN auth */
#define HSX_VAL_FLAG_BOOL         0x10    /* Value is boolean (0 or 1) */

/* Authorization levels */
#define HSX_VAL_AUTH_PUBLIC       0x00    /* No auth required */
#define HSX_VAL_AUTH_USER         0x01    /* User-level auth */
#define HSX_VAL_AUTH_ADMIN        0x02    /* Admin-level auth */
#define HSX_VAL_AUTH_FACTORY      0x03    /* Factory-level auth */

/* Persistence modes */
#define HSX_VAL_PERSIST_VOLATILE  0x00    /* No persistence */
#define HSX_VAL_PERSIST_LOAD      0x01    /* Load on boot */
#define HSX_VAL_PERSIST_SAVE      0x02    /* Load + save on change */

/* Descriptor type tags */
#define HSX_VAL_DESC_GROUP        0x01    /* Group descriptor */
#define HSX_VAL_DESC_NAME         0x02    /* Name descriptor */
#define HSX_VAL_DESC_UNIT         0x03    /* Unit descriptor */
#define HSX_VAL_DESC_RANGE        0x04    /* Range descriptor */
#define HSX_VAL_DESC_PERSIST      0x05    /* Persist descriptor */

/* Special group_id values */
#define HSX_VAL_GROUP_ALL         0xFF    /* All groups (for filtering) */

/* Registry size limits */
#define HSX_VAL_MAX_VALUES        256     /* Maximum value entries */
#define HSX_VAL_STRING_TABLE_SIZE 4096    /* String table size in bytes */

/* Descriptor helpers */
#define HSX_VAL_DESC_INVALID      0xFFFF  /* Invalid descriptor offset */

/* Forward declarations */
struct hsx_val_descriptor;

/*
 * Compact value entry stored in the executive registry.
 * Descriptors are addressed using 16-bit offsets into the descriptor pool.
 */
#pragma pack(push, 1)
typedef struct hsx_val_entry {
    uint8_t  group_id;
    uint8_t  value_id;
    uint8_t  flags;
    uint8_t  auth_level;
    uint16_t owner_pid;
    uint16_t last_f16;       /* Raw IEEE754 half-precision bits */
    uint16_t desc_head;      /* Offset to first descriptor (HSX_VAL_DESC_INVALID if none) */
} hsx_val_entry_t;
#pragma pack(pop)

/*
 * Descriptor base (shared layout for all descriptors).
 * Each descriptor resides in a packed pool; offsets are 16-bit.
 */
#pragma pack(push, 1)
typedef struct hsx_val_descriptor {
    uint8_t  desc_type;
    uint8_t  reserved;
    uint16_t next;           /* Offset to next descriptor or HSX_VAL_DESC_INVALID */
} hsx_val_descriptor_t;

typedef struct hsx_group_desc {
    uint8_t  desc_type;      /* HSX_VAL_DESC_GROUP */
    uint8_t  group_id;
    uint16_t next;
    uint16_t name_offset;    /* Offset into string table */
} hsx_group_desc_t;

typedef struct hsx_name_desc {
    uint8_t  desc_type;      /* HSX_VAL_DESC_NAME */
    uint8_t  reserved;
    uint16_t next;
    uint16_t name_offset;    /* Offset into string table */
} hsx_name_desc_t;

typedef struct hsx_unit_desc {
    uint8_t  desc_type;      /* HSX_VAL_DESC_UNIT */
    uint8_t  reserved;
    uint16_t next;
    uint32_t unit_code;      /* Packed 4-char code */
    uint16_t epsilon_f16;    /* IEEE754 half-precision */
    uint16_t rate_ms;
} hsx_unit_desc_t;

typedef struct hsx_range_desc {
    uint8_t  desc_type;      /* HSX_VAL_DESC_RANGE */
    uint8_t  reserved;
    uint16_t next;
    uint16_t min_f16;        /* IEEE754 half-precision */
    uint16_t max_f16;        /* IEEE754 half-precision */
} hsx_range_desc_t;

typedef struct hsx_persist_desc {
    uint8_t  desc_type;      /* HSX_VAL_DESC_PERSIST */
    uint8_t  reserved;
    uint16_t next;
    uint16_t persist_key;
    uint16_t debounce_ms;
} hsx_persist_desc_t;
#pragma pack(pop)

_Static_assert(sizeof(hsx_val_entry_t) == 10, "hsx_val_entry_t must remain packed (10 bytes)");

/*
 * VALUE SVC calling convention (ABI summary)
 *
 * All value traps use SVC module 0x07.
 *   R0 : status result (0 == HSX_VAL_STATUS_OK on success)
 *   R1..R4 : arguments in order (see table below)
 *   Caller-saved registers (R0..R5) may be clobbered by the trap handler.
 *
 * ---------------------------------------------------------------------------
 *  Call                 R1          R2          R3          R4
 * ---------------------------------------------------------------------------
 *  VAL_REGISTER         group_id    value_id    flags       desc_ptr
 *  VAL_LOOKUP           group_id    value_id    (unused)    (unused)
 *  VAL_GET              oid         (unused)    (unused)    (unused)
 *  VAL_SET              oid         f16_value   flags       (unused)
 *  VAL_LIST             group_filt  out_ptr     max_items   (unused)
 *  VAL_SUB              oid         mbox_ptr    flags       (unused)
 *  VAL_PERSIST          oid         mode        (unused)    (unused)
 * ---------------------------------------------------------------------------
 *
 * Notes:
 * - OID (Object ID) = (group_id << 8) | value_id
 * - f16_value is IEEE 754 half-precision float in lower 16 bits of R2
 * - VAL_REGISTER returns OID in R1 on success
 * - VAL_GET returns f16_value in R0 lower 16 bits on success
 * - VAL_LIST returns count in R1 on success
 */

#endif /* HSX_VALUE_H */
