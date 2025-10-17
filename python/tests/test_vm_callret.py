from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM


def _assemble(lines):
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = hsx_asm.assemble(lines)
    assert not relocs, f"Unresolved relocations: {relocs}"
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code_bytes, entry, rodata


def test_call_and_ret_basic():
    asm_lines = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R5, 0",
        "    CALL foo",
        "    ADD R5, R5, R13",
        "    RET",
        "foo:",
        "    LDI R13, 1",
        "    RET",
    ]
    code, entry, rodata = _assemble(asm_lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)

    for _ in range(8):
        if not vm.running:
            break
        vm.step()

    assert vm.regs[5] == 1
    assert not vm.call_stack


def test_nested_calls_unwind():
    asm_lines = [
        ".entry main",
        ".text",
        "main:",
        "    CALL foo",
        "    RET",
        "foo:",
        "    CALL bar",
        "    RET",
        "bar:",
        "    LDI R0, 42",
        "    RET",
    ]
    code, entry, rodata = _assemble(asm_lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)

    for _ in range(12):
        if not vm.running:
            break
        vm.step()

    assert vm.regs[0] == 42
    assert not vm.call_stack


def test_call_to_earlier_label_uses_pc_relative_offset():
    asm_lines = [
        ".entry main",
        ".text",
        "prologue:",
        "    LDI R2, 7",
        "    RET",
        "main:",
        "    CALL prologue",
        "    RET",
    ]
    (
        code_words,
        entry,
        _externs,
        _imports,
        rodata,
        relocs,
        _exports,
        entry_symbol,
        local_symbols,
    ) = hsx_asm.assemble(asm_lines)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    prologue_addr = local_symbols["prologue"]["offset"]
    main_addr = local_symbols["main"]["offset"]
    assert entry_symbol == "main"
    assert entry == main_addr

    vm = MiniVM(code_bytes, entry=entry, rodata=rodata)

    # Execute CALL prologue and ensure PC jumps backwards via relative offset.
    vm.step()
    assert vm.pc & 0xFFFF == prologue_addr

    # Execute prologue body (LDI + RET) to return to the caller.
    vm.step()
    vm.step()
    assert vm.pc & 0xFFFF == (main_addr + 4)
    assert vm.regs[2] == 7
