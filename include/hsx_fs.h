#ifndef HSX_FS_H
#define HSX_FS_H

#include "hsx_hal_types.h"

/*
 * HSX Filesystem HAL - User-space library interface
 * 
 * Provides POSIX-like filesystem API:
 * - File operations: open, read, write, close (via syscall)
 * - Directory operations: listdir, mkdir, delete, rename (via syscall)
 */

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
int hsx_fs_printf(hsx_fd_t fd, const char* format, ...) __attribute__((format(printf, 2, 3)));

#endif /* HSX_FS_H */
