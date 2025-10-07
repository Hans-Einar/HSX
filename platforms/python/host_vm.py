#!/usr/bin/env python3
import argparse
import json
import socketserver
import time
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
import struct
import sys
import zlib
from typing import Any, Dict, Optional, List

HSX_MAGIC = 0x48535845  # 'HSXE'
HEADER = struct.Struct(">IHHIIIIII")
HEADER_FIELDS = (
    "magic",
    "version",
    "flags",
    "entry",
    "code_len",
    "ro_len",
    "bss_size",
    "req_caps",
    "crc32",
)


@dataclass
class TaskContext:
    """Represents the architectural state for a single HSX task."""

    regs: List[int] = field(default_factory=lambda: [0] * 16)
    pc: int = 0
    sp: int = 0x8000
    psw: int = 0
    reg_base: int = 0
    stack_base: int = 0
    stack_limit: int = 0
    time_slice_cycles: int = 1000
    accounted_cycles: int = 0
    state: str = "ready"
    priority: int = 10
    pid: Optional[int] = None


def clone_context(ctx: TaskContext) -> TaskContext:
    return TaskContext(
        regs=list(ctx.regs),
        pc=ctx.pc,
        sp=ctx.sp,
        psw=ctx.psw,
        reg_base=ctx.reg_base,
        stack_base=ctx.stack_base,
        stack_limit=ctx.stack_limit,
        time_slice_cycles=ctx.time_slice_cycles,
        accounted_cycles=ctx.accounted_cycles,
        state=ctx.state,
        priority=ctx.priority,
        pid=ctx.pid,
    )


def context_to_dict(ctx: TaskContext) -> Dict[str, Any]:
    return {
        "regs": list(ctx.regs),
        "pc": ctx.pc,
        "sp": ctx.sp,
        "psw": ctx.psw,
        "reg_base": ctx.reg_base,
        "stack_base": ctx.stack_base,
        "stack_limit": ctx.stack_limit,
        "time_slice_cycles": ctx.time_slice_cycles,
        "accounted_cycles": ctx.accounted_cycles,
        "state": ctx.state,
        "priority": ctx.priority,
        "pid": ctx.pid,
    }


def dict_to_context(data: Dict[str, Any]) -> TaskContext:
    return TaskContext(
        regs=list(data.get("regs", [0] * 16)),
        pc=int(data.get("pc", 0)) & 0xFFFFFFFF,
        sp=int(data.get("sp", 0)) & 0xFFFFFFFF,
        psw=int(data.get("psw", 0)) & 0xFF,
        reg_base=int(data.get("reg_base", 0)) & 0xFFFFFFFF,
        stack_base=int(data.get("stack_base", 0)) & 0xFFFFFFFF,
        stack_limit=int(data.get("stack_limit", 0)) & 0xFFFFFFFF,
        time_slice_cycles=int(data.get("time_slice_cycles", 1000)),
        accounted_cycles=int(data.get("accounted_cycles", 0)),
        state=str(data.get("state", "ready")),
        priority=int(data.get("priority", 10)) & 0xFF,
        pid=data.get("pid"),
    )

def f16_to_f32(h):
    h &= 0xFFFF
    s = (h >> 15) & 0x1
    e = (h >> 10) & 0x1F
    f = h & 0x3FF
    if e == 0:
        if f == 0:
            return -0.0 if s else 0.0
        # subnormal
        return ((-1.0 if s else 1.0) * (f / (1<<10)) * (2 ** (1 - 15)))
    if e == 0x1F:
        if f == 0:
            return float('-inf') if s else float('inf')
        return float('nan')
    # normal
    return (-1.0 if s else 1.0) * (1.0 + f / (1<<10)) * (2 ** (e - 15))

def f32_to_f16(val):
    # Handle special cases
    if val != val:
        return 0x7E00  # NaN
    if val == float('inf'):
        return 0x7C00
    if val == float('-inf'):
        return 0xFC00
    s = 0
    if val < 0 or (val == 0.0 and str(val).startswith('-')):
        s = 1
    a = abs(val)
    if a == 0.0:
        return s << 15
    import math
    e = int(math.floor(math.log(a, 2)))
    # half exponent range -14 .. +15
    if e > 15:
        return (s<<15) | 0x7C00  # overflow to inf
    if e < -14:
        # subnormal
        frac = a / (2 ** (-14))
        f = int(round(frac * (1<<10))) - (1<<10)
        if f < 0: f = 0
        return (s<<15) | (f & 0x3FF)
    # normal
    bias_e = e + 15
    mant = a / (2 ** e) - 1.0
    f = int(round(mant * (1<<10)))
    if f == (1<<10):  # rounding overflow to next exponent
        f = 0
        bias_e += 1
        if bias_e >= 0x1F:
            return (s<<15) | 0x7C00
    return (s<<15) | ((bias_e & 0x1F)<<10) | (f & 0x3FF)


def be32(b, off):
    return (b[off]<<24)|(b[off+1]<<16)|(b[off+2]<<8)|b[off+3]


class FSStub:
    def __init__(self):
        self.files = {"/hello.txt": bytearray(b"Hi from FS!\n")}
        self.fds = {}
        self.next_fd = 3
    def open(self, path, flags=0):
        if path not in self.files:
            self.files[path] = bytearray()
        fd = self.next_fd; self.next_fd += 1
        self.fds[fd] = {"path": path, "pos": 0}
        return fd
    def read(self, fd, n):
        if fd not in self.fds: return b""
        ent = self.fds[fd]; data = self.files[ent["path"]]
        start = ent["pos"]; end = min(start+n, len(data))
        ent["pos"] = end
        return bytes(data[start:end])
    def write(self, fd, buf):
        if fd not in self.fds: return 0
        ent = self.fds[fd]; data = self.files[ent["path"]]
        start = ent["pos"]
        # extend file if needed
        end = start + len(buf)
        if end > len(data): data.extend(b"\x00"*(end-len(data)))
        data[start:end] = buf
        ent["pos"] = end
        return len(buf)
    def close(self, fd):
        if fd in self.fds: del self.fds[fd]; return 0
        return -1
    def listdir(self, path):
        # very naive: list keys with that prefix
        return "\n".join(sorted(self.files.keys())).encode("utf-8")
    def delete(self, path):
        if path in self.files: del self.files[path]; return 0
        return -1
    def rename(self, old, new):
        if old in self.files and new not in self.files:
            self.files[new] = self.files.pop(old); return 0
        return -1
    def mkdir(self, path): return 0

class MiniVM:
    def __init__(self, code: bytes, *, entry: int = 0, rodata: bytes = b"", trace: bool = False, svc_trace: bool = False, dev_libm: bool = False, trace_file=None, exec_root=None):
        self.code = bytearray(code)
        self.entry = entry
        self.context: TaskContext = TaskContext(pc=entry)
        self.running = True
        self.cycles = 0
        self.set_context(self.context)
        self.mem = bytearray(64 * 1024)
        self.fs = FSStub()
        self.trace = trace
        self.svc_trace = svc_trace
        self.dev_libm = dev_libm
        self.sleep_until: Optional[float] = None
        self.sleep_pending_ms: Optional[int] = None
        self.pending_events: List[Dict[str, Any]] = []
        self.attached = False
        self.trace_out = trace_file
        self.exec_root = Path(exec_root).resolve() if exec_root else None
        if rodata:
            self._load_rodata(rodata)

    def _log(self, msg):
        if self.trace_out:
            self.trace_out.write(msg + "\n")
            self.trace_out.flush()
        print(msg)

    def _load_rodata(self, rodata: bytes, base: int = 0x4000):
        end = min(base + len(rodata), len(self.mem))
        self.mem[base:end] = rodata[: end - base]

    def set_entry(self, entry):
        self.pc = entry
        self.context.pc = entry

    # ------------------------------------------------------------------
    # Context handling helpers

    def current_context(self) -> TaskContext:
        return self.context

    def create_context(self, *, entry: Optional[int] = None, stack_base: int = 0, stack_limit: int = 0, priority: int = 10, quantum: int = 1000, pid: Optional[int] = None) -> TaskContext:
        ctx = TaskContext(
            pc=entry if entry is not None else self.entry,
            sp=0x8000,
            psw=0,
            reg_base=0,
            stack_base=stack_base,
            stack_limit=stack_limit,
            time_slice_cycles=max(1, int(quantum)),
            accounted_cycles=0,
            state="ready",
            priority=priority,
            pid=pid,
        )
        return ctx

    def set_context(self, ctx: TaskContext) -> None:
        self.context = ctx
        self.regs = ctx.regs
        self.pc = ctx.pc
        self.sp = ctx.sp
        self.flags = ctx.psw
        ctx.state = "running" if self.running else ctx.state

    def save_context(self) -> None:
        ctx = self.context
        if ctx is None:
            return
        ctx.pc = self.pc
        ctx.sp = self.sp
        ctx.psw = self.flags
    def snapshot_registers(self):
        ctx = self.context
        context_meta = None
        if ctx is not None:
            context_meta = {
                "pid": ctx.pid,
                "state": ctx.state,
                "priority": ctx.priority,
                "time_slice_cycles": ctx.time_slice_cycles,
                "accounted_cycles": ctx.accounted_cycles,
                "reg_base": ctx.reg_base,
                "stack_base": ctx.stack_base,
                "stack_limit": ctx.stack_limit,
            }
        return {
            "pc": self.pc,
            "regs": list(self.regs),
            "sp": self.sp,
            "flags": self.flags,
            "running": self.running,
            "cycles": self.cycles,
            "context": context_meta,
        }

    def restore_registers(self, snapshot):
        self.pc = snapshot.get("pc", self.pc) & 0xFFFFFFFF
        regs = snapshot.get("regs")
        if regs is not None:
            if len(regs) != len(self.regs):
                raise ValueError("regs length mismatch")
            self.regs = [int(x) & 0xFFFFFFFF for x in regs]
            self.context.regs = self.regs
        self.sp = snapshot.get("sp", self.sp) & 0xFFFFFFFF
        self.flags = snapshot.get("flags", self.flags) & 0xFF
        self.running = bool(snapshot.get("running", self.running))
        self.context.pc = self.pc
        self.context.sp = self.sp
        self.context.psw = self.flags
        self.context.state = "running" if self.running else "stopped"
        ctx_snapshot = snapshot.get("context")
        if ctx_snapshot:
            new_ctx = dict_to_context(ctx_snapshot)
            new_ctx.regs = self.regs
            self.context = new_ctx
        return self.snapshot_registers()

    def snapshot_state(self) -> Dict[str, Any]:
        self.save_context()
        ctx = clone_context(self.context)
        return {
            "context": context_to_dict(ctx),
            "code": bytearray(self.code),
            "mem": bytearray(self.mem),
            "running": self.running,
            "sleep_until": self.sleep_until,
            "sleep_pending_ms": self.sleep_pending_ms,
            "cycles": self.cycles,
            "pending_events": list(self.pending_events),
        }

    def restore_state(self, state: Dict[str, Any]) -> None:
        self.code = bytearray(state.get("code", self.code))
        mem_state = state.get("mem")
        if mem_state is not None:
            self.mem = bytearray(mem_state)
        self.cycles = int(state.get("cycles", self.cycles))
        self.sleep_until = state.get("sleep_until")
        self.sleep_pending_ms = state.get("sleep_pending_ms")
        self.pending_events = list(state.get("pending_events", []))
        ctx_dict = state.get("context")
        if ctx_dict:
            ctx = dict_to_context(ctx_dict)
            self.set_context(ctx)
        self.running = bool(state.get("running", True))

    def emit_event(self, event: Dict[str, Any]) -> None:
        self.pending_events.append(event)

    def consume_events(self) -> List[Dict[str, Any]]:
        events = self.pending_events
        self.pending_events = []
        return events

    def request_sleep(self, ms: int) -> None:
        ms = max(int(ms), 0)
        if ms <= 0:
            self.sleep_pending_ms = None
            return
        self.sleep_pending_ms = ms
        self.emit_event({"type": "sleep_request", "ms": ms})
        if self.attached:
            return
        self.sleep_until = time.monotonic() + (ms / 1000.0)

    def read_mem(self, addr: int, length: int) -> bytes:
        if length <= 0:
            return b""
        a = addr & 0xFFFF
        end = min(a + length, len(self.mem))
        return bytes(self.mem[a:end])

    def write_mem(self, addr: int, data: bytes) -> None:
        if not data:
            return
        a = addr & 0xFFFF
        end = min(a + len(data), len(self.mem))
        self.mem[a:end] = data[: end - a]

    def step(self):
        if self.sleep_until is not None:
            remaining = self.sleep_until - time.monotonic()
            if remaining > 0:
                time.sleep(min(remaining, 0.005))
                self.save_context()
                return
            self.sleep_until = None
            self.sleep_pending_ms = None
            self.emit_event({"type": "sleep_complete"})

        if self.pc + 4 > len(self.code):
            print(f"[VM] PC 0x{self.pc:04X} is outside code length {len(self.code)}")
            self.running = False
            self.save_context()
            return

        ins = be32(self.code, self.pc)
        op = (ins >> 24) & 0xFF
        rd = (ins >> 20) & 0x0F
        rs1 = (ins >> 16) & 0x0F
        rs2 = (ins >> 12) & 0x0F
        imm = ins & 0x0FFF
        if imm & 0x800:
            imm -= 0x1000

        def set_flags(v):
            self.flags = 0
            if v == 0:
                self.flags |= 1  # Z flag

        def ld32(addr):
            a = addr & 0xFFFF
            return (self.mem[a] << 24) | (self.mem[(a + 1) & 0xFFFF] << 16) | (self.mem[(a + 2) & 0xFFFF] << 8) | self.mem[(a + 3) & 0xFFFF]

        def st32(addr, val):
            a = addr & 0xFFFF
            self.mem[a] = (val >> 24) & 0xFF
            self.mem[(a + 1) & 0xFFFF] = (val >> 16) & 0xFF
            self.mem[(a + 2) & 0xFFFF] = (val >> 8) & 0xFF
            self.mem[(a + 3) & 0xFFFF] = val & 0xFF

        def ld8(addr):
            return self.mem[addr & 0xFFFF]

        def st8(addr, v):
            self.mem[addr & 0xFFFF] = v & 0xFF

        def ld16(addr):
            a = addr & 0xFFFF
            return (self.mem[a] << 8) | self.mem[(a + 1) & 0xFFFF]

        def st16(addr, v):
            a = addr & 0xFFFF
            self.mem[a] = (v >> 8) & 0xFF
            self.mem[(a + 1) & 0xFFFF] = v & 0xFF

        if self.trace or self.trace_out:
            self._log(f"[TRACE] pc=0x{self.pc:04X} op=0x{op:02X} rd=R{rd} rs1=R{rs1} rs2=R{rs2} imm={imm}")

        adv = 4
        if op == 0x01:  # LDI
            self.regs[rd] = imm & 0xFFFFFFFF
        elif op == 0x02:  # LD
            self.regs[rd] = ld32((self.regs[rs1] + imm) & 0xFFFFFFFF)
        elif op == 0x03:  # ST
            st32((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
        elif op == 0x04:  # MOV
            self.regs[rd] = self.regs[rs1]
        elif op == 0x06:  # LDB
            self.regs[rd] = ld8((self.regs[rs1] + imm) & 0xFFFFFFFF)
        elif op == 0x07:  # LDH
            self.regs[rd] = ld16((self.regs[rs1] + imm) & 0xFFFFFFFF)
        elif op == 0x08:  # STB
            st8((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
        elif op == 0x09:  # STH
            st16((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
        elif op == 0x10:  # ADD
            v = (self.regs[rs1] + self.regs[rs2]) & 0xFFFFFFFF
            self.regs[rd] = v
            set_flags(v)
        elif op == 0x11:  # SUB
            v = (self.regs[rs1] - self.regs[rs2]) & 0xFFFFFFFF
            self.regs[rd] = v
            set_flags(v)
        elif op == 0x12:  # MUL
            v = (self.regs[rs1] * self.regs[rs2]) & 0xFFFFFFFF
            self.regs[rd] = v
            set_flags(v)
        elif op == 0x14:  # AND
            v = self.regs[rs1] & self.regs[rs2]
            self.regs[rd] = v & 0xFFFFFFFF
            set_flags(v)
        elif op == 0x15:  # OR
            v = self.regs[rs1] | self.regs[rs2]
            self.regs[rd] = v & 0xFFFFFFFF
            set_flags(v)
        elif op == 0x16:  # XOR
            v = self.regs[rs1] ^ self.regs[rs2]
            self.regs[rd] = v & 0xFFFFFFFF
            set_flags(v)
        elif op == 0x17:  # NOT
            v = (~self.regs[rs1]) & 0xFFFFFFFF
            self.regs[rd] = v
            set_flags(v)
        elif op == 0x20:  # CMP
            v = (self.regs[rs1] - self.regs[rs2]) & 0xFFFFFFFF
            set_flags(v)
        elif op == 0x21:  # JMP
            self.pc = imm & 0xFFFFFFFF
            adv = 0
        elif op == 0x22:  # JZ
            if self.flags & 0x1:
                self.pc = imm & 0xFFFFFFFF
                adv = 0
        elif op == 0x23:  # JNZ
            if not (self.flags & 0x1):
                self.pc = imm & 0xFFFFFFFF
                adv = 0
        elif op == 0x24:  # CALL (no stack yet)
            self.pc = imm & 0xFFFFFFFF
            adv = 0
        elif op == 0x25:  # RET (placeholder: stop VM)
            self.running = False
        elif op == 0x30:  # SVC
            mod = (imm >> 8) & 0x0F
            fn = imm & 0xFF
            if self.svc_trace:
                self._log(f"[SVC] mod=0x{mod:X} fn=0x{fn:X} R0..R3={self.regs[:4]}")
            self.handle_svc(mod, fn)
        elif op == 0x50:  # FADD
            a = f16_to_f32(self.regs[rs1] & 0xFFFF)
            b = f16_to_f32(self.regs[rs2] & 0xFFFF)
            self.regs[rd] = (self.regs[rd] & 0xFFFF0000) | (f32_to_f16(a + b) & 0xFFFF)
        elif op == 0x51:  # FSUB
            a = f16_to_f32(self.regs[rs1] & 0xFFFF)
            b = f16_to_f32(self.regs[rs2] & 0xFFFF)
            self.regs[rd] = (self.regs[rd] & 0xFFFF0000) | (f32_to_f16(a - b) & 0xFFFF)
        elif op == 0x52:  # FMUL
            a = f16_to_f32(self.regs[rs1] & 0xFFFF)
            b = f16_to_f32(self.regs[rs2] & 0xFFFF)
            self.regs[rd] = (self.regs[rd] & 0xFFFF0000) | (f32_to_f16(a * b) & 0xFFFF)
        elif op == 0x53:  # FDIV
            a = f16_to_f32(self.regs[rs1] & 0xFFFF)
            b = f16_to_f32(self.regs[rs2] & 0xFFFF)
            if b == 0.0:
                b = float("inf")
            self.regs[rd] = (self.regs[rd] & 0xFFFF0000) | (f32_to_f16(a / b) & 0xFFFF)
        elif op == 0x54:  # I2F
            val = self.regs[rs1]
            if val & 0x80000000:
                val = val - 0x100000000
            f = float(val)
            self.regs[rd] = (self.regs[rd] & 0xFFFF0000) | f32_to_f16(f)
        elif op == 0x55:  # F2I
            h = self.regs[rs1] & 0xFFFF
            f = f16_to_f32(h)
            self.regs[rd] = int(f) & 0xFFFFFFFF
        elif op == 0x60:  # LDI32 (two-word immediate)
            if self.pc + 8 > len(self.code):
                print(f"[VM] LDI32 at 0x{self.pc:04X} overruns code")
                self.running = False
                self.save_context()
                return
            full = be32(self.code, self.pc + 4)
            self.regs[rd] = full & 0xFFFFFFFF
            adv = 8
        else:
            print(f"[VM] Illegal opcode 0x{op:02X} at PC=0x{self.pc:04X}")
            self.running = False

        self.pc = (self.pc + adv) & 0xFFFFFFFF
        self.cycles += 1
        ctx = self.context
        if ctx is not None:
            ctx.accounted_cycles += 1
            ctx.pc = self.pc
            ctx.sp = self.sp
            ctx.psw = self.flags
            if not self.running:
                ctx.state = "stopped"

    def handle_svc(self, mod, fn):
        if mod == 0x0 and fn == 0:
            self.regs[0] = self.cycles
        elif mod == 0x1 and fn == 0:
            exit_code = self.regs[0] & 0xFFFFFFFF
            self._log(f"[EXIT {exit_code}]")
            self.running = False
        elif mod == 0x1 and fn == 1:
            ptr = self.regs[1] & 0xFFFF
            ln = self.regs[2] & 0xFFFF
            data = bytes(self.mem[ptr : ptr + ln])
            text = data.decode("utf-8", errors="ignore")
            self._log(f"[UART.tx] {text}")
            self.regs[0] = ln
        elif mod == 0x2 and fn == 0:
            can_id = self.regs[1] & 0x7FF
            ptr = self.regs[2] & 0xFFFF
            ln = self.regs[3] & 0xFF
            data = bytes(self.mem[ptr : ptr + ln])
            self._log(f"[CAN.tx] id=0x{can_id:03X} data={data.hex()}")
            self.regs[0] = 0
        elif self.dev_libm and mod == 0xE:
            import math
            funcs = {0: math.sin, 1: math.cos, 2: math.exp}
            if fn in funcs:
                arg = f16_to_f32(self.regs[1] & 0xFFFF)
                res = funcs[fn](arg)
                self.regs[0] = (self.regs[0] & 0xFFFF0000) | (f32_to_f16(res) & 0xFFFF)
            else:
                self._log(f"[SVC] dev-libm fn={fn} unsupported")
                self.regs[0] = 0
        elif mod == 0x7:
            self._svc_exec(fn)
        elif mod == 0x3:
            self._svc_shell(fn)
        elif mod == 0x4:
            self._svc_fs(fn)
        else:
            self._log(f"[SVC] mod=0x{mod:X} fn=0x{fn:X} (stub)")
            self.regs[0] = 0

    def _read_c_string(self, addr):
        out = bytearray()
        a = addr & 0xFFFF
        while a < len(self.mem) and self.mem[a] != 0:
            out.append(self.mem[a])
            a += 1
        return out.decode("utf-8", errors="ignore")

    def _svc_exec(self, fn):
        if fn == 0:  # yield
            self.emit_event({"type": "yield"})
            self.regs[0] = 0
        elif fn == 1:  # sleep_ms
            ms = self.regs[0] & 0xFFFFFFFF
            self.request_sleep(ms)
            self.regs[0] = 0
        else:
            self._log(f"[EXEC] fn={fn} not implemented")
            self.regs[0] = 0


    def _svc_fs(self, fn):
        if fn == 0:  # open(path, flags)
            path = self._read_c_string(self.regs[1]) or "/unnamed"
            flags = self.regs[2] & 0xFFFF
            self.regs[0] = self.fs.open(path, flags)
        elif fn == 1:  # read(fd, ptr, len)
            fd = self.regs[1] & 0xFFFF
            ptr = self.regs[2] & 0xFFFF
            ln = self.regs[3] & 0xFFFF
            data = self.fs.read(fd, ln)
            self.mem[ptr : ptr + len(data)] = data
            self.regs[0] = len(data)
        elif fn == 2:  # write(fd, ptr, len)
            fd = self.regs[1] & 0xFFFF
            ptr = self.regs[2] & 0xFFFF
            ln = self.regs[3] & 0xFFFF
            buf = bytes(self.mem[ptr : ptr + ln])
            self.regs[0] = self.fs.write(fd, buf)
        elif fn == 3:  # close(fd)
            fd = self.regs[1] & 0xFFFF
            self.regs[0] = self.fs.close(fd)
        elif fn == 10:  # listdir(path, out, max)
            path = self._read_c_string(self.regs[1]) or "/"
            out_ptr = self.regs[2] & 0xFFFF
            mx = self.regs[3] & 0xFFFF
            data = self.fs.listdir(path)[:mx]
            self.mem[out_ptr : out_ptr + len(data)] = data
            self.regs[0] = len(data)
        elif fn == 11:  # delete(path)
            path = self._read_c_string(self.regs[1])
            self.regs[0] = self.fs.delete(path)
        elif fn == 12:  # rename(old,new)
            old = self._read_c_string(self.regs[1])
            new = self._read_c_string(self.regs[2])
            self.regs[0] = self.fs.rename(old, new)
        elif fn == 13:  # mkdir(path)
            path = self._read_c_string(self.regs[1])
            self.regs[0] = self.fs.mkdir(path)
        else:
            print(f"[FS] fn={fn} not implemented")
            self.regs[0] = -1


    def _svc_shell(self, fn):
        if self.exec_root is None:
            self.regs[0] = 0
            return
        root = self.exec_root
        if fn == 1:
            out_ptr = self.regs[1] & 0xFFFF
            max_len = self.regs[2] & 0xFFFF
            if max_len <= 0 or out_ptr >= len(self.mem):
                self.regs[0] = 0
                return
            names = []
            for p in root.rglob("*.hxe"):
                try:
                    rel = p.relative_to(root)
                except ValueError:
                    rel = p
                names.append(rel.as_posix())
            names.sort()
            if names:
                payload = ("\n".join(names) + "\n").encode("utf-8")
            else:
                payload = b"(none)\n"
            limit = min(max_len, len(self.mem) - out_ptr)
            self.mem[out_ptr:out_ptr + limit] = b"\x00" * limit
            chunk = payload[:limit]
            self.mem[out_ptr:out_ptr + len(chunk)] = chunk
            self.regs[0] = len(chunk)
            return
        if fn == 0:
            name = self._read_c_string(self.regs[1])
            if not name:
                self.regs[0] = 0
                return
            target = root / name
            if target.is_dir():
                target = target / "main.hxe"
            if target.suffix.lower() != ".hxe":
                target = target.with_suffix(".hxe")
            if not target.exists():
                self._log(f"[exec] missing payload {target}")
                self.regs[0] = 0
                return
            try:
                header, code, rodata = load_hxe(target)
            except Exception as exc:
                self._log(f"[exec] failed to load {target}: {exc}")
                self.regs[0] = 0
                return
            child = MiniVM(
                code,
                entry=header["entry"],
                rodata=rodata,
                trace=self.trace,
                svc_trace=self.svc_trace,
                dev_libm=self.dev_libm,
                trace_file=self.trace_out,
                exec_root=self.exec_root,
            )
            steps = 0
            max_steps = 20000
            while child.running and steps < max_steps:
                child.step()
                steps += 1
            if child.running:
                self._log(f"[exec] max steps reached for {target.name}")
                child.running = False
            self.regs[0] = child.regs[0] & 0xFFFFFFFF
            return
        self.regs[0] = 0


class VMController:
    def __init__(self, *, trace: bool = False, svc_trace: bool = False, dev_libm: bool = False):
        self.trace = trace
        self.svc_trace = svc_trace
        self.dev_libm = dev_libm
        self.vm: Optional[MiniVM] = None
        self.header: Optional[Dict[str, Any]] = None
        self.program_path: Optional[str] = None
        self.attached = False
        self.paused = False
        self.tasks: Dict[int, Dict[str, Any]] = {}
        self.task_states: Dict[int, Dict[str, Any]] = {}
        self.current_pid: Optional[int] = None
        self.next_pid = 1
        self.restart_requested: bool = False
        self.restart_targets: Optional[List[str]] = None
        self.server: Optional["VMServer"] = None

    def reset(self) -> Dict[str, Any]:
        self.vm = None
        self.header = None
        self.program_path = None
        self.attached = False
        self.paused = False
        self.tasks.clear()
        self.task_states.clear()
        self.current_pid = None
        self.next_pid = 1
        return {"status": "ok"}

    def info(self, pid: Optional[int] = None) -> Dict[str, Any]:
        vm = self.vm
        active_ctx = None
        if self.current_pid is not None:
            state = self.task_states.get(self.current_pid)
            if state:
                active_ctx = state.get("context")
        summary = self.task_list()
        info = {
            "loaded": bool(self.tasks),
            "program": self.program_path,
            "running": bool(vm.running) if vm else False,
            "pc": vm.pc if vm else None,
            "attached": self.attached,
            "paused": self.paused,
            "sleep_pending": bool((vm.sleep_until is not None) or (vm and getattr(vm, "sleep_pending_ms", None) is not None)) if vm else False,
            "current_pid": summary.get("current_pid"),
            "active_context": active_ctx,
            "tasks": summary.get("tasks", []),
        }
        if pid is not None:
            try:
                info["selected_pid"] = pid
                info["selected_registers"] = self.read_regs(pid)
            except ValueError as exc:
                info["selected_error"] = str(exc)
        return info

    def schedule_restart(self, targets: Optional[List[str]] = None) -> None:
        self.restart_requested = True
        self.restart_targets = list(targets or ["vm"])
        try:
            self.stop_auto()
        except Exception:
            pass
        if self.server is not None:
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def load_from_path(self, path: str, *, verbose: bool = False) -> Dict[str, Any]:
        self._store_active_state()
        header, code, rodata = load_hxe(path, verbose=verbose)
        temp_vm = MiniVM(code, entry=header["entry"], rodata=rodata, trace=self.trace, svc_trace=self.svc_trace, dev_libm=self.dev_libm)
        state = temp_vm.snapshot_state()
        pid = self.next_pid
        self.next_pid += 1
        ctx = state["context"]
        ctx["pid"] = pid
        state["context"] = ctx
        self.tasks[pid] = {
            "pid": pid,
            "program": str(Path(path).resolve()),
            "state": "running",
            "priority": ctx.get("priority", 10),
            "quantum": ctx.get("time_slice_cycles", 1000),
            "pc": ctx.get("pc", header["entry"]),
            "stdout": "uart0",
            "sleep_pending": False,
            "vm_state": state,
        }
        self.task_states[pid] = state
        self.program_path = self.tasks[pid]["program"]
        self._activate_task(pid, state_override=state)
        return {
            "entry": header["entry"],
            "code_len": header["code_len"],
            "ro_len": header["ro_len"],
            "bss": header["bss_size"],
        }

    # ------------------------------------------------------------------
    # Task/context helpers

    def _get_task(self, pid: int) -> Dict[str, Any]:
        task = self.tasks.get(pid)
        if task is None:
            raise ValueError(f"unknown pid {pid}")
        return task

    def _store_active_state(self) -> None:
        if self.current_pid is None or self.vm is None:
            return
        state = self.vm.snapshot_state()
        ctx = state["context"]
        ctx["pid"] = self.current_pid
        ctx["state"] = "paused" if self.paused else ("running" if self.vm.running else "stopped")
        state["context"] = ctx
        state["running"] = self.vm.running
        state["cycles"] = self.vm.cycles
        self.task_states[self.current_pid] = state
        task = self.tasks.get(self.current_pid)
        if task:
            task["vm_state"] = state
            task["pc"] = ctx.get("pc", task.get("pc"))
            task["sleep_pending"] = bool(self.vm.sleep_until or self.vm.sleep_pending_ms)
            if self.paused:
                task["state"] = "paused"
                ctx["state"] = "paused"
            elif self.vm.running:
                task["state"] = "ready"
                ctx["state"] = "ready"
            else:
                task["state"] = "stopped"
                ctx["state"] = "stopped"

    def _activate_task(self, pid: int, state_override: Optional[Dict[str, Any]] = None) -> None:
        task = self._get_task(pid)
        state = state_override or self.task_states.get(pid) or task.get("vm_state")
        if state is None:
            raise ValueError(f"no state for pid {pid}")
        if self.vm is None:
            initial_code = bytes(state.get("code", bytearray()))
            entry = state.get("context", {}).get("pc", task.get("pc", 0))
            self.vm = MiniVM(initial_code, entry=entry, trace=self.trace, svc_trace=self.svc_trace, dev_libm=self.dev_libm)
        self.vm.restore_state(state)
        self.vm.attached = self.attached
        self.current_pid = pid
        task["vm_state"] = state
        ctx = state.get("context", {})
        task["pc"] = ctx.get("pc", task.get("pc"))
        task["state"] = "running" if self.vm.running else ctx.get("state", task.get("state", "stopped"))
        self.task_states[pid] = state

    def _runnable_pids(self) -> List[int]:
        return [pid for pid, meta in self.tasks.items() if meta.get("state") in {"running", "ready"}]

    def _rotate_active(self) -> None:
        runnable = self._runnable_pids()
        if not runnable:
            return
        if self.current_pid not in runnable:
            self._activate_task(runnable[0])
            return
        if len(runnable) == 1:
            return
        idx = runnable.index(self.current_pid)
        next_pid = runnable[(idx + 1) % len(runnable)]
        if next_pid != self.current_pid:
            self._activate_task(next_pid)

    def _task_summary(self, pid: int) -> Dict[str, Any]:
        task = self._get_task(pid)
        state = self.task_states.get(pid, {})
        ctx = state.get("context", {})
        return {
            "pid": pid,
            "program": task.get("program"),
            "state": task.get("state"),
            "pc": ctx.get("pc", task.get("pc")),
            "priority": task.get("priority"),
            "quantum": task.get("quantum"),
            "accounted_cycles": ctx.get("accounted_cycles", 0),
            "sleep_pending": task.get("sleep_pending", False),
        }

    def step(self, cycles: int) -> Dict[str, Any]:
        if not self.tasks:
            return {
                "executed": 0,
                "running": False,
                "pc": None,
                "cycles": 0,
                "sleep_pending": False,
                "events": [],
                "paused": self.paused,
                "current_pid": self.current_pid,
            }
        if self.current_pid is None:
            first_pid = next(iter(self.tasks))
            self._activate_task(first_pid)
        vm = self._require_vm()
        if self.paused:
            snapshot = vm.snapshot_registers()
            events = vm.consume_events()
            self._store_active_state()
            return {
                "executed": 0,
                "running": vm.running,
                "pc": snapshot["pc"],
                "cycles": snapshot["cycles"],
                "sleep_pending": bool((vm.sleep_until is not None) or (vm.sleep_pending_ms is not None)),
                "events": events,
                "paused": True,
                "current_pid": self.current_pid,
            }
        budget = max(int(cycles), 0)
        executed = 0
        events: List[Dict[str, Any]] = []
        while executed < budget and vm.running:
            vm.step()
            executed += 1
            if not vm.running:
                break
        events.extend(vm.consume_events())
        snapshot = vm.snapshot_registers()
        self._store_active_state()
        self._rotate_active()
        return {
            "executed": executed,
            "running": snapshot["running"],
            "pc": snapshot["pc"],
            "cycles": snapshot["cycles"],
            "sleep_pending": bool((vm.sleep_until is not None) or (vm.sleep_pending_ms is not None)),
            "events": events,
            "paused": self.paused,
            "current_pid": self.current_pid,
        }

    def read_regs(self, pid: Optional[int] = None) -> Dict[str, Any]:
        pid = self.current_pid if pid is None else pid
        if pid is None:
            return {}
        if pid == self.current_pid and self.vm is not None:
            return self.vm.snapshot_registers()
        state = self.task_states.get(pid)
        if not state:
            raise ValueError(f"unknown pid {pid}")
        ctx = dict_to_context(state["context"])
        return {
            "pc": ctx.pc,
            "regs": list(ctx.regs),
            "sp": ctx.sp,
            "flags": ctx.psw,
            "running": state.get("running", ctx.state == "running"),
            "cycles": state.get("cycles", ctx.accounted_cycles),
            "context": state["context"],
        }

    def write_regs(self, payload: Dict[str, Any], pid: Optional[int] = None) -> Dict[str, Any]:
        pid = self.current_pid if pid is None else pid
        if pid is None:
            raise ValueError("no task selected")
        if pid != self.current_pid:
            self._activate_task(pid)
        vm = self._require_vm()
        resp = vm.restore_registers(payload or {})
        self._store_active_state()
        return resp

    def read_mem(self, addr: int, length: int) -> bytes:
        vm = self._require_vm()
        return vm.read_mem(addr, length)

    def write_mem(self, addr: int, data: bytes) -> None:
        vm = self._require_vm()
        vm.write_mem(addr, data)

    def task_list(self) -> Dict[str, Any]:
        tasks = [self._task_summary(pid) for pid in sorted(self.tasks)]
        return {"tasks": tasks, "current_pid": self.current_pid}

    def pause_task(self, pid: int) -> Dict[str, Any]:
        task = self._get_task(pid)
        if pid == self.current_pid and self.vm is not None:
            self._store_active_state()
            self.vm = None
            self.current_pid = None
        task["state"] = "paused"
        state = self.task_states.get(pid)
        if state:
            state["context"]["state"] = "paused"
        return self._task_summary(pid)

    def resume_task(self, pid: int) -> Dict[str, Any]:
        task = self._get_task(pid)
        task["state"] = "running"
        state = self.task_states.get(pid)
        if state:
            state["context"]["state"] = "running"
        self._activate_task(pid, state_override=state)
        return self._task_summary(pid)

    def kill_task(self, pid: int) -> Dict[str, Any]:
        task = self._get_task(pid)
        summary = self._task_summary(pid)
        if pid == self.current_pid:
            self._store_active_state()
            self.vm = None
            self.current_pid = None
        self.tasks.pop(pid, None)
        self.task_states.pop(pid, None)
        summary["state"] = "terminated"
        if self.tasks:
            remaining = sorted(self.tasks)
            self._activate_task(remaining[0])
        return summary

    def set_task_attrs(self, pid: int, *, priority: Optional[int] = None, quantum: Optional[int] = None) -> Dict[str, Any]:
        task = self._get_task(pid)
        state = self.task_states.get(pid)
        if priority is not None:
            pr = max(0, int(priority))
            task["priority"] = pr
            if state:
                state["context"]["priority"] = pr
            if pid == self.current_pid and self.vm is not None:
                self.vm.context.priority = pr
        if quantum is not None:
            q = max(1, int(quantum))
            task["quantum"] = q
            if state:
                state["context"]["time_slice_cycles"] = q
            if pid == self.current_pid and self.vm is not None:
                self.vm.context.time_slice_cycles = q
        return self._task_summary(pid)

    def request_dump_regs(self, pid: Optional[int]) -> Dict[str, Any]:
        return self.read_regs(pid)

    def request_peek(self, pid: int, addr: int, length: int) -> bytes:
        if pid == self.current_pid and self.vm is not None:
            return self.vm.read_mem(addr, length)
        state = self.task_states.get(pid)
        if not state:
            raise ValueError(f"unknown pid {pid}")
        mem = state.get("mem")
        if mem is None:
            return b""
        a = addr & 0xFFFF
        end = min(a + length, len(mem))
        return bytes(mem[a:end])

    def request_poke(self, pid: int, addr: int, data: bytes) -> None:
        if pid == self.current_pid and self.vm is not None:
            self.vm.write_mem(addr, data)
            self._store_active_state()
            return
        state = self.task_states.get(pid)
        if not state:
            raise ValueError(f"unknown pid {pid}")
        mem = state.get("mem")
        if mem is None:
            mem = bytearray(64 * 1024)
            state["mem"] = mem
        a = addr & 0xFFFF
        end = min(a + len(data), len(mem))
        mem[a:end] = data[: end - a]
        self.task_states[pid] = state
        task = self.tasks.get(pid)
        if task:
            task["vm_state"] = state

    def handle_command(self, request: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(request, dict):
            return {"status": "error", "error": "invalid_request"}
        cmd = str(request.get("cmd", "")).lower()
        if not cmd:
            return {"status": "error", "error": "missing_cmd"}
        try:
            if cmd == "ping":
                return {"status": "ok", "reply": "pong"}
            if cmd == "info":
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                return {"status": "ok", "info": self.info(pid)}
            if cmd == "reset":
                return self.reset()
            if cmd == "attach":
                self.attached = True
                if self.vm is not None:
                    self.vm.attached = True
                return {"status": "ok", "info": self.info()}
            if cmd == "detach":
                self.attached = False
                if self.vm is not None:
                    self.vm.attached = False
                    self.vm.sleep_pending_ms = None
                    self.vm.sleep_until = None
                return {"status": "ok", "info": self.info()}
            if cmd == "pause":
                pid_value = request.get("pid")
                if pid_value is None:
                    self.paused = True
                    self._store_active_state()
                    return {"status": "ok"}
                task = self.pause_task(int(pid_value))
                return {"status": "ok", "task": task}
            if cmd == "resume":
                pid_value = request.get("pid")
                if pid_value is None:
                    self.paused = False
                    return {"status": "ok"}
                self.paused = False
                task = self.resume_task(int(pid_value))
                return {"status": "ok", "task": task}
            if cmd == "kill":
                pid_value = request.get("pid")
                if pid_value is None:
                    raise ValueError("kill requires 'pid'")
                task = self.kill_task(int(pid_value))
                return {"status": "ok", "task": task}
            if cmd == "load":
                path_value = request.get("path")
                if not path_value:
                    raise ValueError("load requires 'path'")
                return {"status": "ok", "image": self.load_from_path(str(path_value), verbose=bool(request.get("verbose")))}
            if cmd == "ps":
                return {"status": "ok", "tasks": self.task_list()}
            if cmd == "step":
                cycles = int(request.get("cycles", 1))
                return {"status": "ok", "result": self.step(cycles)}
            if cmd == "read_regs":
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                return {"status": "ok", "registers": self.read_regs(pid)}
            if cmd == "write_regs":
                payload = request.get("registers") or {}
                if not isinstance(payload, dict):
                    raise ValueError("write_regs requires dict payload")
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                return {"status": "ok", "registers": self.write_regs(payload, pid)}
            if cmd == "read_mem":
                addr = int(request.get("addr"))
                length = int(request.get("length", 0))
                pid_value = request.get("pid")
                if pid_value is not None:
                    data = self.request_peek(int(pid_value), addr, length)
                else:
                    data = self.read_mem(addr, length)
                return {"status": "ok", "data": data.hex()}
            if cmd == "write_mem":
                addr = int(request.get("addr"))
                data_hex = request.get("data")
                if not isinstance(data_hex, str):
                    raise ValueError("write_mem requires hex string 'data'")
                pid_value = request.get("pid")
                data = bytes.fromhex(data_hex)
                if pid_value is not None:
                    self.request_poke(int(pid_value), addr, data)
                else:
                    self.write_mem(addr, data)
                return {"status": "ok"}
            if cmd == "dumpregs":
                pid_value = request.get("pid")
                pid = int(pid_value) if pid_value is not None else None
                regs = self.request_dump_regs(pid)
                return {"status": "ok", "registers": regs}
            if cmd == "peek":
                pid = int(request.get("pid"))
                addr = int(request.get("addr"))
                length = int(request.get("length", 0))
                data = self.request_peek(pid, addr, length)
                return {"status": "ok", "data": data.hex()}
            if cmd == "poke":
                pid = int(request.get("pid"))
                addr = int(request.get("addr"))
                data_hex = request.get("data")
                if not isinstance(data_hex, str):
                    raise ValueError("poke requires 'data' hex string")
                self.request_poke(pid, addr, bytes.fromhex(data_hex))
                return {"status": "ok"}
            if cmd == "sched":
                pid = int(request.get("pid"))
                priority = request.get("priority")
                quantum = request.get("quantum")
                task = self.set_task_attrs(pid, priority=priority, quantum=quantum)
                return {"status": "ok", "task": task}
            if cmd == "restart":
                targets = request.get("targets")
                if isinstance(targets, str):
                    targets_list = targets.split()
                elif isinstance(targets, list):
                    targets_list = [str(t) for t in targets]
                else:
                    targets_list = ["vm"]
                self.schedule_restart(targets_list)
                return {"status": "ok", "restart": targets_list}
            return {"status": "error", "error": f"unknown_cmd:{cmd}"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _require_vm(self) -> MiniVM:
        if self.vm is None:
            raise RuntimeError("no image loaded")
        return self.vm


class _VMRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        while True:
            line = self.rfile.readline()
            if not line:
                break
            try:
                request = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                self._send({"status": "error", "error": "invalid_json"})
                continue
            response = self.server.controller.handle_command(request)
            self._send(response)

    def _send(self, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self.wfile.write(data)
        self.wfile.flush()

class VMServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, controller: VMController):
        super().__init__(server_address, _VMRequestHandler)
        self.controller = controller
        controller.server = self

def load_hxe(path, *, verbose: bool = False):
    data = Path(path).read_bytes()
    if len(data) < HEADER.size:
        raise ValueError(".hxe file too small")
    fields = HEADER.unpack_from(data)
    header = dict(zip(HEADER_FIELDS, fields))
    if header["magic"] != HSX_MAGIC:
        raise ValueError(f"Bad magic 0x{header['magic']:08X}")
    crc_input = data[: HEADER.size - 4] + data[HEADER.size :]
    calc_crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    if calc_crc != header["crc32"]:
        raise ValueError(f"CRC mismatch: file=0x{header['crc32']:08X} calc=0x{calc_crc:08X}")
    code_start = HEADER.size
    code_end = code_start + header["code_len"]
    ro_end = code_end + header["ro_len"]
    code = data[code_start:code_end]
    rodata = data[code_end:ro_end]
    if verbose:
        print(
            f"[HXE] entry=0x{header['entry']:08X} code_len={header['code_len']} ro_len={header['ro_len']} bss={header['bss_size']} caps=0x{header['req_caps']:08X}"
        )
    return header, code, rodata

def main():
    ap = argparse.ArgumentParser(description="HSX Python VM")
    ap.add_argument("program", nargs="?", help=".hxe image produced by asm.py")
    ap.add_argument("--trace", action="store_true", help="print executed instructions")
    ap.add_argument("--trace-file", help="append trace output to a file")
    ap.add_argument("--exec-root", help="directory containing .hxe payloads for exec SVC")
    ap.add_argument("--svc-trace", action="store_true", help="log SVC invocations")
    ap.add_argument("--max-steps", type=int, default=None, help="safety cap on executed steps")
    ap.add_argument("--max-cycles", type=int, default=None, help="deprecated alias for --max-steps")
    ap.add_argument("--entry-symbol", help="override entry address (numeric for now)")
    ap.add_argument("--no-preload", action="store_true", help="skip demo memory preload")
    ap.add_argument("--dev-libm", action="store_true", help="enable sin_hsx/cos_hsx/exp_hsx soft handlers")
    ap.add_argument("--listen", type=int, help="start RPC server on given TCP port")
    ap.add_argument("--listen-host", default="127.0.0.1", help="interface for RPC server (default: 127.0.0.1)")
    ap.add_argument("-v", "--verbose", action="store_true", help="print header metadata")
    args = ap.parse_args()

    if args.listen:
        controller = VMController(trace=args.trace, svc_trace=args.svc_trace, dev_libm=args.dev_libm)
        if args.program:
            controller.load_from_path(args.program, verbose=args.verbose)
        server = VMServer((args.listen_host, args.listen), controller)
        print(f"[RPC] HSX VM listening on {args.listen_host}:{args.listen}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[RPC] Shutting down")
        finally:
            server.server_close()
        if controller.restart_requested:
            targets = controller.restart_targets or ["vm"]
            if "vm" in targets:
                print("[RPC] Restarting VM process")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if not args.program:
        ap.error("the following arguments are required: program")

    max_steps_arg = args.max_steps if args.max_steps is not None else args.max_cycles
    if max_steps_arg is not None and max_steps_arg <= 0:
        max_steps = None
    else:
        max_steps = max_steps_arg or 100000

    trace_fp = None
    if args.trace_file:
        trace_fp = open(args.trace_file, "w", encoding="utf-8")

    header, code, rodata = load_hxe(args.program, verbose=args.verbose)

    exec_root = None
    if args.exec_root:
        exec_root = Path(args.exec_root).resolve()
    else:
        default_root = Path(args.program).resolve().parent / "payloads"
        if default_root.exists():
            exec_root = default_root

    vm = MiniVM(
        code,
        entry=header["entry"],
        rodata=rodata,
        trace=args.trace,
        svc_trace=args.svc_trace,
        dev_libm=args.dev_libm,
        trace_file=trace_fp,
        exec_root=exec_root,
    )

    if args.entry_symbol:
        try:
            entry_override = int(args.entry_symbol, 0)
        except ValueError as exc:
            raise SystemExit("--entry-symbol must be numeric (e.g. 0x100)") from exc
        vm.set_entry(entry_override)

    try:
        if not args.no_preload:
            vm.mem[0x0200:0x020C] = b"/hello.txt" + bytes([0])
            vm.mem[0x0100:0x0114] = b"hello from MiniVM!\n"

        while vm.running and (max_steps is None or vm.cycles < max_steps):
            vm.step()
    finally:
        if trace_fp:
            trace_fp.close()

    if vm.running and max_steps is not None and vm.cycles >= max_steps:
        print(f"[VM] Max steps {max_steps} reached; halting")
    print(f"[VM] Halted after {vm.cycles} cycles @ PC=0x{vm.pc:04X}")
    print(f"[VM] R0..R7: {vm.regs[:8]}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as exc:
        raise
