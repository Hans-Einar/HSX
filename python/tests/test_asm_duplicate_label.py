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


def test_duplicate_label_raises_clear_error():
    with pytest.raises(ValueError, match="Duplicate label: dup"):
        assemble_source(
            """
            .text
            dup:
                RET
            dup:
                RET
            """
        )
