#ifndef HSX_STDLIB_H
#define HSX_STDLIB_H

#include <stdint.h>

/*
 * Reserved group/value/command identifiers used by lib/hsx_std/stdlib.mvasm.
 * These constants are provided so payloads can construct OIDs without
 * repeating the literal numbers.
 */

#define HSX_STD_GROUP_SYSTEM        0xF0

/* Value identifiers */
#define HSX_STD_VALUE_SYS_VERSION   0x01
#define HSX_STD_VALUE_SYS_BUILD     0x02
#define HSX_STD_VALUE_SYS_UPTIME    0x03
#define HSX_STD_VALUE_SYS_HEALTH    0x04

/* Command identifiers */
#define HSX_STD_CMD_SYS_RESET       0x10
#define HSX_STD_CMD_SYS_NOOP        0x11

static inline uint16_t hsx_std_oid(uint8_t group_id, uint8_t value_id) {
    return (uint16_t)((group_id << 8) | value_id);
}

#define HSX_STD_OID_SYS_VERSION hsx_std_oid(HSX_STD_GROUP_SYSTEM, HSX_STD_VALUE_SYS_VERSION)
#define HSX_STD_OID_SYS_BUILD   hsx_std_oid(HSX_STD_GROUP_SYSTEM, HSX_STD_VALUE_SYS_BUILD)
#define HSX_STD_OID_SYS_UPTIME  hsx_std_oid(HSX_STD_GROUP_SYSTEM, HSX_STD_VALUE_SYS_UPTIME)
#define HSX_STD_OID_SYS_HEALTH  hsx_std_oid(HSX_STD_GROUP_SYSTEM, HSX_STD_VALUE_SYS_HEALTH)

#ifdef __cplusplus
extern "C" {
#endif

void hsx_std_reset(void);
void hsx_std_noop(void);

#ifdef __cplusplus
}
#endif

#endif /* HSX_STDLIB_H */
