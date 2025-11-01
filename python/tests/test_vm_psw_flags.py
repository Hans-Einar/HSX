from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM, FLAG_Z, FLAG_C, FLAG_N, FLAG_V


def _assemble(lines):
    (
        code_words,
        entry,
        _externs,
        _imports,
        rodata,
        relocs,
        _exports,
        _entry_symbol,
        _locals,
    ) = hsx_asm.assemble(lines)
    assert not relocs, f"Unresolved relocations: {relocs}"
    code = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code, entry, rodata


def _run(lines, max_steps=64):
    code, entry, rodata = _assemble(lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)
    steps = max_steps
    while vm.running and steps:
        vm.step()
        steps -= 1
    return vm


def _flag_set(vm, flag):
    return bool(vm.flags & flag)


def test_add_sets_carry_and_zero():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI32 R1, 0xFFFFFFFF",
        "    LDI R2, 1",
        "    ADD R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert _flag_set(vm, FLAG_Z)
    assert _flag_set(vm, FLAG_C)
    assert not _flag_set(vm, FLAG_N)
    assert not _flag_set(vm, FLAG_V)
    assert vm.regs[3] == 0


def test_add_sets_signed_overflow():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI32 R1, 0x40000000",
        "    LDI32 R2, 0x40000000",
        "    ADD R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert not _flag_set(vm, FLAG_Z)
    assert not _flag_set(vm, FLAG_C)
    assert _flag_set(vm, FLAG_N)
    assert _flag_set(vm, FLAG_V)
    assert vm.regs[3] == 0x80000000


def test_subtract_sets_borrow():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 3",
        "    LDI R2, 5",
        "    SUB R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert not _flag_set(vm, FLAG_C)
    assert _flag_set(vm, FLAG_N)
    assert not _flag_set(vm, FLAG_Z)
    assert not _flag_set(vm, FLAG_V)
    assert vm.regs[3] == 0xFFFFFFFE


def test_subtract_without_borrow_sets_carry():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 5",
        "    LDI R2, 3",
        "    SUB R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert _flag_set(vm, FLAG_C)
    assert not _flag_set(vm, FLAG_N)
    assert not _flag_set(vm, FLAG_Z)
    assert not _flag_set(vm, FLAG_V)
    assert vm.regs[3] == 2


def test_cmp_updates_flags_without_touching_registers():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 1",
        "    LDI R2, 1",
        "    CMP R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert _flag_set(vm, FLAG_Z)
    assert _flag_set(vm, FLAG_C)
    assert not _flag_set(vm, FLAG_N)
    assert not _flag_set(vm, FLAG_V)
    assert vm.regs[1] == 1
    assert vm.regs[2] == 1


def test_branch_observes_zero_flag():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 4",
        "    LDI R2, 4",
        "    SUB R3, R1, R2",  # zero result -> Z flag
        "    JZ taken",
        "    LDI32 R0, 0xBAD",
        "    BRK 0",
        "taken:",
        "    LDI32 R0, 0x123",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[0] == 0x123
    assert _flag_set(vm, FLAG_Z)


def test_adc_consumes_carry_in():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI32 R1, 0xFFFFFFFF",
        "    LDI R2, 1",
        "    ADD R0, R1, R2",  # sets C = 1
        "    ADC R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[3] == 1
    assert _flag_set(vm, FLAG_C)
    assert not _flag_set(vm, FLAG_Z)
    assert not _flag_set(vm, FLAG_V)


def test_adc_sets_overflow_when_carry_used():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI32 R1, 0xFFFFFFFF",
        "    LDI R2, 1",
        "    ADD R0, R1, R2",  # sets C = 1
        "    LDI32 R3, 0x7FFFFFFF",
        "    LDI R4, 0",
        "    ADC R5, R3, R4",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[5] == 0x80000000
    assert not _flag_set(vm, FLAG_C)
    assert _flag_set(vm, FLAG_V)
    assert _flag_set(vm, FLAG_N)


def test_sbc_consumes_borrow_when_carry_clear():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 0",
        "    LDI R2, 1",
        "    SUB R0, R1, R2",  # sets C = 0
        "    LDI R3, 5",
        "    LDI R4, 3",
        "    SBC R5, R3, R4",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[5] == 1
    assert _flag_set(vm, FLAG_C)
    assert not _flag_set(vm, FLAG_N)
    assert not _flag_set(vm, FLAG_V)


def test_sbc_sets_borrow_when_needed():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 4",
        "    LDI R2, 4",
        "    SUB R0, R1, R2",  # sets C = 1
        "    LDI R3, 3",
        "    LDI R4, 7",
        "    SBC R5, R3, R4",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[5] == 0xFFFFFFFC
    assert not _flag_set(vm, FLAG_C)
    assert _flag_set(vm, FLAG_N)
