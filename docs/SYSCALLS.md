# 🧩 HSX System Calls (SVC Interface)

---

## 🧠 Overview
System calls (SVC) provide the interface between HSX user programs and the Executive/HAL.
All SVC instructions use the format:

```
SVC <mod>, <fn>, Rn, Rm
```
where `<mod>` selects subsystem, and `<fn>` selects function within it.

Return values are placed in `R0`.

---

## 🔌 Module 0x01 – UART / Serial I/O

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `UART_WRITE` | R1: ptr, R2: len | R0 = bytes written | Write raw bytes to UART. |
| 0x01 | `UART_WRITE_INT` | R1: int value | none | Convert integer to ASCII and send. |
| 0x02 | `UART_WRITE_F16` | R1: f16 value | none | Convert f16 to ASCII and send. |
| 0x03 | `UART_WRITE_BOOL` | R1: bool (0/1) | none | Send "false"/"true". |
| 0x04 | `UART_WRITE_LN` | none | none | Send CRLF (like Serial.println). |

Example (C binding):
```c
hsx_svc(0x01, 0x02, *(uint16_t*)&f16_val, 0);
```

---

## 💾 Module 0x02 – File System (FS)

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `FS_OPEN` | R1: ptr to filename | R0 = fd | Open file for read/write. |
| 0x01 | `FS_READ` | R1: fd, R2: ptr, R3: len | R0 = bytes read | Read from file. |
| 0x02 | `FS_WRITE` | R1: fd, R2: ptr, R3: len | R0 = bytes written | Write to file. |
| 0x03 | `FS_CLOSE` | R1: fd | none | Close handle. |
| 0x04 | `FS_LIST` | R1: ptr, R2: max | R0 = entries | List files. |

---

## 📡 Module 0x03 – CAN / Network

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `CAN_TX` | R1: ptr to frame | R0 = 0 on success | Send CAN frame. |
| 0x01 | `CAN_RX` | R1: ptr buffer | R0 = bytes | Receive CAN frame (blocking). |
| 0x02 | `CAN_STATUS` | none | bitmask | Get controller state. |

---

## 🕹️ Module 0x04 – GPIO / Timers

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `GPIO_READ` | R1: pin | R0 = value | Read digital input. |
| 0x01 | `GPIO_WRITE` | R1: pin, R2: val | none | Set output. |
| 0x02 | `PWM_SET` | R1: channel, R2: duty | none | Configure PWM. |
| 0x03 | `TIMER_WAIT` | R1: ms | none | Delay. |

---

## 📨 Module 0x05 – Mailbox / Event System

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `MBX_SEND` | R1: box_id, R2: ptr, R3: len | R0 = 0 on success | Post message. |
| 0x01 | `MBX_RECV` | R1: box_id, R2: ptr, R3: max | R0 = len | Wait for message. |
| 0x02 | `MBX_CHECK` | R1: box_id | R0 = count | Return pending count. |

---

## 🔢 Module 0x06 – Value Interface

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `VAL_READ` | R1: id | R0 = f16 | Read shared value. |
| 0x01 | `VAL_WRITE` | R1: id, R2: f16 | none | Write shared value. |
| 0x02 | `VAL_LIST` | R1: ptr | R0 = count | Enumerate available values. |

---

## ⚙️ Module 0x07 – System / Exec Control

| Fn | Name | Params | Return | Description |
|----|------|---------|---------|--------------|
| 0x00 | `EXEC_EXIT` | R1: code | none | Terminate task. |
| 0x01 | `EXEC_YIELD` | none | none | Cooperative yield. |
| 0x02 | `EXEC_TASKLIST` | R1: ptr | R0 = count | List running tasks. |

---

## 🧩 Return Conventions
- `R0` always holds return value (if any).  
- On error, `R0` contains **negative error code** (`-1`, `-2`, etc).  
- Syscalls are **blocking** unless specified.

---

**Maintainer:** Hans Einar (HSX Project)**  
**Updated:** 2025-10-04  
