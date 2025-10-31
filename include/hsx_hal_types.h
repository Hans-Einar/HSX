#ifndef HSX_HAL_TYPES_H
#define HSX_HAL_TYPES_H

#include <stdint.h>
#include <stdbool.h>

/*
 * HSX HAL common types and constants
 * Shared between executive-space HAL modules and user-space libraries
 */

/* Common return codes */
#define HSX_HAL_OK             0
#define HSX_HAL_ERROR         -1
#define HSX_HAL_TIMEOUT       -2
#define HSX_HAL_BUSY          -3
#define HSX_HAL_INVALID_PARAM -4
#define HSX_HAL_NO_MEMORY     -5
#define HSX_HAL_UNSUPPORTED   -6

/* Common flags */
#define HSX_HAL_NONBLOCK      0x01
#define HSX_HAL_TIMEOUT_INF   0xFFFFFFFF

/* HAL module IDs (syscall module numbers) */
#define HSX_HAL_MODULE_UART   0x10
#define HSX_HAL_MODULE_CAN    0x11
#define HSX_HAL_MODULE_TIMER  0x12
#define HSX_HAL_MODULE_FRAM   0x13
#define HSX_HAL_MODULE_FS     0x14
#define HSX_HAL_MODULE_GPIO   0x15

/* Mailbox namespace prefix for HAL events */
#define HSX_HAL_MBX_PREFIX    "hal:"

/* Event callback type */
typedef void (*hsx_hal_event_callback_t)(void* event_data, uint32_t length, void* user_data);

#endif /* HSX_HAL_TYPES_H */
