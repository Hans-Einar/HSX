# Python HAL Implementation Design

**Status:** DESIGN | **Date:** 2025-10-31 | **Owner:** HSX Core

> **Purpose:** Defines Python-based HAL modules for development and testing. Includes GUI emulation for GPIO, filesystem access, and thoughts on device driver architecture (I2C, SPI, IMU sensors).

## Overview

The Python HAL implementation serves multiple purposes:
1. **Development platform** - Test HSX applications without hardware
2. **CI/CD testing** - Automated testing of HAL-dependent code
3. **Prototyping** - Rapid iteration on HAL interfaces
4. **Cross-platform** - Run HSX apps on Linux, macOS, Windows

## Python HAL Module Structure

```text
platforms/python/hal/
├── __init__.py           # HAL module exports
├── hal_base.py           # Base class for HAL modules
├── uart_hal.py           # UART implementation (sockets, files)
├── can_hal.py            # CAN implementation (virtual bus)
├── gpio_hal.py           # GPIO implementation (GUI or CLI)
├── timer_hal.py          # Timer implementation (threading)
├── fram_hal.py           # FRAM implementation (file-backed)
├── fs_hal.py             # Filesystem implementation (host access)
├── i2c_hal.py            # I2C bus emulation
├── spi_hal.py            # SPI bus emulation
├── devices/              # Device drivers
│   ├── __init__.py
│   ├── imu_mpu6050.py    # MPU6050 IMU emulator
│   ├── imu_bmi088.py     # BMI088 IMU emulator
│   ├── display_7seg.py   # 7-segment display emulator
│   └── sensor_generic.py # Generic sensor interface
└── gui/                  # GUI components
    ├── __init__.py
    ├── gpio_panel.py     # GPIO control panel (tkinter)
    ├── can_monitor.py    # CAN bus monitor
    └── system_view.py    # System overview
```

## Core HAL Module Implementations

### UART HAL (uart_hal.py)

**Implementation Strategy:**
- Use Python `socket` for inter-process UART
- Use files for logging UART traffic
- Support multiple virtual UART ports

```python
"""
Python UART HAL Implementation
"""
import socket
import threading
import queue
from typing import Optional, Callable

class UARTPort:
    def __init__(self, port_id: int):
        self.port_id = port_id
        self.baud = 115200
        self.rx_queue = queue.Queue()
        self.socket: Optional[socket.socket] = None
        self.rx_thread: Optional[threading.Thread] = None
        self.running = False
        
    def configure(self, baud: int, parity: str, stop_bits: int) -> int:
        """Configure UART parameters"""
        self.baud = baud
        # In simulation, these are mostly informational
        return 0
    
    def write(self, data: bytes) -> int:
        """Write data to UART (synchronous)"""
        if self.socket:
            try:
                self.socket.sendall(data)
                return len(data)
            except:
                pass
        # Fallback: print to stdout
        print(f"[UART{self.port_id} TX] {data.decode('utf-8', errors='ignore')}")
        return len(data)
    
    def read_poll(self, max_len: int) -> bytes:
        """Non-blocking read (returns immediately)"""
        try:
            data = self.rx_queue.get_nowait()
            return data[:max_len]
        except queue.Empty:
            return b''
    
    def read_blocking(self, max_len: int, timeout_ms: int) -> bytes:
        """Blocking read with timeout"""
        timeout_s = timeout_ms / 1000.0 if timeout_ms != 0xFFFFFFFF else None
        try:
            data = self.rx_queue.get(timeout=timeout_s)
            return data[:max_len]
        except queue.Empty:
            return b''
    
    def _rx_thread_func(self):
        """Background thread for receiving data"""
        while self.running:
            try:
                data = self.socket.recv(1024)
                if data:
                    self.rx_queue.put(data)
            except:
                pass
    
    def connect_socket(self, host: str, port: int):
        """Connect to TCP socket for UART data"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((host, port))
        self.running = True
        self.rx_thread = threading.Thread(target=self._rx_thread_func, daemon=True)
        self.rx_thread.start()

class UART_HAL:
    def __init__(self):
        self.ports = {
            0: UARTPort(0),
            1: UARTPort(1),
            2: UARTPort(2),
        }
        self.mailbox_manager = None
    
    def set_mailbox_manager(self, mbx_mgr):
        """Link to mailbox manager for posting RX events"""
        self.mailbox_manager = mbx_mgr
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle UART syscalls (module 0x10)"""
        if fn == 0x00:  # UART_WRITE
            port = args['port']
            data = args['data']
            bytes_written = self.ports[port].write(data)
            return {'status': 0, 'bytes_written': bytes_written}
        
        elif fn == 0x01:  # UART_READ_POLL
            port = args['port']
            max_len = args['max_len']
            data = self.ports[port].read_poll(max_len)
            return {'status': 0, 'data': data, 'bytes_read': len(data)}
        
        elif fn == 0x02:  # UART_CONFIG
            port = args['port']
            baud = args['baud']
            status = self.ports[port].configure(baud, 'N', 1)
            return {'status': status}
        
        elif fn == 0x03:  # UART_GET_STATUS
            # Return status flags (always ready in simulation)
            return {'status': 0, 'flags': 0x03}  # TX_READY | RX_READY
        
        return {'status': -1}  # HSX_HAL_ERROR
    
    def post_rx_event(self, port_id: int, data: bytes):
        """Post RX data to mailbox"""
        if self.mailbox_manager:
            mbx_name = f"hal:uart:{port_id}:rx"
            event = {
                'port': port_id,
                'data': data,
                'length': len(data),
                'flags': 0
            }
            # Serialize event and post to mailbox
            self.mailbox_manager.post_event(mbx_name, event)
```

### GPIO HAL with GUI (gpio_hal.py)

**Implementation Strategy:**
- Use `tkinter` for GUI (cross-platform)
- Checkboxes for input pins (user can click)
- LEDs for output pins (visual feedback)
- Support interrupt generation

```python
"""
Python GPIO HAL Implementation with GUI
"""
import tkinter as tk
from tkinter import ttk
import threading
from typing import Dict, Optional, Callable
from enum import Enum

class GPIOMode(Enum):
    INPUT = 0
    OUTPUT = 1
    ANALOG = 2

class GPIOEdge(Enum):
    NONE = 0
    RISING = 1
    FALLING = 2
    BOTH = 3

class GPIOPin:
    def __init__(self, pin_num: int):
        self.pin_num = pin_num
        self.mode = GPIOMode.INPUT
        self.pull = None
        self.value = 0
        self.last_value = 0
        self.interrupt_enabled = False
        self.interrupt_edge = GPIOEdge.NONE
        
        # GUI elements (created by GUI thread)
        self.checkbox: Optional[tk.Checkbutton] = None
        self.led_canvas: Optional[tk.Canvas] = None
        self.label: Optional[tk.Label] = None

class GPIO_HAL:
    def __init__(self, num_pins: int = 16):
        self.pins: Dict[int, GPIOPin] = {
            i: GPIOPin(i) for i in range(num_pins)
        }
        self.mailbox_manager = None
        self.gui_window: Optional[tk.Tk] = None
        self.gui_thread: Optional[threading.Thread] = None
        
    def set_mailbox_manager(self, mbx_mgr):
        """Link to mailbox manager for posting interrupt events"""
        self.mailbox_manager = mbx_mgr
    
    def start_gui(self):
        """Start GPIO GUI in separate thread"""
        self.gui_thread = threading.Thread(target=self._create_gui, daemon=True)
        self.gui_thread.start()
    
    def _create_gui(self):
        """Create tkinter GUI for GPIO control"""
        self.gui_window = tk.Tk()
        self.gui_window.title("HSX GPIO Panel")
        self.gui_window.geometry("400x600")
        
        # Title
        title = tk.Label(self.gui_window, text="GPIO Pins", 
                        font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        # Create frame with scrollbar
        container = tk.Frame(self.gui_window)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Create GPIO pin controls
        for pin_num, pin in self.pins.items():
            self._create_pin_control(scrollable_frame, pin)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.gui_window.mainloop()
    
    def _create_pin_control(self, parent: tk.Frame, pin: GPIOPin):
        """Create control widgets for a single GPIO pin"""
        frame = tk.Frame(parent, relief=tk.RIDGE, borderwidth=2)
        frame.pack(fill=tk.X, padx=5, pady=3)
        
        # Pin number label
        label = tk.Label(frame, text=f"Pin {pin.pin_num:02d}", 
                        font=("Arial", 10, "bold"), width=8)
        label.pack(side=tk.LEFT, padx=5)
        pin.label = label
        
        # Mode indicator
        mode_label = tk.Label(frame, text="INPUT", 
                             font=("Arial", 9), width=8, fg="blue")
        mode_label.pack(side=tk.LEFT, padx=5)
        
        # LED indicator (for output mode)
        led_canvas = tk.Canvas(frame, width=20, height=20, bg="white")
        led_canvas.pack(side=tk.LEFT, padx=5)
        led_circle = led_canvas.create_oval(2, 2, 18, 18, fill="gray", outline="black")
        pin.led_canvas = led_canvas
        pin.led_circle = led_circle
        
        # Checkbox (for input mode)
        var = tk.IntVar(value=0)
        checkbox = tk.Checkbutton(
            frame, text="High", variable=var,
            command=lambda: self._on_input_change(pin.pin_num, var.get())
        )
        checkbox.pack(side=tk.LEFT, padx=5)
        pin.checkbox = checkbox
        pin.checkbox_var = var
        
        # Interrupt indicator
        int_label = tk.Label(frame, text="", font=("Arial", 8), fg="red")
        int_label.pack(side=tk.LEFT, padx=5)
        pin.interrupt_label = int_label
        
        # Store references
        pin.mode_label = mode_label
    
    def _on_input_change(self, pin_num: int, new_value: int):
        """Called when user clicks input checkbox"""
        pin = self.pins[pin_num]
        
        if pin.mode == GPIOMode.INPUT:
            old_value = pin.value
            pin.value = new_value
            
            # Check for interrupt
            if pin.interrupt_enabled:
                edge_detected = False
                
                if pin.interrupt_edge == GPIOEdge.RISING and old_value == 0 and new_value == 1:
                    edge_detected = True
                    edge_type = GPIOEdge.RISING
                elif pin.interrupt_edge == GPIOEdge.FALLING and old_value == 1 and new_value == 0:
                    edge_detected = True
                    edge_type = GPIOEdge.FALLING
                elif pin.interrupt_edge == GPIOEdge.BOTH and old_value != new_value:
                    edge_detected = True
                    edge_type = GPIOEdge.RISING if new_value == 1 else GPIOEdge.FALLING
                
                if edge_detected:
                    self._trigger_interrupt(pin_num, edge_type, new_value)
    
    def _trigger_interrupt(self, pin_num: int, edge: GPIOEdge, value: int):
        """Post interrupt event to mailbox"""
        pin = self.pins[pin_num]
        
        # Flash interrupt indicator
        if pin.interrupt_label:
            pin.interrupt_label.config(text="INT!")
            self.gui_window.after(500, lambda: pin.interrupt_label.config(text=""))
        
        # Post to mailbox
        if self.mailbox_manager:
            mbx_name = f"hal:gpio:{pin_num}"
            event = {
                'pin': pin_num,
                'edge': edge.value,
                'value': value,
                'timestamp': 0  # Would use timer tick in real impl
            }
            self.mailbox_manager.post_event(mbx_name, event)
    
    def _update_led(self, pin_num: int):
        """Update LED visualization for output pin"""
        pin = self.pins[pin_num]
        if pin.led_canvas and hasattr(pin, 'led_circle'):
            color = "green" if pin.value else "gray"
            pin.led_canvas.itemconfig(pin.led_circle, fill=color)
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle GPIO syscalls (module 0x15)"""
        if fn == 0x00:  # GPIO_READ
            pin_num = args['pin']
            value = self.pins[pin_num].value
            return {'status': 0, 'value': value}
        
        elif fn == 0x01:  # GPIO_WRITE
            pin_num = args['pin']
            value = args['value']
            pin = self.pins[pin_num]
            
            if pin.mode == GPIOMode.OUTPUT:
                pin.value = value
                if self.gui_window:
                    self.gui_window.after(0, lambda: self._update_led(pin_num))
                return {'status': 0}
            else:
                return {'status': -4}  # HSX_HAL_INVALID_PARAM
        
        elif fn == 0x02:  # GPIO_CONFIG
            pin_num = args['pin']
            mode = GPIOMode(args['mode'])
            pull = args.get('pull', 0)
            
            pin = self.pins[pin_num]
            pin.mode = mode
            pin.pull = pull
            
            # Update GUI
            if self.gui_window and hasattr(pin, 'mode_label'):
                mode_text = mode.name
                self.gui_window.after(0, lambda: pin.mode_label.config(text=mode_text))
            
            return {'status': 0}
        
        elif fn == 0x03:  # GPIO_SET_INTERRUPT
            pin_num = args['pin']
            edge = GPIOEdge(args['edge'])
            enable = args['enable']
            
            pin = self.pins[pin_num]
            pin.interrupt_enabled = enable
            pin.interrupt_edge = edge
            
            # Update GUI
            if self.gui_window and hasattr(pin, 'interrupt_label'):
                text = f"INT:{edge.name[:3]}" if enable else ""
                self.gui_window.after(0, lambda: pin.interrupt_label.config(text=text))
            
            return {'status': 0}
        
        return {'status': -1}
```

### CAN HAL (can_hal.py)

**Implementation Strategy:**
- Virtual CAN bus (all instances share)
- Thread-safe message queue
- Optional GUI monitor

```python
"""
Python CAN HAL Implementation
"""
import threading
import queue
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class CANFrame:
    can_id: int
    dlc: int
    flags: int
    data: bytes
    timestamp: float

class VirtualCANBus:
    """Singleton virtual CAN bus shared by all CAN HAL instances"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.subscribers = []
                    cls._instance.bus_lock = threading.Lock()
        return cls._instance
    
    def subscribe(self, callback):
        """Subscribe to CAN frames"""
        with self.bus_lock:
            self.subscribers.append(callback)
    
    def transmit(self, frame: CANFrame):
        """Transmit frame to all subscribers"""
        with self.bus_lock:
            for callback in self.subscribers:
                try:
                    callback(frame)
                except:
                    pass

class CAN_HAL:
    def __init__(self):
        self.bitrate = 500000
        self.virtual_bus = VirtualCANBus()
        self.rx_queue = queue.Queue(maxsize=100)
        self.filters: Dict[int, tuple] = {}  # filter_id -> (mask, id)
        self.mailbox_manager = None
        
        # Subscribe to virtual bus
        self.virtual_bus.subscribe(self._on_frame_received)
    
    def set_mailbox_manager(self, mbx_mgr):
        """Link to mailbox manager for posting RX events"""
        self.mailbox_manager = mbx_mgr
    
    def _on_frame_received(self, frame: CANFrame):
        """Called when frame arrives on virtual bus"""
        # Apply filters
        if self.filters:
            accepted = False
            for mask, filter_id in self.filters.values():
                if (frame.can_id & mask) == (filter_id & mask):
                    accepted = True
                    break
            if not accepted:
                return
        
        # Add to RX queue
        try:
            self.rx_queue.put_nowait(frame)
            
            # Post to mailbox
            if self.mailbox_manager:
                event = {
                    'can_id': frame.can_id,
                    'dlc': frame.dlc,
                    'flags': frame.flags,
                    'data': frame.data,
                    'timestamp': int(frame.timestamp * 1e6)
                }
                self.mailbox_manager.post_event("hal:can:rx", event)
        except queue.Full:
            pass  # Drop frame if queue full
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle CAN syscalls (module 0x11)"""
        if fn == 0x00:  # CAN_TX
            frame = CANFrame(
                can_id=args['can_id'],
                dlc=args['dlc'],
                flags=args.get('flags', 0),
                data=args['data'],
                timestamp=time.time()
            )
            self.virtual_bus.transmit(frame)
            return {'status': 0}
        
        elif fn == 0x01:  # CAN_CONFIG
            self.bitrate = args['bitrate']
            return {'status': 0}
        
        elif fn == 0x02:  # CAN_SET_FILTER
            filter_id = args['filter_id']
            mask = args['mask']
            can_id = args['id']
            self.filters[filter_id] = (mask, can_id)
            return {'status': 0}
        
        elif fn == 0x03:  # CAN_GET_STATUS
            return {'status': 0, 'flags': 0}
        
        return {'status': -1}
```

### Filesystem HAL (fs_hal.py)

**Implementation Strategy:**
- Map to `hal_drive/` directory on host
- Isolate HSX apps from full filesystem access
- Support all standard file operations

```python
"""
Python Filesystem HAL Implementation
"""
import os
from pathlib import Path
from typing import Dict, Optional

class FS_HAL:
    def __init__(self, base_dir: str = "hal_drive"):
        self.base_dir = Path(base_dir).absolute()
        self.base_dir.mkdir(exist_ok=True)
        
        self.fd_table: Dict[int, Optional[object]] = {}
        self.next_fd = 3  # 0, 1, 2 reserved for stdin, stdout, stderr
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_dir, prevent escaping"""
        if path.startswith('/'):
            path = path[1:]
        
        full_path = (self.base_dir / path).resolve()
        
        # Security: ensure path is within base_dir
        try:
            full_path.relative_to(self.base_dir)
        except ValueError:
            raise PermissionError("Path outside hal_drive")
        
        return full_path
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle filesystem syscalls (module 0x14)"""
        if fn == 0x00:  # FS_OPEN
            path = args['path']
            flags = args['flags']
            
            try:
                full_path = self._resolve_path(path)
                
                # Convert HSX flags to Python mode
                mode = 'r'
                if flags & 0x0002:  # WRONLY
                    mode = 'w'
                elif flags & 0x0003:  # RDWR
                    mode = 'r+'
                
                if flags & 0x0004:  # CREAT
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    mode += '+'
                
                if flags & 0x0010:  # APPEND
                    mode = 'a' if 'w' in mode else 'a+'
                
                # Open file
                file_obj = open(full_path, mode + 'b')
                
                fd = self.next_fd
                self.next_fd += 1
                self.fd_table[fd] = file_obj
                
                return {'status': 0, 'fd': fd}
            except Exception as e:
                print(f"FS_OPEN error: {e}")
                return {'status': -1, 'fd': -1}
        
        elif fn == 0x01:  # FS_READ
            fd = args['fd']
            max_len = args['length']
            
            if fd not in self.fd_table:
                return {'status': -1, 'data': b'', 'bytes_read': 0}
            
            try:
                data = self.fd_table[fd].read(max_len)
                return {'status': 0, 'data': data, 'bytes_read': len(data)}
            except:
                return {'status': -1, 'data': b'', 'bytes_read': 0}
        
        elif fn == 0x02:  # FS_WRITE
            fd = args['fd']
            data = args['data']
            
            if fd not in self.fd_table:
                return {'status': -1, 'bytes_written': 0}
            
            try:
                self.fd_table[fd].write(data)
                return {'status': 0, 'bytes_written': len(data)}
            except:
                return {'status': -1, 'bytes_written': 0}
        
        elif fn == 0x03:  # FS_CLOSE
            fd = args['fd']
            
            if fd in self.fd_table:
                try:
                    self.fd_table[fd].close()
                    del self.fd_table[fd]
                    return {'status': 0}
                except:
                    pass
            
            return {'status': -1}
        
        elif fn == 0x0A:  # FS_LISTDIR
            path = args['path']
            
            try:
                full_path = self._resolve_path(path)
                files = os.listdir(full_path)
                listing = '\n'.join(files)
                return {'status': 0, 'data': listing.encode('utf-8')}
            except:
                return {'status': -1, 'data': b''}
        
        elif fn == 0x0B:  # FS_DELETE
            path = args['path']
            
            try:
                full_path = self._resolve_path(path)
                full_path.unlink()
                return {'status': 0}
            except:
                return {'status': -1}
        
        elif fn == 0x0C:  # FS_RENAME
            old_path = args['old_path']
            new_path = args['new_path']
            
            try:
                old_full = self._resolve_path(old_path)
                new_full = self._resolve_path(new_path)
                old_full.rename(new_full)
                return {'status': 0}
            except:
                return {'status': -1}
        
        elif fn == 0x0D:  # FS_MKDIR
            path = args['path']
            
            try:
                full_path = self._resolve_path(path)
                full_path.mkdir(parents=True, exist_ok=True)
                return {'status': 0}
            except:
                return {'status': -1}
        
        return {'status': -1}
```

## I2C and SPI Bus Emulation

### Design Philosophy

For device drivers (IMU, sensors), we have two approaches:

**Approach 1: Bus-Level Emulation (More Flexible)**
- Emulate I2C/SPI at bus level
- HSX apps use I2C/SPI HAL syscalls
- Device drivers run on HSX side
- Pro: Same code runs on real hardware
- Con: More overhead, slower in Python

**Approach 2: Virtual Device Drivers (More Practical)**
- Emulate devices, not buses
- HSX apps use high-level device APIs
- Device drivers run on host side (Python or C)
- Pro: Fast, easy to test
- Con: Device-specific code on both sides

**Recommendation for CAN Nodes:**
Use **Approach 2** for production, **Approach 1** for development.

### I2C HAL (i2c_hal.py)

```python
"""
Python I2C HAL Implementation
"""
from typing import Dict, Optional

class I2CDevice:
    """Base class for I2C device emulators"""
    def __init__(self, address: int):
        self.address = address
    
    def read_register(self, reg: int) -> int:
        """Read from device register"""
        raise NotImplementedError
    
    def write_register(self, reg: int, value: int):
        """Write to device register"""
        raise NotImplementedError
    
    def read_bytes(self, reg: int, length: int) -> bytes:
        """Read multiple bytes"""
        raise NotImplementedError

class I2C_HAL:
    def __init__(self):
        self.devices: Dict[int, I2CDevice] = {}
        self.bus_speed = 100000  # 100 kHz
    
    def register_device(self, address: int, device: I2CDevice):
        """Register virtual I2C device on bus"""
        self.devices[address] = device
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle I2C syscalls (module 0x17, if added)"""
        if fn == 0x00:  # I2C_WRITE
            address = args['address']
            data = args['data']
            
            if address in self.devices:
                device = self.devices[address]
                # First byte is register, rest is data
                if len(data) >= 2:
                    device.write_register(data[0], data[1])
                return {'status': 0}
            else:
                return {'status': -1}  # Device not found
        
        elif fn == 0x01:  # I2C_READ
            address = args['address']
            reg = args['register']
            length = args['length']
            
            if address in self.devices:
                device = self.devices[address]
                data = device.read_bytes(reg, length)
                return {'status': 0, 'data': data}
            else:
                return {'status': -1, 'data': b''}
        
        return {'status': -1}
```

### SPI HAL (spi_hal.py)

```python
"""
Python SPI HAL Implementation
"""
from typing import Dict, Optional

class SPIDevice:
    """Base class for SPI device emulators"""
    def __init__(self, cs_pin: int):
        self.cs_pin = cs_pin
    
    def transfer(self, tx_data: bytes) -> bytes:
        """SPI full-duplex transfer"""
        raise NotImplementedError

class SPI_HAL:
    def __init__(self):
        self.devices: Dict[int, SPIDevice] = {}  # cs_pin -> device
        self.mode = 0
        self.speed = 1000000  # 1 MHz
    
    def register_device(self, cs_pin: int, device: SPIDevice):
        """Register virtual SPI device"""
        self.devices[cs_pin] = device
    
    def handle_syscall(self, fn: int, args: dict) -> dict:
        """Handle SPI syscalls (module 0x18, if added)"""
        if fn == 0x00:  # SPI_TRANSFER
            cs_pin = args['cs_pin']
            tx_data = args['tx_data']
            
            if cs_pin in self.devices:
                device = self.devices[cs_pin]
                rx_data = device.transfer(tx_data)
                return {'status': 0, 'rx_data': rx_data}
            else:
                return {'status': -1, 'rx_data': b''}
        
        elif fn == 0x01:  # SPI_CONFIG
            self.mode = args['mode']
            self.speed = args['speed']
            return {'status': 0}
        
        return {'status': -1}
```

## Device Drivers

### IMU MPU6050 Emulator (devices/imu_mpu6050.py)

```python
"""
MPU6050 IMU Emulator
"""
import math
import time
from ..i2c_hal import I2CDevice

class MPU6050(I2CDevice):
    """MPU6050 6-axis IMU emulator"""
    
    # Register addresses
    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B
    GYRO_XOUT_H = 0x43
    WHO_AM_I = 0x75
    
    def __init__(self, address: int = 0x68):
        super().__init__(address)
        self.registers = bytearray(128)
        self.registers[self.WHO_AM_I] = 0x68  # Device ID
        
        # Simulated sensor state
        self.accel = [0.0, 0.0, 9.81]  # m/s^2 (resting, gravity on Z)
        self.gyro = [0.0, 0.0, 0.0]    # deg/s
        self.start_time = time.time()
    
    def _simulate_motion(self):
        """Simulate some motion for testing"""
        t = time.time() - self.start_time
        
        # Gentle oscillation
        self.accel[0] = 0.5 * math.sin(t * 0.5)
        self.accel[1] = 0.3 * math.cos(t * 0.7)
        self.gyro[2] = 10.0 * math.sin(t * 0.3)  # Yaw rotation
    
    def read_register(self, reg: int) -> int:
        if reg == self.WHO_AM_I:
            return 0x68
        return self.registers[reg]
    
    def write_register(self, reg: int, value: int):
        self.registers[reg] = value
        
        if reg == self.PWR_MGMT_1 and value == 0:
            # Wake up device
            pass
    
    def read_bytes(self, reg: int, length: int) -> bytes:
        if reg == self.ACCEL_XOUT_H:
            # Update simulated data
            self._simulate_motion()
            
            # Convert to 16-bit signed integers (LSB = 16384 for ±2g)
            accel_raw = [int(a * 16384 / 9.81) for a in self.accel]
            
            data = bytearray()
            for val in accel_raw:
                val = max(-32768, min(32767, val))
                data.append((val >> 8) & 0xFF)  # High byte
                data.append(val & 0xFF)          # Low byte
            
            return bytes(data[:length])
        
        elif reg == self.GYRO_XOUT_H:
            # Convert to 16-bit signed integers (LSB = 131 for ±250 deg/s)
            gyro_raw = [int(g * 131) for g in self.gyro]
            
            data = bytearray()
            for val in gyro_raw:
                val = max(-32768, min(32767, val))
                data.append((val >> 8) & 0xFF)
                data.append(val & 0xFF)
            
            return bytes(data[:length])
        
        return bytes(self.registers[reg:reg+length])
```

### CAN-based Sensor Device (devices/sensor_generic.py)

```python
"""
Generic CAN-based Sensor
"""
from ..can_hal import CANFrame
import time

class CANSensor:
    """Base class for CAN-connected sensors"""
    def __init__(self, node_id: int, can_hal):
        self.node_id = node_id
        self.can_hal = can_hal
        self.base_can_id = 0x100 + (node_id << 4)
    
    def send_sensor_data(self, data: dict):
        """Send sensor data via CAN"""
        # Pack data into CAN frame
        payload = self._pack_data(data)
        
        frame = CANFrame(
            can_id=self.base_can_id,
            dlc=len(payload),
            flags=0,
            data=payload,
            timestamp=time.time()
        )
        
        self.can_hal.virtual_bus.transmit(frame)
    
    def _pack_data(self, data: dict) -> bytes:
        """Pack sensor data into bytes (override in subclass)"""
        raise NotImplementedError

class IMU_CANNode(CANSensor):
    """IMU that communicates over CAN"""
    def __init__(self, node_id: int, can_hal, imu_device):
        super().__init__(node_id, can_hal)
        self.imu = imu_device
    
    def publish_imu_data(self):
        """Read IMU and publish via CAN"""
        # Read accelerometer
        accel_data = self.imu.read_bytes(MPU6050.ACCEL_XOUT_H, 6)
        
        # Send via CAN (accelerometer)
        self.send_sensor_data({
            'type': 'accel',
            'data': accel_data
        })
        
        # Read gyroscope
        gyro_data = self.imu.read_bytes(MPU6050.GYRO_XOUT_H, 6)
        
        # Send via CAN (gyroscope)
        self.send_sensor_data({
            'type': 'gyro',
            'data': gyro_data
        })
    
    def _pack_data(self, data: dict) -> bytes:
        """Pack IMU data into CAN frame"""
        if data['type'] == 'accel':
            # Accel data: 6 bytes (X, Y, Z as 16-bit signed)
            return data['data']
        elif data['type'] == 'gyro':
            # Gyro data: 6 bytes
            return data['data']
        return b''
```

## Architecture Recommendations for CAN Nodes

### Problem Statement
You have:
- Multiple CAN nodes with IMUs (I2C/SPI connected)
- Central processing node that aggregates sensor data
- Display node with 7-segment display
- Want same HSX code to run on all nodes

### Recommended Architecture

```text
┌─────────────────────────────────────────────────────────┐
│  HSX Application (runs on all nodes)                    │
│  - Same binary on all nodes                             │
│  - Uses high-level sensor API                           │
│  - Publishes data via CAN                               │
└──────────────┬──────────────────────────────────────────┘
               │
        ┌──────┴──────────────┐
        │                     │
┌───────▼────────┐    ┌──────▼──────────┐
│ Local Sensors  │    │ Remote Sensors  │
│ (I2C/SPI HAL)  │    │ (CAN messages)  │
└───────┬────────┘    └──────┬──────────┘
        │                     │
┌───────▼────────────────────▼──────────┐
│  Device Abstraction Layer (in HAL)    │
│  - Unified sensor interface           │
│  - Hides I2C/SPI/CAN details          │
└───────────────────────────────────────┘
```

**Key Insight:** Create a **Device Abstraction Layer** that provides unified sensor access regardless of connection type.

### Example: Sensor HAL API

```c
// HSX app code - same on all nodes!
#include <hsx_sensor.h>

int main(void) {
    hsx_sensor_t imu;
    
    // Open IMU - HAL decides if it's local I2C or remote CAN
    hsx_sensor_open("imu0", HSX_SENSOR_TYPE_IMU, &imu);
    
    while (1) {
        // Read sensor data - works same for local or remote
        hsx_sensor_data_t data;
        hsx_sensor_read(imu, &data);
        
        // Process data
        process_imu_data(&data);
        
        // Publish results (if this is aggregator node)
        if (is_aggregator_node()) {
            hsx_can_publish_results(&data);
        }
        
        hsx_timer_sleep_ms(10);
    }
}
```

**HAL decides implementation:**
- **Sensor node:** I2C/SPI to local IMU
- **Aggregator node:** CAN messages from sensor nodes
- **Same HSX app binary!**

### Implementation Split

**In Executive (host code):**
- CAN driver (complex, hardware-specific)
- I2C/SPI drivers (hardware-specific)
- Device driver for IMU (talks to I2C/SPI)
- Device abstraction layer (maps sensor ID to driver)

**In HSX App (VM code):**
- Application logic only
- High-level sensor API calls
- Data processing algorithms
- Decision making

**Why:** Keep hardware complexity in executive where it's fast (C/C++). Keep application logic in HSX where it's portable.

## Integration Example

```python
"""
Complete HAL initialization example
"""
from platforms.python.hal import (
    UART_HAL, GPIO_HAL, CAN_HAL, FS_HAL,
    I2C_HAL, SPI_HAL
)
from platforms.python.hal.devices import MPU6050, IMU_CANNode

def initialize_python_hal(executive):
    """Initialize all Python HAL modules"""
    
    # Create HAL modules
    uart_hal = UART_HAL()
    gpio_hal = GPIO_HAL(num_pins=16)
    can_hal = CAN_HAL()
    fs_hal = FS_HAL(base_dir="hal_drive")
    i2c_hal = I2C_HAL()
    spi_hal = SPI_HAL()
    
    # Link to mailbox manager
    uart_hal.set_mailbox_manager(executive.mailbox_mgr)
    gpio_hal.set_mailbox_manager(executive.mailbox_mgr)
    can_hal.set_mailbox_manager(executive.mailbox_mgr)
    
    # Start GPIO GUI
    gpio_hal.start_gui()
    
    # Register I2C devices
    imu = MPU6050(address=0x68)
    i2c_hal.register_device(0x68, imu)
    
    # Create CAN sensor node
    imu_can_node = IMU_CANNode(node_id=1, can_hal=can_hal, imu_device=imu)
    
    # Register HAL modules with executive
    executive.register_hal(0x10, uart_hal)
    executive.register_hal(0x11, can_hal)
    executive.register_hal(0x14, fs_hal)
    executive.register_hal(0x15, gpio_hal)
    executive.register_hal(0x17, i2c_hal)  # If I2C module added
    executive.register_hal(0x18, spi_hal)  # If SPI module added
    
    return {
        'uart': uart_hal,
        'gpio': gpio_hal,
        'can': can_hal,
        'fs': fs_hal,
        'i2c': i2c_hal,
        'spi': spi_hal,
        'devices': {
            'imu': imu,
            'imu_can_node': imu_can_node
        }
    }
```

## Summary

**Python HAL provides:**
1. ✅ Development platform without hardware
2. ✅ GUI for GPIO (checkboxes for inputs, LEDs for outputs)
3. ✅ Filesystem access via `hal_drive/` folder
4. ✅ Virtual CAN bus for multi-node simulation
5. ✅ I2C/SPI bus emulation for device drivers
6. ✅ IMU and sensor emulators
7. ✅ Device abstraction for portable HSX apps

**For CAN nodes:**
- Keep hardware drivers (CAN, I2C, SPI, device drivers) in **executive** (fast C/C++)
- Keep application logic in **HSX** (portable bytecode)
- Use device abstraction layer to hide local vs. remote sensors
- Same HSX binary runs on all nodes!

**Next steps:**
1. Implement Python HAL modules
2. Create GPIO GUI with tkinter
3. Add I2C/SPI syscall modules (0x17, 0x18)
4. Define device abstraction API
5. Create example CAN node applications
