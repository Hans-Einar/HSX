#!/usr/bin/env python3
import sys, struct

def be32(b, off):
    return (b[off]<<24)|(b[off+1]<<16)|(b[off+2]<<8)|b[off+3]

class MiniVM:
    def __init__(self, code: bytes):
        self.code = code
        self.regs = [0]*16
        self.pc = 0
        self.sp = 0x8000
        self.flags = 0
        self.running = True
        self.cycles = 0
        self.mem = bytearray(64*1024)

    def set_entry(self, entry):
        self.pc = entry

    def step(self):
        if self.pc+4 > len(self.code):
            print("PC OOB"); self.running=False; return
        ins = be32(self.code, self.pc)
        op  = (ins>>24)&0xFF
        rd  = (ins>>20)&0x0F
        rs1 = (ins>>16)&0x0F
        rs2 = (ins>>12)&0x0F
        imm = ins & 0x0FFF
        if imm & 0x800: imm -= 0x1000

        def set_flags(v):
            self.flags = 0
            if v==0: self.flags |= 1  # Z

        def ld32(addr):
            a = addr & 0xFFFF
            return (self.mem[a]<<24)|(self.mem[a+1]<<16)|(self.mem[a+2]<<8)|self.mem[a+3]

        def st32(addr, val):
            a = addr & 0xFFFF
            self.mem[a]   = (val>>24)&0xFF
            self.mem[a+1] = (val>>16)&0xFF
            self.mem[a+2] = (val>>8)&0xFF
            self.mem[a+3] = (val>>0)&0xFF

        adv = 4
        if op == 0x01: # LDI
            self.regs[rd] = imm
        elif op == 0x02: # LD
            self.regs[rd] = ld32((self.regs[rs1]+imm)&0xFFFFFFFF)
        elif op == 0x03: # ST
            st32((self.regs[rs1]+imm)&0xFFFFFFFF, self.regs[rs2])
        elif op == 0x04: # MOV
            self.regs[rd] = self.regs[rs1]
        elif op == 0x10: # ADD
            v = (self.regs[rs1] + self.regs[rs2]) & 0xFFFFFFFF
            self.regs[rd] = v; set_flags(v)
        elif op == 0x11: # SUB
            v = (self.regs[rs1] - self.regs[rs2]) & 0xFFFFFFFF
            self.regs[rd] = v; set_flags(v)
        elif op == 0x20: # CMP
            v = (self.regs[rs1] - self.regs[rs2]) & 0xFFFFFFFF; set_flags(v)
        elif op == 0x21: # JMP
            self.pc = imm & 0xFFFFFFFF; adv = 0
        elif op == 0x22: # JZ
            if (self.flags & 1): self.pc = imm & 0xFFFFFFFF; adv=0
        elif op == 0x23: # JNZ
            if not (self.flags & 1): self.pc = imm & 0xFFFFFFFF; adv=0
        elif op == 0x24: # CALL
            self.pc = imm & 0xFFFFFFFF; adv=0
        elif op == 0x25: # RET
            self.running = False
        elif op == 0x30: # SVC
            mod = (imm>>8)&0x0F; fn=imm&0xFF
            self.handle_svc(mod, fn)
        elif op == 0x60: # LDI32
            if self.pc+8 > len(self.code):
                print("LDI32 OOB"); self.running=False; return
            full = be32(self.code, self.pc+4)
            self.regs[rd] = full & 0xFFFFFFFF
            adv = 8
        else:
            print(f"Illegal opcode {op:02X}"); self.running=False

        self.pc += adv
        self.cycles += 1

    def handle_svc(self, mod, fn):
        if mod==0x0 and fn==0:
            self.regs[0] = self.cycles
        elif mod==0x1 and fn==0:
            ptr = self.regs[1] & 0xFFFF
            ln  = self.regs[2] & 0xFFFF
            s = bytes(self.mem[ptr:ptr+ln]).decode('utf-8', errors='ignore')
            print("[UART.tx]", s, end="")
            self.regs[0] = ln
        elif mod==0x4 and fn==0:
            can_id = self.regs[1] & 0x7FF
            ptr = self.regs[2] & 0xFFFF
            ln  = self.regs[3] & 0xFF
            data = self.mem[ptr:ptr+ln]
            print(f"[CAN.tx] id=0x{can_id:X} data={data.hex()}")
            self.regs[0] = 0
        else:
            print(f"[SVC] mod={mod} fn={fn} (stub)"); self.regs[0]=0

def load_exe(path):
    b = open(path,"rb").read()
    if len(b) < 36: raise ValueError("Too small")
    magic = int.from_bytes(b[0:4],"big"); ver=int.from_bytes(b[4:6],"big"); flags=int.from_bytes(b[6:8],"big"); entry=int.from_bytes(b[8:12],"big"); code_len=int.from_bytes(b[12:16],"big"); ro_len=int.from_bytes(b[16:20],"big"); bss=int.from_bytes(b[20:24],"big"); caps=int.from_bytes(b[24:28],"big"); crc=int.from_bytes(b[32:36],"big")
    if magic != 0x4D564243: raise ValueError("Bad magic")
    code = b[36:36+code_len]
    return entry, code

def main():
    if len(sys.argv)<2:
        print("Usage: host_vm.py program.exe"); return
    entry, code = load_exe(sys.argv[1])
    vm = MiniVM(code); vm.set_entry(entry)
    # preload message
    msg = b"hello from MiniVM!\n"
    vm.mem[0x0100:0x0100+len(msg)] = msg
    while vm.running and vm.cycles < 100000:
        vm.step()
    print("\nVM halted. R0..R3:", vm.regs[:4])

if __name__ == "__main__":
    main()
