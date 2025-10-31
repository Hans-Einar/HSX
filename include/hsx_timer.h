#ifndef HSX_TIMER_H
#define HSX_TIMER_H

#include "hsx_hal_types.h"

/*
 * HSX Timer HAL - User-space library interface
 * 
 * Provides convenient API for timer operations:
 * - Monotonic tick counter (via syscall)
 * - Sleep operations (via EXEC syscall)
 * - Periodic/one-shot timers with callbacks (via mailbox)
 */

/* Timer types */
typedef enum {
    HSX_TIMER_ONE_SHOT = 0,
    HSX_TIMER_PERIODIC = 1,
} hsx_timer_type_t;

/* Timer handle (opaque) */
typedef uint16_t hsx_timer_t;

/* Timer event data (delivered via mailbox) */
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
 * Sleep for specified microseconds.
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
