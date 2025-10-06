# python_toolset.md — HSX Python Toolchain

## Mål
Kjøre runden **C → LLVM IR → HSX ASM → HXE → host VM** i Python.

## Verktøy i /python
- asm.py — HSX assembler (.hxe, HSXE magic + CRC).
- host_vm.py — HSX VM (--trace/--svc-trace, CRC-sjekk).
- hsx-llc.py — NY: LLVM IR (tekst) → .mvasm (MVP).
- hld.py — NY: linker/packer (MVP pass-through).

## Eksempel
- examples/c/hello.c

## Avhengigheter
- Clang/LLVM (for IR): `clang -S -emit-llvm -O2 examples/c/hello.c -o examples/c/hello.ll`

## Pipeline
clang -S -emit-llvm -O2 examples/c/hello.c -o examples/c/hello.ll
python3 python/hsx-llc.py examples/c/hello.ll -o examples/c/hello.mvasm --trace
python3 python/asm.py    examples/c/hello.mvasm -o examples/c/hello.hxe -v
python3 platforms/python/host_vm.py examples/c/hello.hxe --trace

## ABI (MVP)
R0=ret, R1..R3 args, stack R15, f16 in low16(R*).

## Instruksjoner til Codex
- Utvid hsx-llc.py: load/store, icmp+branches, phi-moves, call/ret, _Float16.
- Utvid host_vm.py: valgfri dev-libm (sin_hsx etc. via Python math), exit-svc.
- Innfør .hxo mellomformat og utvid hld.py til ekte statisk linking.
