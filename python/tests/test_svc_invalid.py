import importlib.util
from pathlib import Path

from platforms.python.host_vm import HSX_ERR_ENOSYS, MiniVM


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def _assemble(lines):
    text = [line + "\n" for line in lines]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(text)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    return code_bytes, entry, rodata


def test_invalid_svc_returns_enosys():
    code, entry, rodata = _assemble(
        [
            ".text",
            ".entry start",
            "start:",
            "    SVC MOD=0xF FN=0x7F",
            "    RET",
        ]
    )

    vm = MiniVM(code, entry=entry, rodata=rodata)
    vm.step()
    assert vm.regs[0] == HSX_ERR_ENOSYS
    assert vm.running
