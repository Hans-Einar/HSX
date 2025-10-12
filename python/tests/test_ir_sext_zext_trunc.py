import importlib.util
import textwrap
from pathlib import Path

from platforms.python.host_vm import MiniVM


def _load_module(name: str, rel_path: str):
    root = Path(__file__).resolve().parents[1] / rel_path
    spec = importlib.util.spec_from_file_location(name, root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_module("hsx_llc", "hsx-llc.py")
ASM = _load_module("hsx_asm", "asm.py")


def _run_ir(ir: str) -> MiniVM:
    source = textwrap.dedent(ir).lstrip()
    asm_text = HSX_LLC.compile_ll_to_mvasm(source, trace=False)
    lines = [f"{line}\n" for line in asm_text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(lines)
    assert not relocs, "unexpected relocations for integer cast sample"
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    vm = MiniVM(code_bytes, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    return vm


def _to_signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def test_integer_ext_trunc_roundtrip():
    cases = [
        (
            "sext i8 preserves sign",
            """
            define dso_local i32 @main() {
            entry:
              %c = trunc i32 -128 to i8
              %sx = sext i8 %c to i32
              ret i32 %sx
            }
            """,
            -128,
            True,
        ),
        (
            "sext i16 preserves sign",
            """
            define dso_local i32 @main() {
            entry:
              %c = trunc i32 -32768 to i16
              %sx = sext i16 %c to i32
              ret i32 %sx
            }
            """,
            -32768,
            True,
        ),
        (
            "zext i8 clears high bits",
            """
            define dso_local i32 @main() {
            entry:
              %c = trunc i32 -128 to i8
              %zx = zext i8 %c to i32
              ret i32 %zx
            }
            """,
            128,
            False,
        ),
        (
            "zext i16 clears high bits",
            """
            define dso_local i32 @main() {
            entry:
              %c = trunc i32 -32768 to i16
              %zx = zext i16 %c to i32
              ret i32 %zx
            }
            """,
            32768,
            False,
        ),
        (
            "trunc i32->i16 retains lower bits",
            """
            define dso_local i32 @main() {
            entry:
              %tr = trunc i32 32895 to i16
              %zx = zext i16 %tr to i32
              ret i32 %zx
            }
            """,
            32895,
            False,
        ),
        (
            "trunc i32->i8 retains lower bits",
            """
            define dso_local i32 @main() {
            entry:
              %tr = trunc i32 120 to i8
              %zx = zext i8 %tr to i32
              ret i32 %zx
            }
            """,
            120,
            False,
        ),
    ]

    for label, ir, expected, expect_signed in cases:
        vm = _run_ir(ir)
        result = vm.regs[0] & 0xFFFFFFFF
        value = _to_signed(result) if expect_signed else result
        assert value == expected, f"{label}: expected {expected}, got {value}"
