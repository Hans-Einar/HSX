#ifndef HSX_GPIO_H
#define HSX_GPIO_H

#include "hsx_hal_types.h"

/*
 * HSX GPIO HAL - User-space library interface
 * 
 * Provides convenient API for GPIO operations:
 * - Synchronous read/write (via syscall)
 * - Event-driven interrupts with callbacks (via mailbox)
 */

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

/* GPIO event data (delivered via mailbox) */
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
