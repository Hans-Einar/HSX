#ifndef HSX_CAN_H
#define HSX_CAN_H

#include "hsx_hal_types.h"

/*
 * HSX CAN HAL - User-space library interface
 * 
 * Provides convenient API for CAN operations:
 * - Synchronous transmit (via syscall)
 * - Blocking receive (via mailbox)
 * - Event-driven RX with callbacks (via mailbox)
 */

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

/* CAN RX event data (delivered via mailbox) */
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
