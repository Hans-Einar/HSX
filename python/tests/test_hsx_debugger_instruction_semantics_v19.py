from __future__ import annotations

from dataclasses import replace

import opcodes

from hsx_debugger import HsxAddress, InstructionRecord
from hsx_debugger.instruction_semantics import (
    CallSemanticStatus,
    FIXED32_CALL_OPCODE,
    FIXED32_ENCODING,
    FIXED32_KNOWN_OPCODES,
    prove_call,
)
from test_hsx_debugger_stack import foundation


def _instruction(f, *, encoded_word=(0x24 << 24), byte_size=4, address=None):
    return InstructionRecord(
        "semantic-candidate",
        address or HsxAddress(f.code, 0x120),
        byte_size,
        encoded_word,
        "caller",
        None,
        f.instruction.classification,
    )


def test_fixed32_constants_and_decode_rule_match_canonical_toolchain() -> None:
    assert FIXED32_ENCODING == "hsx.fixed32/1"
    assert FIXED32_CALL_OPCODE == opcodes.OPCODES["CALL"] == 0x24
    assert FIXED32_KNOWN_OPCODES == frozenset(
        opcode for _, opcode in opcodes.OPCODE_LIST
    )
    word = (opcodes.OPCODES["CALL"] << 24) | 0x00ABCDEF
    assert ((word >> 24) & 0xFF) == FIXED32_CALL_OPCODE


def test_prove_call_accepts_only_exact_fixed32_call_opcode() -> None:
    f = foundation()
    result = prove_call(f.architecture, _instruction(f, encoded_word=(0x24 << 24) | 0x1234))
    assert result.status is CallSemanticStatus.CALL
    assert result.opcode == 0x24
    assert result.diagnostics == ()

    non_call = prove_call(f.architecture, _instruction(f, encoded_word=(0x04 << 24) | 0x1234))
    assert non_call.status is CallSemanticStatus.NOT_CALL
    assert non_call.opcode == 0x04
    assert non_call.diagnostics[0].code == "call_site_not_call"


def test_unknown_fixed32_primary_opcode_is_corrupt_not_legitimate_non_call() -> None:
    f = foundation()
    assert 0x05 not in FIXED32_KNOWN_OPCODES
    result = prove_call(f.architecture, _instruction(f, encoded_word=(0x05 << 24)))
    assert result.status is CallSemanticStatus.CORRUPT
    assert result.opcode is None
    assert result.diagnostics[0].code == "instruction_encoding_contract"


def test_prove_call_requires_encoded_word_and_exact_fixed32_call_width() -> None:
    f = foundation()
    unavailable = prove_call(f.architecture, _instruction(f, encoded_word=None))
    assert unavailable.status is CallSemanticStatus.UNAVAILABLE
    assert unavailable.opcode is None
    assert unavailable.diagnostics[0].code == "instruction_semantics_unavailable"

    wrong_width = prove_call(
        f.architecture,
        _instruction(f, encoded_word=0x2400, byte_size=2),
    )
    assert wrong_width.status is CallSemanticStatus.CORRUPT
    assert wrong_width.diagnostics[0].code == "instruction_encoding_contract"


def test_prove_call_rejects_unsupported_encoding_without_guessing_bytes() -> None:
    f = foundation()
    architecture = replace(f.architecture, instruction_encoding="future.variable/2")
    result = prove_call(architecture, _instruction(f))
    assert result.status is CallSemanticStatus.UNSUPPORTED
    assert result.opcode is None
    assert result.diagnostics[0].code == "instruction_encoding_unsupported"


def test_prove_call_rejects_non_executable_or_wrong_space_instruction_address() -> None:
    f = foundation()
    result = prove_call(
        f.architecture,
        _instruction(f, address=HsxAddress(f.data, 0x120)),
    )
    assert result.status is CallSemanticStatus.CORRUPT
    assert result.diagnostics[0].code == "instruction_encoding_contract"
