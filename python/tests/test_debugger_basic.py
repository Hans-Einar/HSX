import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM, VMController


def _assemble(lines: list[str]) -> tuple[bytes, int, bytes]:
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = hsx_asm.assemble(lines)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code_bytes, entry or 0, rodata


def _setup_controller(code: bytes, entry: int, rodata: bytes) -> tuple[VMController, MiniVM]:
    controller = VMController()
    vm = MiniVM(code, entry=entry, rodata=rodata)
    controller.vm = vm
    state = vm.snapshot_state()
    ctx = state["context"]
    ctx["pid"] = 1
    controller.task_states[1] = state
    controller.tasks[1] = {
        "pid": 1,
        "program": "<inline>",
        "state": "running",
        "priority": ctx.get("priority", 10),
        "quantum": ctx.get("time_slice_cycles", 1000),
        "pc": ctx.get("pc", entry),
        "sleep_pending": False,
        "vm_state": state,
        "trace": False,
    }
    controller.current_pid = 1
    return controller, vm


def test_debugger_breakpoint_and_step(tmp_path: Path) -> None:
    lines = [
        ".text",
        ".entry start",
        "start:",
        "LDI R0, 1",
        "BRK 3",
        "RET",
    ]
    code, entry, rodata = _assemble(lines)
    controller, _vm = _setup_controller(code, entry, rodata)

    attach = controller.debug_attach(1)
    assert attach["attached"] is True

    bp_info = controller.debug_add_breakpoint(1, entry)
    assert entry in bp_info["breakpoints"]

    cont = controller.debug_continue(1)
    debug_event = cont["result"].get("debug_event")
    assert debug_event and debug_event.get("reason") == "breakpoint"

    dbg_state = controller.debug_sessions[1]
    assert dbg_state.last_stop is not None and dbg_state.last_stop.get("pc") == entry

    step_once = controller.debug_step(1)
    step_event = step_once["result"].get("debug_event")
    assert step_event and step_event.get("reason") == "step"
    regs_snapshot = controller.debug_registers(1)
    registers = regs_snapshot["registers"]
    assert isinstance(registers, dict)
    assert registers["regs"][0] == 1

    step_brk = controller.debug_step(1)
    brk_event = step_brk["result"].get("debug_event")
    assert brk_event and brk_event.get("reason") == "brk"
    assert brk_event.get("code") == 3


def test_debugger_async_break(tmp_path: Path) -> None:
    lines = [
        ".text",
        ".entry start",
        "start:",
        "LDI R1, 1",
        "loop:",
        "ADD R0, R0, R1",
        "JMP loop",
    ]
    code, entry, rodata = _assemble(lines)
    controller, _vm = _setup_controller(code, entry, rodata)

    controller.debug_attach(1)
    controller.debug_continue(1, max_cycles=10)
    async_break = controller.debug_break(1)
    event = async_break["result"].get("debug_event")
    assert event and event.get("reason") == "async_break"
    assert controller.debug_sessions[1].last_stop == event
    assert controller.paused is True
