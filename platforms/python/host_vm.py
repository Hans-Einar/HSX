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
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, Optional, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from python.mailbox import MailboxManager, MailboxError, MailboxMessage
    from python import hsx_mailbox_constants as mbx_const
except ImportError as exc:  # pragma: no cover - require repo sources
    raise ImportError("HSX repo modules not found; ensure repository root on PYTHONPATH") from exc

HSX_MAGIC = 0x48535845  # 'HSXE'
HSX_VERSION = 0x0001
MAX_CODE_LEN = 0x10000
MAX_RODATA_LEN = 0x10000
MAX_BSS_SIZE = 0x10000
HSX_ERR_ENOSYS = 0xFFFF_FF01
HSX_ERR_STACK_UNDERFLOW = 0xFFFF_FF02
HSX_ERR_STACK_OVERFLOW = 0xFFFF_FF03
HSX_ERR_MEM_FAULT = 0xFFFF_FF04
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
    wait_kind: Optional[str] = None
    wait_mailbox: Optional[int] = None
    wait_deadline: Optional[float] = None
    wait_handle: Optional[int] = None
    fd_table: Dict[int, int] = field(default_factory=dict)


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
        wait_kind=ctx.wait_kind,
        wait_mailbox=ctx.wait_mailbox,
        wait_deadline=ctx.wait_deadline,
        wait_handle=ctx.wait_handle,
        fd_table=dict(ctx.fd_table),
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
        "wait_kind": ctx.wait_kind,
        "wait_mailbox": ctx.wait_mailbox,
        "wait_deadline": ctx.wait_deadline,
        "wait_handle": ctx.wait_handle,
        "fd_table": dict(ctx.fd_table),
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
        wait_kind=data.get("wait_kind"),
        wait_mailbox=data.get("wait_mailbox"),
        wait_deadline=data.get("wait_deadline"),
        wait_handle=data.get("wait_handle"),
        fd_table={int(k): int(v) for k, v in dict(data.get("fd_table", {})).items()},
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
        mant = int(round(a * (1 << 24)))
        if mant <= 0:
            return s << 15
        if mant > 0x3FF:
            mant = 0x3FF
        return (s << 15) | mant
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
        self.err_invalid_path = -22

    @staticmethod
    def _is_safe_path(path: str) -> bool:
        if not path:
            return False
        candidate = path.replace('\\', '/').strip()
        if ':' in candidate:
            return False
        p = PurePosixPath(candidate)
        if p.is_absolute():
            return False
        return all(part not in ('', '..') for part in p.parts)

    def open(self, path, flags=0):
        if not self._is_safe_path(path):
            return self.err_invalid_path
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
    def __init__(
        self,
        code: bytes,
        *,
        entry: int = 0,
        rodata: bytes = b"",
        trace: bool = False,
        svc_trace: bool = False,
        dev_libm: bool = False,
        trace_file=None,
        exec_root=None,
        mailboxes: Optional[MailboxManager] = None,
        mailbox_handler: Optional[Callable[[int], None]] = None,
    ):
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
        self.mailboxes = mailboxes or MailboxManager()
        self._mailbox_handler: Optional[Callable[[int], None]] = mailbox_handler
        self.pid: Optional[int] = None
        self.call_stack: List[int] = []
        self._last_pc: Optional[int] = None
        self._repeat_pc_count: int = 0
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
        self.pid = ctx.pid
        ctx.state = "running" if self.running else ctx.state

    def set_mailbox_handler(self, handler: Optional[Callable[[int], None]]) -> None:
        self._mailbox_handler = handler

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
                "wait_kind": ctx.wait_kind,
                "wait_mailbox": ctx.wait_mailbox,
                "wait_deadline": ctx.wait_deadline,
                "wait_handle": ctx.wait_handle,
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
            "call_stack": list(self.call_stack),
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
        self.call_stack = list(state.get("call_stack", []))
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

        prev_pc = self.pc

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

        def ensure_range(addr, size):
            if addr < 0 or addr + size > len(self.mem):
                raise MemoryError

        def ld32(addr):
            a = addr & 0xFFFF
            ensure_range(a, 4)
            return (
                self.mem[a]
                | (self.mem[a + 1] << 8)
                | (self.mem[a + 2] << 16)
                | (self.mem[a + 3] << 24)
            )

        def st32(addr, val):
            a = addr & 0xFFFF
            ensure_range(a, 4)
            self.mem[a] = val & 0xFF
            self.mem[a + 1] = (val >> 8) & 0xFF
            self.mem[a + 2] = (val >> 16) & 0xFF
            self.mem[a + 3] = (val >> 24) & 0xFF

        def ld8(addr):
            a = addr & 0xFFFF
            ensure_range(a, 1)
            return self.mem[a]

        def st8(addr, v):
            a = addr & 0xFFFF
            ensure_range(a, 1)
            self.mem[a] = v & 0xFF

        def ld16(addr):
            a = addr & 0xFFFF
            ensure_range(a, 2)
            return self.mem[a] | (self.mem[a + 1] << 8)

        def st16(addr, v):
            a = addr & 0xFFFF
            ensure_range(a, 2)
            self.mem[a] = v & 0xFF
            self.mem[a + 1] = (v >> 8) & 0xFF

        def trap_memory_fault():
            if self.trace or self.trace_out:
                self._log("[VM] memory access out of range")
            self.regs[0] = HSX_ERR_MEM_FAULT
            self.running = False
            self.save_context()

        if self.trace or self.trace_out:
            self._log(f"[TRACE] pc=0x{self.pc:04X} op=0x{op:02X} rd=R{rd} rs1=R{rs1} rs2=R{rs2} imm={imm}")

        adv = 4
        if op == 0x01:  # LDI
            self.regs[rd] = imm & 0xFFFFFFFF
        elif op == 0x02:  # LD
            try:
                self.regs[rd] = ld32((self.regs[rs1] + imm) & 0xFFFFFFFF)
            except MemoryError:
                trap_memory_fault()
                return
        elif op == 0x03:  # ST
            try:
                st32((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
            except MemoryError:
                trap_memory_fault()
                return
        elif op == 0x04:  # MOV
            self.regs[rd] = self.regs[rs1]
        elif op == 0x06:  # LDB
            try:
                self.regs[rd] = ld8((self.regs[rs1] + imm) & 0xFFFFFFFF)
            except MemoryError:
                trap_memory_fault()
                return
        elif op == 0x07:  # LDH
            try:
                self.regs[rd] = ld16((self.regs[rs1] + imm) & 0xFFFFFFFF)
            except MemoryError:
                trap_memory_fault()
                return
        elif op == 0x08:  # STB
            try:
                st8((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
            except MemoryError:
                trap_memory_fault()
                return
        elif op == 0x09:  # STH
            try:
                st16((self.regs[rs1] + imm) & 0xFFFFFFFF, self.regs[rs2])
            except MemoryError:
                trap_memory_fault()
                return
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
        elif op == 0x24:  # CALL
            return_addr = (self.pc + 4) & 0xFFFFFFFF
            target = imm & 0xFFFFFFFF
            raw_sp = self.sp - 4
            if raw_sp < 0 or raw_sp < (self.context.stack_limit or 0) or raw_sp + 4 > len(self.mem):
                self._log("[CALL] stack overflow")
                self.regs[0] = HSX_ERR_STACK_OVERFLOW
                self.running = False
                self.save_context()
                return
            new_sp = raw_sp & 0xFFFFFFFF
            st32(new_sp, return_addr)
            self.sp = new_sp
            if len(self.regs) >= 16:
                self.regs[15] = self.sp & 0xFFFFFFFF
            self.call_stack.append(return_addr)
            if self.trace:
                self._log(
                    f"[CALL] pc=0x{(self.pc & 0xFFFF):04X} -> 0x{target & 0xFFFFFFFF:04X} "
                    f"ret=0x{return_addr:04X} sp=0x{self.sp:04X}"
                )
            self.pc = target
            adv = 0
        elif op == 0x25:  # RET
            if self.trace:
                self._log(f"[RET] pc=0x{(self.pc & 0xFFFF):04X} sp=0x{self.sp:04X}")
            if not self.call_stack:
                self.running = False
                self.save_context()
                return
            else:
                if self.sp >= len(self.mem):
                    self._log("[RET] stack underflow")
                    self.regs[0] = HSX_ERR_STACK_UNDERFLOW
                    self.running = False
                    self.save_context()
                    return
                else:
                    return_addr = ld32(self.sp)
                    self.sp = (self.sp + 4) & 0xFFFFFFFF
                    if len(self.regs) >= 16:
                        self.regs[15] = self.sp & 0xFFFFFFFF
                    self.call_stack.pop()
                    self.pc = return_addr & 0xFFFFFFFF
                    adv = 0
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

        if self.pc == prev_pc:
            self._repeat_pc_count += 1
            if op == 0x24 and self._repeat_pc_count >= 32:
                self._log(
                    f"[VM] Possible stuck CALL at PC=0x{prev_pc & 0xFFFF:04X}; check stack state"
                )
        else:
            self._repeat_pc_count = 0
        self._last_pc = self.pc

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
        elif mod == mbx_const.HSX_MBX_MODULE_ID:
            self._svc_mailbox(fn)
        elif mod == 0x7:
            self._svc_exec(fn)
        elif mod == 0x3:
            self._svc_shell(fn)
        elif mod == 0x4:
            self._svc_fs(fn)
        else:
            self._log(f"[SVC] mod=0x{mod:X} fn=0x{fn:X} (stub)")
            self.regs[0] = HSX_ERR_ENOSYS

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
            ctx = self.context
            mailbox_handle = None
            if ctx is not None and ctx.fd_table:
                mailbox_handle = ctx.fd_table.get(fd)
            if mailbox_handle is not None and ln > 0:
                flags = 0
                if fd == 1:
                    flags |= mbx_const.HSX_MBX_FLAG_STDOUT
                elif fd == 2:
                    flags |= mbx_const.HSX_MBX_FLAG_STDERR
                try:
                    ok, descriptor_id = self.mailboxes.send(
                        pid=self.pid or 0,
                        handle=mailbox_handle,
                        payload=buf,
                        flags=flags,
                    )
                except MailboxError as exc:
                    self._log(f"[STDIO] mailbox send failed fd={fd}: {exc}")
                    ok = False
                    descriptor_id = None
                if ok:
                    self.regs[0] = len(buf)
                    if descriptor_id is not None:
                        self.emit_event(
                            {
                                "type": "mailbox_send",
                                "pid": self.pid or 0,
                                "descriptor": descriptor_id,
                                "length": len(buf),
                                "flags": flags,
                                "channel": 0,
                            }
                        )
                    return
                self.regs[0] = 0
                return
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


    def _svc_mailbox(self, fn: int) -> None:
        handler = self._mailbox_handler
        if handler is not None:
            handler(fn)
        else:
            self._svc_mailbox_default(fn)

    def _svc_mailbox_default(self, fn: int) -> None:
        pid = self.pid or 0
        try:
            if fn == mbx_const.HSX_MBX_FN_OPEN:
                target = self._read_c_string(self.regs[1])
                flags = self.regs[2] & 0xFFFF
                handle = self.mailboxes.open(pid=pid, target=target or "", flags=flags)
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                self.regs[1] = handle
                return
            if fn == mbx_const.HSX_MBX_FN_BIND:
                target = self._read_c_string(self.regs[1])
                capacity = self.regs[2] & 0xFFFF
                mode = self.regs[3] & 0xFFFF
                desc = self.mailboxes.bind_target(pid=pid, target=target or "", capacity=capacity or None, mode_mask=mode)
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                self.regs[1] = desc.descriptor_id
                return
            if fn == mbx_const.HSX_MBX_FN_CLOSE:
                handle = self.regs[1] & 0xFFFF
                self.mailboxes.close(pid=pid, handle=handle)
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                return
            if fn == mbx_const.HSX_MBX_FN_SEND:
                handle = self.regs[1] & 0xFFFF
                ptr = self.regs[2] & 0xFFFF
                length = self.regs[3] & 0xFFFF
                flags = self.regs[4] & 0xFFFF
                channel = self.regs[5] & 0xFFFF
                payload = bytes(self.mem[ptr : ptr + length])
                ok, _ = self.mailboxes.send(pid=pid, handle=handle, payload=payload, flags=flags, channel=channel)
                if ok:
                    self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                    self.regs[1] = len(payload)
                else:
                    self.regs[0] = mbx_const.HSX_MBX_STATUS_WOULDBLOCK
                return
            if fn == mbx_const.HSX_MBX_FN_RECV:
                handle = self.regs[1] & 0xFFFF
                ptr = self.regs[2] & 0xFFFF
                max_len = self.regs[3] & 0xFFFF
                msg = self.mailboxes.recv(pid=pid, handle=handle)
                if msg is None:
                    self.regs[0] = mbx_const.HSX_MBX_STATUS_NO_DATA
                    self.regs[1] = 0
                    return
                length = min(max_len, msg.length)
                self.mem[ptr : ptr + length] = msg.payload[:length]
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                self.regs[1] = length
                self.regs[2] = msg.flags
                self.regs[3] = msg.channel
                self.regs[4] = msg.src_pid
                return
            if fn == mbx_const.HSX_MBX_FN_PEEK:
                handle = self.regs[1] & 0xFFFF
                info = self.mailboxes.peek(pid=pid, handle=handle)
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                self.regs[1] = info.get("depth", 0)
                self.regs[2] = info.get("bytes_used", 0)
                self.regs[3] = info.get("next_len", 0)
                return
            if fn == mbx_const.HSX_MBX_FN_TAP:
                handle = self.regs[1] & 0xFFFF
                enable = bool(self.regs[2] & 0x1)
                self.mailboxes.tap(pid=pid, handle=handle, enable=enable)
                self.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                return
        except MailboxError as exc:
            self._log(f"[MBX] pid={pid} fn={fn} error: {exc}")
            self.regs[0] = mbx_const.HSX_MBX_STATUS_INTERNAL_ERROR
            return
        self.regs[0] = mbx_const.HSX_MBX_STATUS_INTERNAL_ERROR


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
        self.mailboxes = MailboxManager()
        self.waiting_tasks: Dict[int, Dict[str, Any]] = {}

    def reset(self) -> Dict[str, Any]:
        self.vm = None
        self.header = None
        self.program_path = None
        self.attached = False
        self.paused = False
        self.tasks.clear()
        self.task_states.clear()
        self.waiting_tasks.clear()
        self.mailboxes = MailboxManager()
        self.current_pid = None
        self.next_pid = 1
        return {"status": "ok"}

    def mailbox_snapshot(self) -> List[Dict[str, Any]]:
        return self.mailboxes.descriptor_snapshot()

    def mailbox_open(self, pid: int, target: str, flags: int = 0) -> Dict[str, Any]:
        try:
            handle = self.mailboxes.open(pid=pid, target=target, flags=flags)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "handle": handle,
            "target": target,
            "pid": pid,
        }

    def mailbox_close(self, pid: int, handle: int) -> Dict[str, Any]:
        try:
            self.mailboxes.close(pid=pid, handle=handle)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "ok", "mbx_status": mbx_const.HSX_MBX_STATUS_OK}

    def mailbox_bind(self, pid: int, target: str, *, capacity: Optional[int] = None, mode: int = 0) -> Dict[str, Any]:
        try:
            desc = self.mailboxes.bind_target(pid=pid, target=target, capacity=capacity, mode_mask=mode)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "descriptor": desc.descriptor_id,
            "capacity": desc.capacity,
            "mode": desc.mode_mask,
        }

    def mailbox_config_stdio(self, stream: str, mode: int, *, update_existing: bool = True) -> Dict[str, Any]:
        try:
            updated = self.mailboxes.set_default_stdio_mode(stream, mode, update_existing=update_existing)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "mode": mode,
            "stream": stream,
            "updated_descriptors": updated,
        }

    def mailbox_stdio_summary(self, *, pid: Optional[int] = None, stream: Optional[str] = None, default_only: bool = False) -> Dict[str, Any]:
        streams = self._normalize_stdio_summary_streams(stream)
        default_modes = self.mailboxes.default_stdio_modes()
        summary: Dict[str, Any] = {
            "streams": streams,
            "default": {name: default_modes.get(name, mbx_const.HSX_MBX_MODE_RDWR) for name in streams},
        }
        if default_only:
            return summary
        if pid is None:
            tasks_summary: List[Dict[str, Any]] = []
            for task_pid in sorted(self.tasks):
                modes = self.mailboxes.stdio_modes_for_pid(task_pid)
                tasks_summary.append(
                    {
                        "pid": task_pid,
                        "streams": {name: modes.get(name, mbx_const.HSX_MBX_MODE_RDWR) for name in streams},
                    }
                )
            summary["tasks"] = tasks_summary
            return summary
        task_pid = int(pid)
        if task_pid not in self.tasks:
            raise ValueError(f"unknown pid {task_pid}")
        modes = self.mailboxes.stdio_modes_for_pid(task_pid)
        summary["task"] = {
            "pid": task_pid,
            "streams": {name: modes.get(name, mbx_const.HSX_MBX_MODE_RDWR) for name in streams},
        }
        return summary

    @staticmethod
    def _normalize_stdio_summary_streams(stream: Optional[str]) -> List[str]:
        if stream is None:
            return ["in", "out", "err"]
        normalized = stream.lower()
        if normalized in {"both"}:
            return ["out", "err"]
        if normalized in {"all", "any"}:
            return ["in", "out", "err"]
        if normalized in {"out", "stdout"}:
            return ["out"]
        if normalized in {"err", "stderr"}:
            return ["err"]
        if normalized in {"in", "stdin"}:
            return ["in"]
        raise ValueError(f"unknown stdio stream '{stream}'")

    def mailbox_send(
        self,
        pid: int,
        handle: Optional[int],
        *,
        data: Optional[str] = None,
        data_hex: Optional[str] = None,
        flags: int = 0,
        channel: int = 0,
        target: Optional[str] = None,
    ) -> Dict[str, Any]:
        if data_hex is not None:
            payload = bytes.fromhex(data_hex)
        elif data is not None:
            payload = data.encode("utf-8")
        else:
            payload = b""

        working_handle = handle if isinstance(handle, int) and handle > 0 else None
        auto_handles: List[int] = []

        def _close_auto_handles() -> None:
            seen: set[int] = set()
            for auto in auto_handles:
                if auto in seen:
                    continue
                seen.add(auto)
                try:
                    self.mailboxes.close(pid=pid, handle=auto)
                except MailboxError:
                    continue

        if working_handle is None:
            if not target:
                return {"status": "error", "error": "mailbox_send requires handle or target"}
            try:
                working_handle = self.mailboxes.open(pid=pid, target=target)
            except MailboxError as exc:
                return {"status": "error", "error": str(exc)}
            auto_handles.append(working_handle)

        try:
            ok, descriptor_id = self.mailboxes.send(
                pid=pid,
                handle=working_handle,
                payload=payload,
                flags=flags,
                channel=channel,
            )
        except MailboxError as exc:
            if not target:
                _close_auto_handles()
                return {"status": "error", "error": str(exc)}
            try:
                self.mailboxes.bind_target(pid=pid, target=target, capacity=None)
                working_handle = self.mailboxes.open(pid=pid, target=target)
                auto_handles.append(working_handle)
                ok, descriptor_id = self.mailboxes.send(
                    pid=pid,
                    handle=working_handle,
                    payload=payload,
                    flags=flags,
                    channel=channel,
                )
            except MailboxError as bind_exc:
                _close_auto_handles()
                return {"status": "error", "error": str(bind_exc)}

        _close_auto_handles()

        status = mbx_const.HSX_MBX_STATUS_OK if ok else mbx_const.HSX_MBX_STATUS_WOULDBLOCK
        if ok:
            self._deliver_mailbox_messages(descriptor_id)
        result = {
            "status": "ok",
            "mbx_status": status,
            "length": len(payload) if ok else 0,
            "descriptor": descriptor_id,
        }
        if target:
            result["target"] = target
        return result

    def mailbox_recv(
        self,
        pid: int,
        handle: int,
        *,
        max_len: int = 512,
        timeout: int = mbx_const.HSX_MBX_TIMEOUT_POLL,
    ) -> Dict[str, Any]:
        # Initial implementation honours poll semantics only; blocking handled during scheduler updates.
        if timeout not in (mbx_const.HSX_MBX_TIMEOUT_POLL, 0):
            # Placeholder: future revisions will support blocking/timeouts via scheduler.
            timeout = mbx_const.HSX_MBX_TIMEOUT_POLL
        try:
            msg = self.mailboxes.recv(pid=pid, handle=handle, record_waiter=False)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        if msg is None:
            return {
                "status": "ok",
                "mbx_status": mbx_const.HSX_MBX_STATUS_NO_DATA,
                "length": 0,
            }
        length = min(max_len, msg.length)
        payload = msg.payload[:length]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "length": length,
            "flags": msg.flags,
            "channel": msg.channel,
            "src_pid": msg.src_pid,
            "data_hex": payload.hex(),
            "text": text,
        }

    def mailbox_peek(self, pid: int, handle: int) -> Dict[str, Any]:
        try:
            info = self.mailboxes.peek(pid=pid, handle=handle)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "ok", "info": info}

    def mailbox_tap(self, pid: int, handle: int, enable: bool = True) -> Dict[str, Any]:
        try:
            self.mailboxes.tap(pid=pid, handle=handle, enable=enable)
        except MailboxError as exc:
            return {"status": "error", "error": str(exc)}
        return {"status": "ok", "mbx_status": mbx_const.HSX_MBX_STATUS_OK}

    def _svc_mailbox_controller(self, vm: MiniVM, fn: int) -> None:
        pid = self.current_pid or vm.pid or (vm.context.pid if vm.context else 0) or 0
        try:
            if fn == mbx_const.HSX_MBX_FN_OPEN:
                target = vm._read_c_string(vm.regs[1])
                flags = vm.regs[2] & 0xFFFF
                handle = self.mailboxes.open(pid=pid, target=target or "", flags=flags)
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                vm.regs[1] = handle
                return
            if fn == mbx_const.HSX_MBX_FN_BIND:
                target = vm._read_c_string(vm.regs[1])
                capacity = vm.regs[2] & 0xFFFF
                mode = vm.regs[3] & 0xFFFF
                desc = self.mailboxes.bind_target(pid=pid, target=target or "", capacity=capacity or None, mode_mask=mode)
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                vm.regs[1] = desc.descriptor_id
                return
            if fn == mbx_const.HSX_MBX_FN_CLOSE:
                handle = vm.regs[1] & 0xFFFF
                self.mailboxes.close(pid=pid, handle=handle)
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                return
            if fn == mbx_const.HSX_MBX_FN_PEEK:
                handle = vm.regs[1] & 0xFFFF
                info = self.mailboxes.peek(pid=pid, handle=handle)
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                vm.regs[1] = info.get("depth", 0)
                vm.regs[2] = info.get("bytes_used", 0)
                vm.regs[3] = info.get("next_len", 0)
                return
            if fn == mbx_const.HSX_MBX_FN_TAP:
                handle = vm.regs[1] & 0xFFFF
                enable = bool(vm.regs[2] & 0x1)
                self.mailboxes.tap(pid=pid, handle=handle, enable=enable)
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                return
            if fn == mbx_const.HSX_MBX_FN_SEND:
                handle = vm.regs[1] & 0xFFFF
                ptr = vm.regs[2] & 0xFFFF
                length = vm.regs[3] & 0xFFFF
                flags = vm.regs[4] & 0xFFFF
                channel = vm.regs[5] & 0xFFFF
                payload = bytes(vm.mem[ptr : ptr + length])
                ok, descriptor_id = self.mailboxes.send(pid=pid, handle=handle, payload=payload, flags=flags, channel=channel)
                if ok:
                    vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                    vm.regs[1] = len(payload)
                    vm.emit_event({
                        "type": "mailbox_send",
                        "pid": pid,
                        "descriptor": descriptor_id,
                        "length": len(payload),
                        "flags": flags,
                        "channel": channel,
                    })
                    self._deliver_mailbox_messages(descriptor_id)
                else:
                    vm.regs[0] = mbx_const.HSX_MBX_STATUS_WOULDBLOCK
                return
            if fn == mbx_const.HSX_MBX_FN_RECV:
                handle = vm.regs[1] & 0xFFFF
                ptr = vm.regs[2] & 0xFFFF
                max_len = vm.regs[3] & 0xFFFF
                timeout = vm.regs[4] & 0xFFFF
                msg = self.mailboxes.recv(pid=pid, handle=handle, record_waiter=False)
                if msg is None:
                    if not self._prepare_mailbox_wait(vm, pid, handle, ptr, max_len, timeout):
                        vm.regs[0] = mbx_const.HSX_MBX_STATUS_NO_DATA
                        vm.regs[1] = 0
                    return
                length = min(max_len, msg.length)
                vm.mem[ptr : ptr + length] = msg.payload[:length]
                vm.regs[0] = mbx_const.HSX_MBX_STATUS_OK
                vm.regs[1] = length
                vm.regs[2] = msg.flags
                vm.regs[3] = msg.channel
                vm.regs[4] = msg.src_pid
                vm.emit_event({
                    "type": "mailbox_recv",
                    "pid": pid,
                    "length": length,
                    "flags": msg.flags,
                    "channel": msg.channel,
                    "src_pid": msg.src_pid,
                })
                return
        except MailboxError as exc:
            vm.regs[0] = mbx_const.HSX_MBX_STATUS_INTERNAL_ERROR
            vm.emit_event({"type": "mailbox_error", "pid": pid, "fn": fn, "error": str(exc)})
            return
        vm.regs[0] = mbx_const.HSX_MBX_STATUS_INTERNAL_ERROR

    def _prepare_mailbox_wait(self, vm: MiniVM, pid: int, handle: int, ptr: int, max_len: int, timeout: int) -> bool:
        if timeout in (mbx_const.HSX_MBX_TIMEOUT_POLL, 0):
            return False
        try:
            desc = self.mailboxes.descriptor_for_handle(pid, handle)
        except MailboxError as exc:
            vm.regs[0] = mbx_const.HSX_MBX_STATUS_INVALID_HANDLE
            vm.emit_event({"type": "mailbox_error", "pid": pid, "fn": mbx_const.HSX_MBX_FN_RECV, "error": str(exc)})
            return False
        descriptor_id = desc.descriptor_id
        if pid not in desc.waiters:
            desc.waiters.append(pid)
        now = time.monotonic()
        deadline: Optional[float]
        if timeout == mbx_const.HSX_MBX_TIMEOUT_INFINITE:
            deadline = None
        else:
            deadline = now + (max(timeout, 1) / 1000.0)
        wait_info = {
            "pid": pid,
            "descriptor_id": descriptor_id,
            "handle": handle,
            "buffer_ptr": ptr & 0xFFFF,
            "max_len": max_len & 0xFFFF,
            "timeout": timeout,
            "requested_at": now,
            "deadline": deadline,
        }
        self.waiting_tasks[pid] = wait_info
        ctx = vm.context
        ctx.state = "waiting_mbx"
        ctx.wait_kind = "mailbox"
        ctx.wait_mailbox = descriptor_id
        ctx.wait_handle = handle
        ctx.wait_deadline = deadline
        vm.running = False
        state = self.task_states.get(pid)
        if state:
            state["context"] = context_to_dict(ctx)
            state["wait_info"] = wait_info
        task = self.tasks.get(pid)
        if task:
            task["state"] = "waiting_mbx"
            task["wait_mailbox"] = descriptor_id
            task["wait_deadline"] = deadline
            task["wait_handle"] = handle
        vm.emit_event(
            {
                "type": "mailbox_wait",
                "pid": pid,
                "descriptor": descriptor_id,
                "handle": handle,
                "timeout": timeout,
            }
        )
        return True

    def _complete_mailbox_wait(
        self,
        pid: int,
        *,
        status: int,
        descriptor_id: Optional[int],
        message: Optional[MailboxMessage],
        timed_out: bool = False,
    ) -> None:
        wait_info = self.waiting_tasks.pop(pid, None)
        if wait_info is None:
            return
        if descriptor_id is None:
            descriptor_id = wait_info.get("descriptor_id")
        if descriptor_id is not None:
            self.mailboxes.remove_waiter(descriptor_id, pid)
        buffer_ptr = wait_info.get("buffer_ptr", 0) & 0xFFFF
        max_len = wait_info.get("max_len", 0) & 0xFFFF
        length = 0
        flags = 0
        channel = 0
        src_pid = 0
        payload = b""
        if message is not None:
            length = min(max_len, message.length)
            flags = message.flags
            channel = message.channel
            src_pid = message.src_pid
            payload = message.payload[:length]
        state = self.task_states.get(pid)
        if state is None:
            state = self.tasks.get(pid, {}).get("vm_state")
        if state is not None:
            mem = state.get("mem")
            if mem is None:
                mem = bytearray(64 * 1024)
                state["mem"] = mem
            if payload:
                mem[buffer_ptr : buffer_ptr + length] = payload
            ctx_dict = state.get("context") or {}
            regs = list(ctx_dict.get("regs", [0] * 16))
            while len(regs) < 16:
                regs.append(0)
            regs[0] = status & 0xFFFF
            regs[1] = length & 0xFFFF
            regs[2] = flags & 0xFFFF
            regs[3] = channel & 0xFFFF
            regs[4] = src_pid & 0xFFFF
            ctx_dict["regs"] = regs
            ctx_dict["state"] = "ready"
            ctx_dict["wait_kind"] = None
            ctx_dict["wait_mailbox"] = None
            ctx_dict["wait_deadline"] = None
            ctx_dict["wait_handle"] = None
            state["context"] = ctx_dict
            state.pop("wait_info", None)
            self.task_states[pid] = state
        task = self.tasks.get(pid)
        if task:
            task["state"] = "ready"
            task["wait_mailbox"] = None
            task["wait_deadline"] = None
            task["wait_handle"] = None
        if self.current_pid == pid and self.vm is not None and self.vm.context.pid == pid:
            if payload:
                self.vm.mem[buffer_ptr : buffer_ptr + length] = payload
            self.vm.regs[0] = status & 0xFFFF
            self.vm.regs[1] = length & 0xFFFF
            self.vm.regs[2] = flags & 0xFFFF
            self.vm.regs[3] = channel & 0xFFFF
            self.vm.regs[4] = src_pid & 0xFFFF
            self.vm.context.state = "ready"
            self.vm.context.wait_kind = None
            self.vm.context.wait_mailbox = None
            self.vm.context.wait_handle = None
            self.vm.context.wait_deadline = None
            self.vm.running = True
        event_type = "mailbox_timeout" if timed_out else "mailbox_wake"
        event_payload = {
            "type": event_type,
            "pid": pid,
            "descriptor": descriptor_id,
            "status": status,
            "length": length,
            "flags": flags,
            "channel": channel,
            "src_pid": src_pid,
        }
        if self.vm is not None:
            self.vm.emit_event(event_payload)

    def _deliver_mailbox_messages(self, descriptor_id: int) -> None:
        try:
            desc = self.mailboxes.descriptor_by_id(descriptor_id)
        except MailboxError:
            return
        while desc.waiters:
            waiter_pid = desc.waiters[0]
            wait_info = self.waiting_tasks.get(waiter_pid)
            if wait_info is None:
                desc.waiters.pop(0)
                continue
            handle = wait_info.get("handle")
            try:
                message = self.mailboxes.recv(pid=waiter_pid, handle=handle, record_waiter=False)
            except MailboxError:
                desc.waiters.pop(0)
                self.waiting_tasks.pop(waiter_pid, None)
                continue
            if message is None:
                break
            self._complete_mailbox_wait(
                waiter_pid,
                status=mbx_const.HSX_MBX_STATUS_OK,
                descriptor_id=descriptor_id,
                message=message,
                timed_out=False,
            )

    def _check_mailbox_timeouts(self) -> None:
        if not self.waiting_tasks:
            return
        now = time.monotonic()
        expired: List[int] = []
        for pid, wait_info in list(self.waiting_tasks.items()):
            deadline = wait_info.get("deadline")
            if deadline is not None and now >= deadline:
                expired.append(pid)
        for pid in expired:
            info = self.waiting_tasks.get(pid)
            if not info:
                continue
            descriptor_id = info.get("descriptor_id")
            self._complete_mailbox_wait(
                pid,
                status=mbx_const.HSX_MBX_STATUS_NO_DATA,
                descriptor_id=descriptor_id,
                message=None,
                timed_out=True,
            )

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
        self.mailboxes.register_task(pid)
        stdio_handles = self.mailboxes.ensure_stdio_handles(pid)
        fd_table = {int(k): int(v) for k, v in dict(ctx.get("fd_table", {})).items()}
        fd_table.update(
            {
                fd: handle
                for fd, handle in (
                    (0, stdio_handles.get("stdin")),
                    (1, stdio_handles.get("stdout")),
                    (2, stdio_handles.get("stderr")),
                )
                if handle is not None
            }
        )
        ctx["fd_table"] = fd_table
        self.program_path = self.tasks[pid]["program"]
        self._activate_task(pid, state_override=state)
        return {
            "pid": pid,
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
            else:
                context_state = ctx.get("state")
                if context_state == "waiting_mbx" or self.waiting_tasks.get(self.current_pid):
                    task["state"] = "waiting_mbx"
                    ctx["state"] = "waiting_mbx"
                elif self.vm.running:
                    task["state"] = "ready"
                    ctx["state"] = "ready"
                else:
                    task["state"] = "stopped"
                    ctx["state"] = "stopped"
        wait_info = self.waiting_tasks.get(self.current_pid)
        if wait_info is not None:
            state["wait_info"] = wait_info
            ctx = state["context"]
            ctx["wait_kind"] = "mailbox"
            ctx["wait_mailbox"] = wait_info.get("descriptor_id")
            ctx["wait_handle"] = wait_info.get("handle")
            ctx["wait_deadline"] = wait_info.get("deadline")
            state["context"] = ctx
        else:
            state.pop("wait_info", None)

    def _activate_task(self, pid: int, state_override: Optional[Dict[str, Any]] = None) -> None:
        task = self._get_task(pid)
        state = state_override or self.task_states.get(pid) or task.get("vm_state")
        if state is None:
            raise ValueError(f"no state for pid {pid}")
        if self.vm is None:
            initial_code = bytes(state.get("code", bytearray()))
            entry = state.get("context", {}).get("pc", task.get("pc", 0))
            self.vm = MiniVM(
                initial_code,
                entry=entry,
                trace=self.trace,
                svc_trace=self.svc_trace,
                dev_libm=self.dev_libm,
                mailboxes=self.mailboxes,
            )
        self.vm.set_mailbox_handler(lambda fn, vm=self.vm: self._svc_mailbox_controller(vm, fn))
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
        self._check_mailbox_timeouts()
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
        runnable = self._runnable_pids()
        if not runnable:
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
        if self.current_pid is None or self.current_pid not in runnable:
            self._activate_task(runnable[0])
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
        executed_pid = self.current_pid
        self._store_active_state()
        self._check_mailbox_timeouts()
        self._rotate_active()
        next_pid = self.current_pid
        current_pid_field = executed_pid if executed_pid is not None else next_pid
        if current_pid_field is None:
            current_pid_field = next_pid
        if next_pid is None:
            next_pid = current_pid_field
        return {
            "executed": executed,
            "running": snapshot["running"],
            "pc": snapshot["pc"],
            "cycles": snapshot["cycles"],
            "sleep_pending": bool((vm.sleep_until is not None) or (vm.sleep_pending_ms is not None)),
            "events": events,
            "paused": self.paused,
            "current_pid": current_pid_field,
            "next_pid": next_pid,
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
            if cmd == "mailbox_snapshot":
                return {"status": "ok", "descriptors": self.mailbox_snapshot()}
            if cmd == "mailbox_stdio_summary":
                pid_value = request.get("pid")
                stream_value = request.get("stream")
                default_only = bool(request.get("default_only", False))
                pid: Optional[int] = None
                if isinstance(pid_value, str):
                    stripped = pid_value.strip()
                    if stripped:
                        lower = stripped.lower()
                        if lower in {"default", "global", "template"}:
                            default_only = True
                        elif lower in {"all", "*"}:
                            pid = None
                        else:
                            pid = int(stripped, 0)
                elif pid_value is not None:
                    pid = int(pid_value)
                stream_arg = str(stream_value) if isinstance(stream_value, str) else None
                summary = self.mailbox_stdio_summary(pid=pid, stream=stream_arg, default_only=default_only)
                return {"status": "ok", "summary": summary}
            if cmd == "mailbox_open":
                pid = int(request.get("pid", 0))
                target = str(request.get("target", ""))
                flags = int(request.get("flags", 0))
                return self.mailbox_open(pid, target, flags)
            if cmd == "mailbox_close":
                pid = int(request.get("pid", 0))
                handle = int(request.get("handle"))
                return self.mailbox_close(pid, handle)
            if cmd == "mailbox_bind":
                pid = int(request.get("pid", 0))
                target = str(request.get("target", ""))
                capacity = request.get("capacity")
                capacity_int = int(capacity) if capacity is not None else None
                mode = int(request.get("mode", 0))
                return self.mailbox_bind(pid, target, capacity=capacity_int, mode=mode)
            if cmd == "mailbox_config_stdio":
                stream = str(request.get("stream", "out"))
                mode = int(request.get("mode", mbx_const.HSX_MBX_MODE_RDWR))
                update_existing = bool(request.get("update_existing", True))
                return self.mailbox_config_stdio(stream, mode, update_existing=update_existing)
            if cmd == "mailbox_send":
                pid = int(request.get("pid", 0))
                handle_value = request.get("handle")
                handle = None
                if isinstance(handle_value, int):
                    handle = handle_value
                elif isinstance(handle_value, str) and handle_value.strip():
                    try:
                        handle = int(handle_value, 0)
                    except ValueError:
                        handle = None
                data = request.get("data")
                data_hex = request.get("data_hex")
                flags = int(request.get("flags", 0))
                channel = int(request.get("channel", 0))
                target = request.get("target") if isinstance(request.get("target"), str) else None
                return self.mailbox_send(
                    pid,
                    handle,
                    data=data if isinstance(data, str) else None,
                    data_hex=data_hex if isinstance(data_hex, str) else None,
                    flags=flags,
                    channel=channel,
                    target=target,
                )
            if cmd == "mailbox_recv":
                pid = int(request.get("pid", 0))
                handle = int(request.get("handle"))
                max_len = int(request.get("max_len", 512))
                timeout = int(request.get("timeout", mbx_const.HSX_MBX_TIMEOUT_POLL))
                return self.mailbox_recv(pid, handle, max_len=max_len, timeout=timeout)
            if cmd == "mailbox_peek":
                pid = int(request.get("pid", 0))
                handle = int(request.get("handle"))
                return self.mailbox_peek(pid, handle)
            if cmd == "mailbox_tap":
                pid = int(request.get("pid", 0))
                handle = int(request.get("handle"))
                enable = bool(int(request.get("enable", 1)))
                return self.mailbox_tap(pid, handle, enable=enable)
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
    if header["version"] != HSX_VERSION:
        raise ValueError(f"Unsupported HSXE version 0x{header['version']:04X}")

    crc_input = data[: HEADER.size - 4] + data[HEADER.size :]
    calc_crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    if calc_crc != header["crc32"]:
        raise ValueError(f"CRC mismatch: file=0x{header['crc32']:08X} calc=0x{calc_crc:08X}")

    code_len = header["code_len"]
    ro_len = header["ro_len"]
    bss_size = header["bss_size"]
    entry = header["entry"]

    if code_len < 0 or ro_len < 0 or bss_size < 0:
        raise ValueError("Negative section length not permitted")
    if code_len > MAX_CODE_LEN:
        raise ValueError("Code section exceeds VM capacity")
    if ro_len > MAX_RODATA_LEN:
        raise ValueError("RODATA section exceeds VM capacity")
    if bss_size > MAX_BSS_SIZE:
        raise ValueError("BSS size exceeds VM capacity")
    if code_len % 4 != 0:
        raise ValueError("Code section must be 4-byte aligned")
    if entry % 4 != 0:
        raise ValueError("Entry address must be 4-byte aligned")

    code_start = HEADER.size
    code_end = code_start + code_len
    ro_end = code_end + ro_len

    if ro_end > len(data):
        raise ValueError(".hxe truncated: sections exceed file length")

    if entry < 0 or entry >= code_len:
        raise ValueError("Entry point outside code section")

    code = data[code_start:code_end]
    rodata = data[code_end:ro_end]

    if verbose:
        print(
            f"[HXE] entry=0x{entry:08X} code_len={code_len} ro_len={ro_len} bss={bss_size} caps=0x{header['req_caps']:08X}"
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
