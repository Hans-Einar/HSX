#!/usr/bin/env python3
import argparse
from pathlib import Path
import struct
import sys
import zlib

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
    def __init__(self, code: bytes, *, entry: int = 0, rodata: bytes = b"", trace: bool = False, svc_trace: bool = False, dev_libm: bool = False, trace_file=None):
        self.code = code
        self.regs = [0] * 16
        self.pc = entry
        self.sp = 0x8000
        self.flags = 0
        self.running = True
        self.cycles = 0
        self.mem = bytearray(64 * 1024)
        self.fs = FSStub()
        self.trace = trace
        self.svc_trace = svc_trace
        self.dev_libm = dev_libm
        self.trace_out = trace_file
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

    def step(self):
        if self.pc + 4 > len(self.code):
            print(f"[VM] PC 0x{self.pc:04X} is outside code length {len(self.code)}")
            self.running = False
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
                return
            full = be32(self.code, self.pc + 4)
            self.regs[rd] = full & 0xFFFFFFFF
            adv = 8
        else:
            print(f"[VM] Illegal opcode 0x{op:02X} at PC=0x{self.pc:04X}")
            self.running = False

        self.pc = (self.pc + adv) & 0xFFFFFFFF
        self.cycles += 1

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
    ap.add_argument("program", help=".hxe image produced by asm.py")
    ap.add_argument("--trace", action="store_true", help="print executed instructions")
    ap.add_argument("--trace-file", help="append trace output to a file")
    ap.add_argument("--svc-trace", action="store_true", help="log SVC invocations")
    ap.add_argument("--max-steps", type=int, default=None, help="safety cap on executed steps")
    ap.add_argument("--max-cycles", type=int, default=None, help="deprecated alias for --max-steps")
    ap.add_argument("--entry-symbol", help="override entry address (numeric for now)")
    ap.add_argument("--no-preload", action="store_true", help="skip demo memory preload")
    ap.add_argument("--dev-libm", action="store_true", help="enable sin_hsx/cos_hsx/exp_hsx soft handlers")
    ap.add_argument("-v", "--verbose", action="store_true", help="print header metadata")
    args = ap.parse_args()

    max_steps = args.max_steps or args.max_cycles or 100000

    trace_fp = None
    if args.trace_file:
        trace_fp = open(args.trace_file, "w", encoding="utf-8")

    header, code, rodata = load_hxe(args.program, verbose=args.verbose)

    vm = MiniVM(
        code,
        entry=header["entry"],
        rodata=rodata,
        trace=args.trace,
        svc_trace=args.svc_trace,
        dev_libm=args.dev_libm,
        trace_file=trace_fp,
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
    main()
