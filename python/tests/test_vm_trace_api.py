from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM


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
    return code, entry, rodata, code_words


def test_trace_accessors_and_events():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 1",
        "    ADD R2, R1, R1",
        "    BRK 0",
    ]
    code, entry, rodata, words = _assemble(asm)
    vm = MiniVM(code, entry=entry, rodata=rodata, trace=True)

    vm.step()  # execute LDI
    assert vm.get_last_pc() == entry
    assert vm.get_last_opcode() == words[0] & 0xFFFFFFFF
    regs_snapshot = vm.get_last_regs()
    assert isinstance(regs_snapshot, list) and len(regs_snapshot) == 16
    assert regs_snapshot[1] == 1

    events = vm.consume_events()
    assert events and events[-1]["type"] == "trace_step"
    evt = events[-1]
    assert evt["pc"] == entry
    assert evt["next_pc"] == (entry + 4) & 0xFFFFFFFF
    assert evt["regs"][1] == 1

    vm.step()  # execute ADD
    assert vm.get_last_pc() == (entry + 4) & 0xFFFFFFFF
    assert vm.get_last_regs()[2] == 2


def test_accessors_without_trace_enabled():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 42",
        "    BRK 0",
    ]
    code, entry, rodata, _ = _assemble(asm)
    vm = MiniVM(code, entry=entry, rodata=rodata, trace=False)
    vm.step()
    assert vm.get_last_pc() == entry
    assert vm.get_last_regs()[1] == 42
    assert vm.consume_events() == []
