import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platforms.python.host_vm import VMController, MiniVM


def _assemble(lines):
    from python import asm as hsx_asm

    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = hsx_asm.assemble(lines)
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code_bytes, entry, rodata


class TestStackGuard(unittest.TestCase):
    def test_stack_overflow_triggers_error(self):
        lines = [
            ".text",
            ".entry start",
            "start:",
            # push until stack underflows
            "PUSH R0",
            "JMP start",
        ]
        code, entry, rodata = _assemble(lines)
        controller = VMController()
        vm = MiniVM(code, entry=entry, rodata=rodata)
        controller.vm = vm
        state = vm.snapshot_state()
        state["context"]["pid"] = 1
        controller.task_states[1] = state
        controller.tasks[1] = {
            "pid": 1,
            "program": "<stack-overflow>",
            "state": "running",
            "priority": state["context"].get("priority", 10),
            "quantum": state["context"].get("time_slice_steps", 1),
            "pc": state["context"].get("pc", entry),
            "sleep_pending": False,
            "vm_state": state,
            "trace": False,
        }
        controller.current_pid = 1
        controller._activate_task(1)
        result = controller.step(10)
        self.assertFalse(result.get("running"))
        regs = controller.read_regs(1)
        self.assertEqual(regs["regs"][0], 0xFFFF_FF03)

