#ifndef HSX_FRAM_H
#define HSX_FRAM_H

#include "hsx_hal_types.h"

/*
 * HSX FRAM HAL - User-space library interface
 * 
 * Provides convenient API for FRAM (persistent memory) operations:
 * - Synchronous read/write (via syscall)
 * - Type-safe macros for reading/writing variables
 */

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
 * @return HSX_HAL_OK on success, error code otherwise
 */
#define hsx_fram_read_var(addr, var) \
    hsx_fram_read((addr), &(var), sizeof(var))

/**
 * Write variable to FRAM with type safety.
 * 
 * @param addr FRAM address
 * @param var Variable to write
 * @return Number of bytes written, or negative error code
 */
#define hsx_fram_write_var(addr, var) \
    hsx_fram_write((addr), &(var), sizeof(var))

#endif /* HSX_FRAM_H */
