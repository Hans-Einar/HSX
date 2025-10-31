# HAL Module Architecture - Two-Layer Design

**Status:** DESIGN | **Date:** 2025-10-31 | **Owner:** HSX Core

> **Purpose:** Defines the two-layer HAL architecture with executive-side modules and user-space libraries. Applications link against user-space libraries that abstract whether operations use syscalls or mailboxes.

## Overview

The HAL is organized into two layers:

1. **Executive-Space HAL** (kernel space) - Modules in the executive that handle hardware operations
2. **User-Space HAL** (application space) - Libraries linked into HSX apps that provide convenient API

```text
┌─────────────────────────────────────────────────┐
│         HSX Application Code                    │
│   (uses hsx_uart.h, hsx_gpio.h, etc.)          │
└──────────────┬──────────────────────────────────┘
               │ Links against libhsx_hal.a
               ↓
┌─────────────────────────────────────────────────┐
│      User-Space HAL Libraries                   │
│  (hsx_uart.c, hsx_gpio.c, hsx_timer.c, etc.)   │
│  - Wraps syscalls (SVC instructions)           │
│  - Opens/manages mailboxes for events          │
│  - Provides convenient API                      │
└──────────────┬──────────────────────────────────┘
               │ SVC or Mailbox
               ↓
┌─────────────────────────────────────────────────┐
│     Executive SVC Dispatcher / Mailbox Mgr      │
└──────────────┬──────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────┐
│      Executive-Space HAL Modules                │
│  (uart_hal.c, can_hal.c, gpio_hal.c, etc.)     │
│  - Implements syscall handlers                  │
│  - Posts mailbox events on interrupts           │
│  - Wraps platform drivers                       │
└──────────────┬──────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────┐
│       Platform Drivers (AVR, STM32, etc.)       │
└─────────────────────────────────────────────────┘
```

## Executive-Space HAL Modules

### Module List

| Module | ID | Executive Source | Syscall Module | Mailbox Namespace |
|--------|----|-----------------|-----------------|--------------------|
| UART   | 0x10 | `exec/hal/uart_hal.c` | 0x10 | `hal:uart:*` |
| CAN    | 0x11 | `exec/hal/can_hal.c` | 0x11 | `hal:can:*` |
| Timer  | 0x12 | `exec/hal/timer_hal.c` | 0x12 | `hal:timer:*` |
| FRAM   | 0x13 | `exec/hal/fram_hal.c` | 0x13 | N/A |
| FS     | 0x14 | `exec/hal/fs_hal.c` | 0x14 | N/A |
| GPIO   | 0x15 | `exec/hal/gpio_hal.c` | 0x15 | `hal:gpio:*` |

### UART Module (0x10)

**File:** `exec/hal/uart_hal.c`

**Responsibilities:**
- Handle UART_WRITE syscall (synchronous transmit)
- Handle UART_CONFIG syscall (baud rate, parity, etc.)
- Post received bytes to `hal:uart:rx` mailbox (async)
- Manage TX/RX buffers

**Syscalls:**
- `0x10, 0x00 UART_WRITE(port, buf_ptr, length)` → bytes_written
- `0x10, 0x01 UART_READ_POLL(port, buf_ptr, max_len)` → bytes_read (non-blocking)
- `0x10, 0x02 UART_CONFIG(port, baud, parity, stop_bits)` → status
- `0x10, 0x03 UART_GET_STATUS(port)` → status flags

**Mailbox Events:**
- `hal:uart:0:rx` - Received data on UART 0
- `hal:uart:1:rx` - Received data on UART 1

**Event Message Format:**
```c
typedef struct {
    uint8_t port;        // UART port number
    uint8_t data[32];    // Received bytes
    uint8_t length;      // Number of bytes
    uint8_t flags;       // Parity error, overrun, etc.
} uart_rx_event_t;
```

### CAN Module (0x11)

**File:** `exec/hal/can_hal.c`

**Responsibilities:**
- Handle CAN_TX syscall (synchronous transmit)
- Handle CAN_CONFIG syscall (filters, bitrate)
- Post received frames to `hal:can:rx` mailbox (async)
- Manage TX/RX queues

**Syscalls:**
- `0x11, 0x00 CAN_TX(can_id, buf_ptr, dlc, flags)` → status
- `0x11, 0x01 CAN_CONFIG(bitrate, mode)` → status
- `0x11, 0x02 CAN_SET_FILTER(filter_id, mask, id)` → status
- `0x11, 0x03 CAN_GET_STATUS()` → status flags

**Mailbox Events:**
- `hal:can:rx` - Received CAN frame

**Event Message Format:**
```c
typedef struct {
    uint32_t can_id;     // 11 or 29-bit CAN ID
    uint8_t dlc;         // Data length code (0-8)
    uint8_t flags;       // RTR, extended, etc.
    uint8_t data[8];     // CAN frame data
    uint32_t timestamp;  // Reception timestamp (us)
} can_rx_event_t;
```

### Timer Module (0x12)

**File:** `exec/hal/timer_hal.c`

**Responsibilities:**
- Handle TIMER_GET_TICK syscall (read monotonic counter)
- Handle TIMER_SLEEP syscall (delegated to EXEC_SLEEP_MS)
- Handle TIMER_CREATE syscall (create periodic timer)
- Post timer expiry to mailbox (async)

**Syscalls:**
- `0x12, 0x00 TIMER_GET_TICK()` → tick_count (us)
- `0x12, 0x01 TIMER_GET_TICK_FREQ()` → ticks_per_second
- `0x12, 0x02 TIMER_CREATE(period_us, one_shot)` → timer_id
- `0x12, 0x03 TIMER_CANCEL(timer_id)` → status

**Mailbox Events:**
- `hal:timer:<id>` - Timer expiry for timer <id>

**Event Message Format:**
```c
typedef struct {
    uint16_t timer_id;   // Timer that expired
    uint32_t tick;       // Current tick when expired
    uint8_t overruns;    // Number of missed expirations
} timer_event_t;
```

### FRAM Module (0x13)

**File:** `exec/hal/fram_hal.c`

**Responsibilities:**
- Handle FRAM_READ syscall (synchronous read)
- Handle FRAM_WRITE syscall (synchronous write)
- Manage wear leveling
- CRC validation

**Syscalls:**
- `0x13, 0x00 FRAM_READ(addr, buf_ptr, length)` → bytes_read
- `0x13, 0x01 FRAM_WRITE(addr, buf_ptr, length)` → bytes_written
- `0x13, 0x02 FRAM_GET_SIZE()` → total_bytes
- `0x13, 0x03 FRAM_GET_WEAR(addr)` → write_count

**Mailbox Events:** None (synchronous only)

### FS Module (0x14)

**File:** `exec/hal/fs_hal.c`

**Responsibilities:**
- Handle FS_OPEN, FS_READ, FS_WRITE, FS_CLOSE syscalls
- Handle directory operations
- Manage file descriptors per task

**Syscalls:**
- `0x14, 0x00 FS_OPEN(path_ptr, flags)` → fd
- `0x14, 0x01 FS_READ(fd, buf_ptr, length)` → bytes_read
- `0x14, 0x02 FS_WRITE(fd, buf_ptr, length)` → bytes_written
- `0x14, 0x03 FS_CLOSE(fd)` → status
- `0x14, 0x0A FS_LISTDIR(path_ptr, buf_ptr, max_len)` → bytes_written
- `0x14, 0x0B FS_DELETE(path_ptr)` → status
- `0x14, 0x0C FS_RENAME(old_path_ptr, new_path_ptr)` → status
- `0x14, 0x0D FS_MKDIR(path_ptr)` → status

**Mailbox Events:** None (synchronous only)

### GPIO Module (0x15)

**File:** `exec/hal/gpio_hal.c`

**Responsibilities:**
- Handle GPIO_READ/WRITE syscalls (synchronous I/O)
- Handle GPIO_CONFIG syscall (input/output, pull-up, etc.)
- Handle GPIO_SET_INTERRUPT syscall (edge detection config)
- Post interrupt events to mailbox (async)

**Syscalls:**
- `0x15, 0x00 GPIO_READ(pin)` → value (0 or 1)
- `0x15, 0x01 GPIO_WRITE(pin, value)` → status
- `0x15, 0x02 GPIO_CONFIG(pin, mode, pull)` → status
- `0x15, 0x03 GPIO_SET_INTERRUPT(pin, edge, enable)` → status

**Mailbox Events:**
- `hal:gpio:<pin>` - Interrupt on pin <pin>

**Event Message Format:**
```c
typedef struct {
    uint8_t pin;         // GPIO pin number
    uint8_t edge;        // RISING, FALLING, or BOTH
    uint8_t value;       // Current pin state
    uint32_t timestamp;  // Event timestamp (us)
} gpio_event_t;
```

## User-Space HAL Libraries

### Library Organization

Each HAL module has a corresponding user-space library:

```text
libhsx_hal/
├── include/
│   ├── hsx_uart.h       - UART API
│   ├── hsx_can.h        - CAN API
│   ├── hsx_timer.h      - Timer API
│   ├── hsx_fram.h       - FRAM API
│   ├── hsx_fs.h         - Filesystem API
│   ├── hsx_gpio.h       - GPIO API
│   └── hsx_hal_types.h  - Common types
└── src/
    ├── hsx_uart.c       - UART implementation
    ├── hsx_can.c        - CAN implementation
    ├── hsx_timer.c      - Timer implementation
    ├── hsx_fram.c       - FRAM implementation
    ├── hsx_fs.c         - Filesystem implementation
    └── hsx_gpio.c       - GPIO implementation
```

### Common Header: hsx_hal_types.h

```c
#ifndef HSX_HAL_TYPES_H
#define HSX_HAL_TYPES_H

#include <stdint.h>
#include <stdbool.h>

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

/* Event callback type */
typedef void (*hsx_hal_event_callback_t)(void* event_data, uint32_t length, void* user_data);

#endif /* HSX_HAL_TYPES_H */
```

### UART Library Header: hsx_uart.h

```c
#ifndef HSX_UART_H
#define HSX_UART_H

#include "hsx_hal_types.h"

/* UART port identifiers */
#define HSX_UART_0  0
#define HSX_UART_1  1
#define HSX_UART_2  2

/* UART configuration */
typedef enum {
    HSX_UART_BAUD_9600   = 9600,
    HSX_UART_BAUD_19200  = 19200,
    HSX_UART_BAUD_38400  = 38400,
    HSX_UART_BAUD_57600  = 57600,
    HSX_UART_BAUD_115200 = 115200,
} hsx_uart_baud_t;

typedef enum {
    HSX_UART_PARITY_NONE = 0,
    HSX_UART_PARITY_EVEN = 1,
    HSX_UART_PARITY_ODD  = 2,
} hsx_uart_parity_t;

typedef enum {
    HSX_UART_STOP_1 = 1,
    HSX_UART_STOP_2 = 2,
} hsx_uart_stop_bits_t;

typedef struct {
    hsx_uart_baud_t baud;
    hsx_uart_parity_t parity;
    hsx_uart_stop_bits_t stop_bits;
} hsx_uart_config_t;

/* UART status flags */
#define HSX_UART_STATUS_TX_READY  0x01
#define HSX_UART_STATUS_RX_READY  0x02
#define HSX_UART_STATUS_OVERRUN   0x04
#define HSX_UART_STATUS_PARITY_ERR 0x08

/* UART RX event data */
typedef struct {
    uint8_t port;
    uint8_t data[32];
    uint8_t length;
    uint8_t flags;
} hsx_uart_rx_event_t;

/**
 * Initialize UART port with default configuration.
 * 
 * @param port UART port number (HSX_UART_0, HSX_UART_1, etc.)
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_uart_init(uint8_t port);

/**
 * Configure UART port parameters.
 * 
 * @param port UART port number
 * @param config Pointer to configuration structure
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_uart_config(uint8_t port, const hsx_uart_config_t* config);

/**
 * Write data to UART (synchronous, uses syscall).
 * Blocks until all data is written or timeout occurs.
 * 
 * @param port UART port number
 * @param data Pointer to data buffer
 * @param length Number of bytes to write
 * @return Number of bytes written, or negative error code
 */
int hsx_uart_write(uint8_t port, const void* data, uint32_t length);

/**
 * Read data from UART (non-blocking poll, uses syscall).
 * Returns immediately with available data.
 * 
 * @param port UART port number
 * @param buffer Pointer to receive buffer
 * @param max_length Maximum bytes to read
 * @return Number of bytes read, or negative error code
 */
int hsx_uart_read_poll(uint8_t port, void* buffer, uint32_t max_length);

/**
 * Read data from UART (blocking, uses mailbox).
 * Blocks until data arrives or timeout occurs.
 * 
 * @param port UART port number
 * @param buffer Pointer to receive buffer
 * @param max_length Maximum bytes to read
 * @param timeout_ms Timeout in milliseconds (HSX_HAL_TIMEOUT_INF for infinite)
 * @return Number of bytes read, or negative error code
 */
int hsx_uart_read(uint8_t port, void* buffer, uint32_t max_length, uint32_t timeout_ms);

/**
 * Register callback for UART RX events (mailbox-based).
 * Callback is invoked when data arrives on the specified port.
 * 
 * @param port UART port number
 * @param callback Callback function
 * @param user_data User data passed to callback
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_uart_set_rx_callback(uint8_t port, hsx_hal_event_callback_t callback, void* user_data);

/**
 * Get UART status flags.
 * 
 * @param port UART port number
 * @return Status flags (HSX_UART_STATUS_*)
 */
uint32_t hsx_uart_get_status(uint8_t port);

/**
 * printf-style formatted output to UART.
 * 
 * @param port UART port number
 * @param format Format string (printf-style)
 * @param ... Variable arguments
 * @return Number of characters written, or negative error code
 */
int hsx_uart_printf(uint8_t port, const char* format, ...);

#endif /* HSX_UART_H */
```

### CAN Library Header: hsx_can.h

```c
#ifndef HSX_CAN_H
#define HSX_CAN_H

#include "hsx_hal_types.h"

/* CAN frame types */
#define HSX_CAN_STD_FRAME  0x00  /* Standard 11-bit ID */
#define HSX_CAN_EXT_FRAME  0x01  /* Extended 29-bit ID */
#define HSX_CAN_RTR_FRAME  0x02  /* Remote transmission request */

/* CAN bitrates */
typedef enum {
    HSX_CAN_BITRATE_125K  = 125000,
    HSX_CAN_BITRATE_250K  = 250000,
    HSX_CAN_BITRATE_500K  = 500000,
    HSX_CAN_BITRATE_1M    = 1000000,
} hsx_can_bitrate_t;

/* CAN frame structure */
typedef struct {
    uint32_t can_id;     /* 11 or 29-bit CAN ID */
    uint8_t dlc;         /* Data length code (0-8) */
    uint8_t flags;       /* HSX_CAN_*_FRAME flags */
    uint8_t data[8];     /* CAN frame data */
} hsx_can_frame_t;

/* CAN RX event data */
typedef struct {
    uint32_t can_id;
    uint8_t dlc;
    uint8_t flags;
    uint8_t data[8];
    uint32_t timestamp;
} hsx_can_rx_event_t;

/**
 * Initialize CAN peripheral with default configuration.
 * 
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_init(void);

/**
 * Configure CAN bitrate and mode.
 * 
 * @param bitrate CAN bitrate
 * @param mode Reserved for future use (set to 0)
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_config(hsx_can_bitrate_t bitrate, uint32_t mode);

/**
 * Transmit CAN frame (synchronous, uses syscall).
 * Blocks until frame is sent or timeout occurs.
 * 
 * @param frame Pointer to CAN frame structure
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_tx(const hsx_can_frame_t* frame);

/**
 * Receive CAN frame (blocking, uses mailbox).
 * Blocks until frame arrives or timeout occurs.
 * 
 * @param frame Pointer to receive frame structure
 * @param timeout_ms Timeout in milliseconds
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_rx(hsx_can_frame_t* frame, uint32_t timeout_ms);

/**
 * Set CAN filter (accept/reject frames based on ID).
 * 
 * @param filter_id Filter bank number (0-15)
 * @param mask Filter mask (bits to check)
 * @param id Filter ID (bits to match)
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_set_filter(uint8_t filter_id, uint32_t mask, uint32_t id);

/**
 * Register callback for CAN RX events (mailbox-based).
 * 
 * @param callback Callback function
 * @param user_data User data passed to callback
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_can_set_rx_callback(hsx_hal_event_callback_t callback, void* user_data);

/**
 * Get CAN status flags (error counts, bus-off, etc.).
 * 
 * @return Status flags
 */
uint32_t hsx_can_get_status(void);

#endif /* HSX_CAN_H */
```

### GPIO Library Header: hsx_gpio.h

```c
#ifndef HSX_GPIO_H
#define HSX_GPIO_H

#include "hsx_hal_types.h"

/* GPIO pin modes */
typedef enum {
    HSX_GPIO_MODE_INPUT  = 0,
    HSX_GPIO_MODE_OUTPUT = 1,
    HSX_GPIO_MODE_ANALOG = 2,
} hsx_gpio_mode_t;

/* GPIO pull resistors */
typedef enum {
    HSX_GPIO_PULL_NONE = 0,
    HSX_GPIO_PULL_UP   = 1,
    HSX_GPIO_PULL_DOWN = 2,
} hsx_gpio_pull_t;

/* GPIO interrupt edges */
typedef enum {
    HSX_GPIO_EDGE_NONE    = 0,
    HSX_GPIO_EDGE_RISING  = 1,
    HSX_GPIO_EDGE_FALLING = 2,
    HSX_GPIO_EDGE_BOTH    = 3,
} hsx_gpio_edge_t;

/* GPIO event data */
typedef struct {
    uint8_t pin;
    uint8_t edge;
    uint8_t value;
    uint32_t timestamp;
} hsx_gpio_event_t;

/**
 * Configure GPIO pin mode and pull resistor.
 * 
 * @param pin GPIO pin number
 * @param mode Pin mode (input/output/analog)
 * @param pull Pull resistor configuration
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_config(uint8_t pin, hsx_gpio_mode_t mode, hsx_gpio_pull_t pull);

/**
 * Read GPIO pin value (synchronous, uses syscall).
 * 
 * @param pin GPIO pin number
 * @return Pin value (0 or 1), or negative error code
 */
int hsx_gpio_read(uint8_t pin);

/**
 * Write GPIO pin value (synchronous, uses syscall).
 * 
 * @param pin GPIO pin number
 * @param value Value to write (0 or 1)
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_write(uint8_t pin, uint8_t value);

/**
 * Toggle GPIO pin value.
 * 
 * @param pin GPIO pin number
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_toggle(uint8_t pin);

/**
 * Configure GPIO interrupt (edge detection).
 * 
 * @param pin GPIO pin number
 * @param edge Edge type (rising/falling/both)
 * @param enable Enable (true) or disable (false) interrupt
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_set_interrupt(uint8_t pin, hsx_gpio_edge_t edge, bool enable);

/**
 * Register callback for GPIO interrupt events (mailbox-based).
 * Callback is invoked when configured edge is detected.
 * 
 * @param pin GPIO pin number
 * @param callback Callback function
 * @param user_data User data passed to callback
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_set_interrupt_callback(uint8_t pin, hsx_hal_event_callback_t callback, void* user_data);

/**
 * Wait for GPIO interrupt (blocking, uses mailbox).
 * Blocks until interrupt occurs or timeout.
 * 
 * @param pin GPIO pin number
 * @param timeout_ms Timeout in milliseconds
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_gpio_wait_interrupt(uint8_t pin, uint32_t timeout_ms);

#endif /* HSX_GPIO_H */
```

### Timer Library Header: hsx_timer.h

```c
#ifndef HSX_TIMER_H
#define HSX_TIMER_H

#include "hsx_hal_types.h"

/* Timer types */
typedef enum {
    HSX_TIMER_ONE_SHOT = 0,
    HSX_TIMER_PERIODIC = 1,
} hsx_timer_type_t;

/* Timer handle (opaque) */
typedef uint16_t hsx_timer_t;

/* Timer event data */
typedef struct {
    uint16_t timer_id;
    uint32_t tick;
    uint8_t overruns;
} hsx_timer_event_t;

/**
 * Get current monotonic tick count (microseconds).
 * 
 * @return Tick count in microseconds
 */
uint64_t hsx_timer_get_tick(void);

/**
 * Get timer tick frequency (ticks per second).
 * 
 * @return Ticks per second
 */
uint32_t hsx_timer_get_freq(void);

/**
 * Sleep for specified milliseconds (uses EXEC_SLEEP_MS syscall).
 * Task blocks and yields CPU to other tasks.
 * 
 * @param ms Milliseconds to sleep
 */
void hsx_timer_sleep_ms(uint32_t ms);

/**
 * Sleep for specified microseconds (uses EXEC_SLEEP_MS syscall).
 * 
 * @param us Microseconds to sleep
 */
void hsx_timer_sleep_us(uint32_t us);

/**
 * Create a timer (one-shot or periodic).
 * Timer expiry generates mailbox event.
 * 
 * @param period_us Timer period in microseconds
 * @param type Timer type (one-shot or periodic)
 * @return Timer handle, or negative error code
 */
hsx_timer_t hsx_timer_create(uint32_t period_us, hsx_timer_type_t type);

/**
 * Cancel/delete a timer.
 * 
 * @param timer Timer handle
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_timer_cancel(hsx_timer_t timer);

/**
 * Wait for timer expiry (blocking, uses mailbox).
 * 
 * @param timer Timer handle
 * @param timeout_ms Maximum time to wait
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_timer_wait(hsx_timer_t timer, uint32_t timeout_ms);

/**
 * Register callback for timer expiry events (mailbox-based).
 * 
 * @param timer Timer handle
 * @param callback Callback function
 * @param user_data User data passed to callback
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_timer_set_callback(hsx_timer_t timer, hsx_hal_event_callback_t callback, void* user_data);

#endif /* HSX_TIMER_H */
```

### FRAM Library Header: hsx_fram.h

```c
#ifndef HSX_FRAM_H
#define HSX_FRAM_H

#include "hsx_hal_types.h"

/**
 * Read data from FRAM (synchronous, uses syscall).
 * 
 * @param addr FRAM address
 * @param buffer Pointer to receive buffer
 * @param length Number of bytes to read
 * @return Number of bytes read, or negative error code
 */
int hsx_fram_read(uint32_t addr, void* buffer, uint32_t length);

/**
 * Write data to FRAM (synchronous, uses syscall).
 * 
 * @param addr FRAM address
 * @param data Pointer to data buffer
 * @param length Number of bytes to write
 * @return Number of bytes written, or negative error code
 */
int hsx_fram_write(uint32_t addr, const void* data, uint32_t length);

/**
 * Get total FRAM size in bytes.
 * 
 * @return Total FRAM size, or negative error code
 */
int hsx_fram_get_size(void);

/**
 * Get wear count for FRAM address (number of writes).
 * 
 * @param addr FRAM address
 * @return Write count, or negative error code
 */
int hsx_fram_get_wear(uint32_t addr);

/**
 * Read variable from FRAM with type safety.
 * 
 * @param addr FRAM address
 * @param var Pointer to variable
 * @param size Size of variable
 * @return HSX_HAL_OK on success, error code otherwise
 */
#define hsx_fram_read_var(addr, var) \
    hsx_fram_read((addr), &(var), sizeof(var))

/**
 * Write variable to FRAM with type safety.
 * 
 * @param addr FRAM address
 * @param var Variable to write
 * @return HSX_HAL_OK on success, error code otherwise
 */
#define hsx_fram_write_var(addr, var) \
    hsx_fram_write((addr), &(var), sizeof(var))

#endif /* HSX_FRAM_H */
```

### Filesystem Library Header: hsx_fs.h

```c
#ifndef HSX_FS_H
#define HSX_FS_H

#include "hsx_hal_types.h"

/* File open flags */
#define HSX_FS_O_RDONLY  0x0001
#define HSX_FS_O_WRONLY  0x0002
#define HSX_FS_O_RDWR    0x0003
#define HSX_FS_O_CREAT   0x0004
#define HSX_FS_O_TRUNC   0x0008
#define HSX_FS_O_APPEND  0x0010

/* File descriptor type */
typedef int hsx_fd_t;

/**
 * Open file (synchronous, uses syscall).
 * 
 * @param path File path (C string)
 * @param flags Open flags (HSX_FS_O_*)
 * @return File descriptor, or negative error code
 */
hsx_fd_t hsx_fs_open(const char* path, uint32_t flags);

/**
 * Read from file (synchronous, uses syscall).
 * 
 * @param fd File descriptor
 * @param buffer Pointer to receive buffer
 * @param length Maximum bytes to read
 * @return Number of bytes read, or negative error code
 */
int hsx_fs_read(hsx_fd_t fd, void* buffer, uint32_t length);

/**
 * Write to file (synchronous, uses syscall).
 * 
 * @param fd File descriptor
 * @param data Pointer to data buffer
 * @param length Number of bytes to write
 * @return Number of bytes written, or negative error code
 */
int hsx_fs_write(hsx_fd_t fd, const void* data, uint32_t length);

/**
 * Close file (synchronous, uses syscall).
 * 
 * @param fd File descriptor
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_fs_close(hsx_fd_t fd);

/**
 * List directory contents (synchronous, uses syscall).
 * 
 * @param path Directory path
 * @param buffer Buffer for file list (newline-separated)
 * @param max_length Maximum buffer size
 * @return Number of bytes written, or negative error code
 */
int hsx_fs_listdir(const char* path, char* buffer, uint32_t max_length);

/**
 * Delete file (synchronous, uses syscall).
 * 
 * @param path File path
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_fs_delete(const char* path);

/**
 * Rename file (synchronous, uses syscall).
 * 
 * @param old_path Current file path
 * @param new_path New file path
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_fs_rename(const char* old_path, const char* new_path);

/**
 * Create directory (synchronous, uses syscall).
 * 
 * @param path Directory path
 * @return HSX_HAL_OK on success, error code otherwise
 */
int hsx_fs_mkdir(const char* path);

/**
 * printf-style formatted output to file.
 * 
 * @param fd File descriptor
 * @param format Format string (printf-style)
 * @param ... Variable arguments
 * @return Number of characters written, or negative error code
 */
int hsx_fs_printf(hsx_fd_t fd, const char* format, ...);

#endif /* HSX_FS_H */
```

## Implementation Example: UART Library

**File:** `libhsx_hal/src/hsx_uart.c`

```c
#include "hsx_uart.h"
#include <stdarg.h>
#include <stdio.h>

/* Internal state for mailbox handles */
static struct {
    int rx_mailbox_handle;
    hsx_hal_event_callback_t callback;
    void* user_data;
} uart_state[3] = {0};

/* SVC wrapper macros */
#define SVC_UART_WRITE(port, buf, len) \
    __asm__ volatile ( \
        "mov r1, %0\n" \
        "mov r2, %1\n" \
        "mov r3, %2\n" \
        "svc #0x10, #0x00\n" \
        "mov %0, r0\n" \
        : "+r"(len) : "r"(port), "r"(buf) : "r0", "r1", "r2", "r3")

int hsx_uart_init(uint8_t port) {
    if (port >= 3) {
        return HSX_HAL_INVALID_PARAM;
    }
    
    /* Default configuration: 115200 8N1 */
    hsx_uart_config_t config = {
        .baud = HSX_UART_BAUD_115200,
        .parity = HSX_UART_PARITY_NONE,
        .stop_bits = HSX_UART_STOP_1,
    };
    
    return hsx_uart_config(port, &config);
}

int hsx_uart_config(uint8_t port, const hsx_uart_config_t* config) {
    if (port >= 3 || !config) {
        return HSX_HAL_INVALID_PARAM;
    }
    
    /* Call UART_CONFIG syscall (0x10, 0x02) */
    register uint32_t r0 asm("r0");
    register uint32_t r1 asm("r1") = port;
    register uint32_t r2 asm("r2") = config->baud;
    register uint32_t r3 asm("r3") = (config->parity << 8) | config->stop_bits;
    
    asm volatile (
        "svc #0x1002"  /* Module 0x10, function 0x02 */
        : "=r"(r0)
        : "r"(r1), "r"(r2), "r"(r3)
        : "memory"
    );
    
    return (r0 == 0) ? HSX_HAL_OK : HSX_HAL_ERROR;
}

int hsx_uart_write(uint8_t port, const void* data, uint32_t length) {
    if (port >= 3 || !data || length == 0) {
        return HSX_HAL_INVALID_PARAM;
    }
    
    /* Call UART_WRITE syscall (0x10, 0x00) */
    register uint32_t r0 asm("r0");
    register uint32_t r1 asm("r1") = port;
    register uint32_t r2 asm("r2") = (uint32_t)data;
    register uint32_t r3 asm("r3") = length;
    
    asm volatile (
        "svc #0x1000"  /* Module 0x10, function 0x00 */
        : "=r"(r0)
        : "r"(r1), "r"(r2), "r"(r3)
        : "memory"
    );
    
    return (int)r0;  /* Returns bytes written or negative error */
}

int hsx_uart_read(uint8_t port, void* buffer, uint32_t max_length, uint32_t timeout_ms) {
    if (port >= 3 || !buffer || max_length == 0) {
        return HSX_HAL_INVALID_PARAM;
    }
    
    /* Open RX mailbox if not already open */
    if (uart_state[port].rx_mailbox_handle == 0) {
        char mbx_name[32];
        snprintf(mbx_name, sizeof(mbx_name), "hal:uart:%d:rx", port);
        
        /* Call MAILBOX_OPEN (module 0x05, function 0x00) */
        register uint32_t r0 asm("r0");
        register uint32_t r1 asm("r1") = (uint32_t)mbx_name;
        register uint32_t r2 asm("r2") = 0x01;  /* RDONLY */
        
        asm volatile (
            "svc #0x0500"
            : "=r"(r0), "=r"(r1)
            : "r"(r1), "r"(r2)
            : "memory"
        );
        
        if (r0 != 0) {
            return HSX_HAL_ERROR;
        }
        
        uart_state[port].rx_mailbox_handle = r1;
    }
    
    /* Call MAILBOX_RECV (module 0x05, function 0x03) */
    register uint32_t r0 asm("r0");
    register uint32_t r1 asm("r1") = uart_state[port].rx_mailbox_handle;
    register uint32_t r2 asm("r2") = (uint32_t)buffer;
    register uint32_t r3 asm("r3") = max_length;
    register uint32_t r4 asm("r4") = timeout_ms;
    
    asm volatile (
        "svc #0x0503"
        : "=r"(r0), "=r"(r1)
        : "r"(r1), "r"(r2), "r"(r3), "r"(r4)
        : "memory"
    );
    
    if (r0 != 0) {
        return (r0 == 1) ? HSX_HAL_TIMEOUT : HSX_HAL_ERROR;
    }
    
    return (int)r1;  /* Returns bytes received */
}

int hsx_uart_printf(uint8_t port, const char* format, ...) {
    char buffer[256];
    va_list args;
    
    va_start(args, format);
    int len = vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    
    if (len < 0 || len >= sizeof(buffer)) {
        return HSX_HAL_ERROR;
    }
    
    return hsx_uart_write(port, buffer, len);
}

/* Additional functions omitted for brevity */
```

## Build System Integration

### Makefile for libhsx_hal

```makefile
# libhsx_hal Makefile

CC = hsx-gcc
AR = hsx-ar
CFLAGS = -Wall -Wextra -O2 -Iinclude
LDFLAGS = 

SOURCES = $(wildcard src/*.c)
OBJECTS = $(SOURCES:.c=.o)
LIBRARY = libhsx_hal.a

all: $(LIBRARY)

$(LIBRARY): $(OBJECTS)
	$(AR) rcs $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(LIBRARY)

install: $(LIBRARY)
	install -d $(DESTDIR)/usr/lib/hsx
	install -m 644 $(LIBRARY) $(DESTDIR)/usr/lib/hsx/
	install -d $(DESTDIR)/usr/include/hsx
	install -m 644 include/*.h $(DESTDIR)/usr/include/hsx/

.PHONY: all clean install
```

### Application Makefile Example

```makefile
# Example application Makefile

APP = my_hsx_app
SOURCES = main.c sensors.c actuators.c
OBJECTS = $(SOURCES:.c=.o)

CC = hsx-gcc
CFLAGS = -Wall -Wextra -O2 -I/usr/include/hsx
LDFLAGS = -L/usr/lib/hsx -lhsx_hal

all: $(APP).hxe

$(APP).hxe: $(OBJECTS)
	$(CC) $(LDFLAGS) -o $@ $^

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJECTS) $(APP).hxe

.PHONY: all clean
```

## Example Application Code

### Simple UART Echo

```c
#include <hsx_uart.h>

int main(void) {
    char buffer[128];
    
    /* Initialize UART 0 */
    hsx_uart_init(HSX_UART_0);
    
    hsx_uart_printf(HSX_UART_0, "UART echo started\n");
    
    while (1) {
        /* Blocking read from UART */
        int len = hsx_uart_read(HSX_UART_0, buffer, sizeof(buffer) - 1, 
                                HSX_HAL_TIMEOUT_INF);
        
        if (len > 0) {
            buffer[len] = '\0';
            hsx_uart_printf(HSX_UART_0, "Echo: %s\n", buffer);
        }
    }
    
    return 0;
}
```

### GPIO Interrupt Handler

```c
#include <hsx_gpio.h>
#include <hsx_uart.h>

static void button_callback(void* event_data, uint32_t length, void* user_data) {
    hsx_gpio_event_t* event = (hsx_gpio_event_t*)event_data;
    
    if (event->edge == HSX_GPIO_EDGE_RISING) {
        hsx_uart_printf(HSX_UART_0, "Button pressed on pin %d\n", event->pin);
    }
}

int main(void) {
    /* Initialize UART for debug output */
    hsx_uart_init(HSX_UART_0);
    
    /* Configure GPIO pin 5 as input with pull-up */
    hsx_gpio_config(5, HSX_GPIO_MODE_INPUT, HSX_GPIO_PULL_UP);
    
    /* Enable interrupt on rising edge */
    hsx_gpio_set_interrupt(5, HSX_GPIO_EDGE_RISING, true);
    
    /* Register callback */
    hsx_gpio_set_interrupt_callback(5, button_callback, NULL);
    
    hsx_uart_printf(HSX_UART_0, "Waiting for button press...\n");
    
    /* Event loop - callback handles events */
    while (1) {
        hsx_timer_sleep_ms(1000);
    }
    
    return 0;
}
```

### CAN Bus Monitor

```c
#include <hsx_can.h>
#include <hsx_uart.h>

int main(void) {
    hsx_can_frame_t frame;
    
    /* Initialize peripherals */
    hsx_uart_init(HSX_UART_0);
    hsx_can_init();
    hsx_can_config(HSX_CAN_BITRATE_500K, 0);
    
    hsx_uart_printf(HSX_UART_0, "CAN bus monitor started\n");
    
    while (1) {
        /* Blocking receive with 1 second timeout */
        if (hsx_can_rx(&frame, 1000) == HSX_HAL_OK) {
            hsx_uart_printf(HSX_UART_0, "CAN ID=0x%03X DLC=%d Data=",
                           frame.can_id, frame.dlc);
            
            for (int i = 0; i < frame.dlc; i++) {
                hsx_uart_printf(HSX_UART_0, "%02X ", frame.data[i]);
            }
            
            hsx_uart_printf(HSX_UART_0, "\n");
        }
    }
    
    return 0;
}
```

## Summary

This two-layer architecture provides:

1. **Executive-Space HAL** - Thin wrappers in the executive that handle hardware operations via syscalls and post events to mailboxes
2. **User-Space HAL** - Convenient libraries that abstract syscall/mailbox details from applications

**Benefits:**
- Applications don't need to know if operations use syscalls or mailboxes
- Clean API that's easy to use
- Consistent error handling and types
- Event-driven programming with callbacks
- Blocking and non-blocking operations available
- Easy to port applications between platforms

**Next Steps:**
1. Create header files in `include/` directory
2. Implement executive-side HAL modules in `exec/hal/`
3. Implement user-space libraries in `libhsx_hal/src/`
4. Create examples demonstrating each module
5. Add Python mock implementations for testing
