import subprocess
import sys
from pathlib import Path

from python import hld as hsx_linker
from platforms.python.host_vm import MiniVM, load_hxe


def test_cli_emit_hxo_then_link(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    asm_path = tmp_path / "prog.mvasm"
    asm_path.write_text(
        """
.text
.entry start
start:
    LDI R0, 42
    RET
""".strip() + "\n",
        encoding="utf-8",
    )

    hxo_path = tmp_path / "prog.hxo"
    cmd = [
        sys.executable,
        str(repo_root / "python" / "asm.py"),
        str(asm_path),
        "-o",
        str(hxo_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout

    hxe_path = tmp_path / "linked.hxe"
    hsx_linker.link_objects([hxo_path], hxe_path)
    header, code_bytes, rodata = load_hxe(hxe_path)

    vm = MiniVM(code_bytes, entry=header["entry"], rodata=rodata)
    while vm.running:
        vm.step()

    assert vm.regs[0] == 42
