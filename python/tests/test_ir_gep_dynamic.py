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
    assert not relocs, "unexpected relocations for GEP sample"
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    vm = MiniVM(code_bytes, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    return vm


def _to_signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def test_dynamic_gep_handles_varied_element_sizes():
    cases = [
        (
            "array of i8 indexed dynamically",
            """
            @arr8 = internal global [4 x i8] zeroinitializer, align 1

            define internal void @set(i32 %idx, i8 %value) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [4 x i8], ptr @arr8, i64 0, i64 %idx64
              store i8 %value, ptr %ptr, align 1
              ret void
            }

            define internal i32 @get(i32 %idx) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [4 x i8], ptr @arr8, i64 0, i64 %idx64
              %val = load i8, ptr %ptr, align 1
              %res = sext i8 %val to i32
              ret i32 %res
            }

            define dso_local i32 @main() {
            entry:
              %idx = add i32 1, 2
              call void @set(i32 %idx, i8 -9)
              %val = call i32 @get(i32 %idx)
              ret i32 %val
            }
            """,
            -9,
            True,
        ),
        (
            "array of i16 indexed dynamically",
            """
            @arr16 = internal global [4 x i16] zeroinitializer, align 2

            define internal void @set(i32 %idx, i16 %value) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [4 x i16], ptr @arr16, i64 0, i64 %idx64
              store i16 %value, ptr %ptr, align 2
              ret void
            }

            define internal i32 @get(i32 %idx) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [4 x i16], ptr @arr16, i64 0, i64 %idx64
              %val = load i16, ptr %ptr, align 2
              %res = sext i16 %val to i32
              ret i32 %res
            }

            define dso_local i32 @main() {
            entry:
              %idx = add i32 1, 1
              call void @set(i32 %idx, i16 -32768)
              %val = call i32 @get(i32 %idx)
              ret i32 %val
            }
            """,
            -32768,
            True,
        ),
        (
            "pointer GEP scales offsets for i32 elements",
            """
            @arr32 = internal global [5 x i32] zeroinitializer, align 4

            define internal void @set32(i32 %idx, i32 %value) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [5 x i32], ptr @arr32, i64 0, i64 %idx64
              store i32 %value, ptr %ptr, align 4
              ret void
            }

            define dso_local i32 @main() {
            entry:
              call void @set32(i32 0, i32 5)
              call void @set32(i32 2, i32 11)
              call void @set32(i32 3, i32 -13)
              %mid = getelementptr inbounds [5 x i32], ptr @arr32, i64 0, i64 2
              %delta = add i32 -1, -1
              %delta64 = sext i32 %delta to i64
              %ptr = getelementptr inbounds i32, ptr %mid, i64 %delta64
              %val = load i32, ptr %ptr, align 4
              ret i32 %val
            }
            """,
            5,
            True,
        ),
        (
            "writes to separate scratch buffer honour element size",
            """
            @scratch32 = internal global [5 x i32] zeroinitializer, align 4

            define internal void @write32(i32 %idx, i32 %value) {
            entry:
              %idx64 = sext i32 %idx to i64
              %ptr = getelementptr inbounds [5 x i32], ptr @scratch32, i64 0, i64 %idx64
              store i32 %value, ptr %ptr, align 4
              ret void
            }

            define dso_local i32 @main() {
            entry:
              call void @write32(i32 4, i32 -21)
              %idx64 = sext i32 4 to i64
              %ptr = getelementptr inbounds [5 x i32], ptr @scratch32, i64 0, i64 %idx64
              %val = load i32, ptr %ptr, align 4
              ret i32 %val
            }
            """,
            -21,
            True,
        ),
    ]

    for label, ir, expected, expect_signed in cases:
        vm = _run_ir(ir)
        raw = vm.regs[0] & 0xFFFFFFFF
        value = _to_signed(raw) if expect_signed else raw
        assert value == expected, f"{label}: expected {expected}, got {value}"
