import importlib.util
import textwrap
from pathlib import Path

import pytest


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def assemble_source(src: str):
    text = textwrap.dedent(src).strip("\n")
    lines = [f"{line}\n" for line in text.splitlines()]
    return ASM.assemble(lines)


def test_forward_branch_beyond_imm12_range_fails():
    filler_lines = "\n".join("    ADD R0, R0, R0" for _ in range(1100))
    source = f"""
    .text
    .entry start
    start:
        JMP far_label
    {filler_lines}
    far_label:
        RET
    """
    with pytest.raises(ValueError, match="Immediate out of 12-bit range"):
        assemble_source(source)
