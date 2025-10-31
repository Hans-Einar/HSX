#ifndef HSX_UART_H
#define HSX_UART_H

#include "hsx_hal_types.h"

/*
 * HSX UART HAL - User-space library interface
 * 
 * Provides convenient API for UART operations:
 * - Synchronous transmit (via syscall)
 * - Blocking/non-blocking receive (via syscall or mailbox)
 * - Event-driven RX with callbacks (via mailbox)
 */

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
#define HSX_UART_STATUS_TX_READY   0x01
#define HSX_UART_STATUS_RX_READY   0x02
#define HSX_UART_STATUS_OVERRUN    0x04
#define HSX_UART_STATUS_PARITY_ERR 0x08

/* UART RX event data (delivered via mailbox) */
typedef struct {
    uint8_t port;
    uint8_t data[32];
    uint8_t length;
    uint8_t flags;
} hsx_uart_rx_event_t;

/**
 * Initialize UART port with default configuration (115200 8N1).
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
int hsx_uart_printf(uint8_t port, const char* format, ...) __attribute__((format(printf, 2, 3)));

#endif /* HSX_UART_H */
