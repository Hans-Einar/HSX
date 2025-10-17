import struct

from platforms.python.host_vm import MiniVM
from python.disassemble import disassemble


def _program_with_far_jump(target: int) -> bytes:
    """Build a minimal program that jumps to `target` and returns."""

    assert 0 <= target < 0x10000
    code = bytearray(target + 4)
    struct.pack_into(">I", code, 0, 0x21000000 | (target & 0x0FFF))
    # RET at the landing site so the VM halts cleanly after the jump.
    struct.pack_into(">I", code, target, 0x25000000)
    return bytes(code)


def test_jmp_immediate_zero_extends_target():
    target = 0x0A10  # >= 0x0800 exercises the sign-bit of the 12-bit field.
    program = _program_with_far_jump(target)
    vm = MiniVM(program, entry=0, rodata=b"")

    vm.step()

    assert vm.pc == target
    assert vm.running

    vm.step()

    # The RET at `target` should execute, causing the VM to stop without error.
    assert vm.pc == target
    assert not vm.running


def test_disassembler_reports_unsigned_jump_target():
    target = 0x0A10
    program = _program_with_far_jump(target)
    listing = disassemble(program)

    first = listing[0]
    assert first["mnemonic"] == "JMP"
    assert first["imm_effective"] == target
    assert first["operands"].startswith("0x00000A10")
