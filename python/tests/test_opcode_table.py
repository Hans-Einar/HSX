from __future__ import annotations

import re
from pathlib import Path

from python import asm as hsx_asm
from python import disasm_util
from python import opcodes


def test_opcode_definitions_shared():
    """Assembler and disassembler should reference the shared opcode table."""

    assert hsx_asm.OPC is opcodes.OPCODES
    assert disasm_util.OPCODES is opcodes.OPCODES
    assert disasm_util.OPCODE_NAMES == opcodes.OPCODE_NAMES


def test_host_vm_opcode_coverage():
    """Ensure the VM executes every opcode defined by the toolchain."""

    vm_path = Path(__file__).resolve().parents[2] / "platforms" / "python" / "host_vm.py"
    vm_source = vm_path.read_text()
    pattern = re.compile(r"\b(?:if|elif)\s+op\s*==\s*0x([0-9A-Fa-f]{2})")
    vm_opcodes = {int(match.group(1), 16) for match in pattern.finditer(vm_source)}
    defined_opcodes = set(opcodes.OPCODES.values())
    assert vm_opcodes == defined_opcodes


def test_spec_opcode_table_matches_mapping():
    """Generated opcode docs must stay in sync with the canonical table."""

    doc_path = Path(__file__).resolve().parents[2] / "docs" / "MVASM_SPEC.md"
    lines = doc_path.read_text().splitlines()
    in_table = False
    doc_pairs = set()
    for line in lines:
        if line.strip() == "## Opcode Table":
            in_table = True
            continue
        if in_table:
            stripped = line.strip()
            if not stripped:
                if doc_pairs:
                    break
                continue
            if stripped.startswith("| ------") or stripped.startswith("| Opcode"):
                continue
            if stripped.startswith("| 0x"):
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                opcode_value = int(cells[0], 16)
                mnemonic = cells[1].strip("`")
                doc_pairs.add((opcode_value, mnemonic))
    defined_pairs = {(opcode, mnemonic) for mnemonic, opcode in opcodes.OPCODE_LIST}
    assert doc_pairs == defined_pairs
