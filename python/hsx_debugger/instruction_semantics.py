"""Minimal instruction-semantic proof needed by RF-004 stack reconstruction.

This module is intentionally not a disassembler.  It classifies only the evidence needed to
prove that a checked candidate address names CALL for a versioned instruction encoding.
Artifact parsing, stack walking, source mapping, runtime I/O and frontend formatting live
elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .addresses import AddressStatus, ArchitectureDescriptor, Permission
from .metadata import InstructionRecord
from .results import Diagnostic


FIXED32_ENCODING = "hsx.fixed32/1"
FIXED32_CALL_OPCODE = 0x24
# Frozen self-contained projection of the canonical stable opcode table.  This avoids making
# the debugger package depend on the build/toolchain module at runtime; conformance tests assert
# exact set equality against python/opcodes.py.
FIXED32_KNOWN_OPCODES = frozenset(
    {
        0x01, 0x02, 0x03, 0x04, 0x06, 0x07, 0x08, 0x09,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35,
        0x40, 0x41,
        0x50, 0x51, 0x52, 0x53, 0x54, 0x55,
        0x60, 0x7F,
    }
)


class CallSemanticStatus(str, Enum):
    CALL = "call"
    NOT_CALL = "not_call"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    CORRUPT = "corrupt"


@dataclass(frozen=True, slots=True)
class CallSemanticEvidence:
    status: CallSemanticStatus
    opcode: int | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if type(self.status) is not CallSemanticStatus:
            raise TypeError("status must be CallSemanticStatus")
        if self.opcode is not None and (
            type(self.opcode) is not int or not 0 <= self.opcode <= 0xFF
        ):
            raise ValueError("opcode must be an unsigned byte or None")
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        if self.status is CallSemanticStatus.CALL:
            if self.opcode != FIXED32_CALL_OPCODE or diagnostics:
                raise ValueError("CALL requires the exact fixed32 CALL opcode and no diagnostics")
        elif self.status is CallSemanticStatus.NOT_CALL:
            if (
                self.opcode is None
                or self.opcode == FIXED32_CALL_OPCODE
                or self.opcode not in FIXED32_KNOWN_OPCODES
                or not diagnostics
            ):
                raise ValueError("NOT_CALL requires a canonical non-CALL fixed32 opcode and diagnostic")
        elif self.opcode is not None or not diagnostics:
            raise ValueError("unavailable/unsupported/corrupt semantic evidence has no opcode and diagnostics")
        object.__setattr__(self, "diagnostics", diagnostics)


def _diagnostic(code: str, message: str) -> tuple[Diagnostic, ...]:
    return (Diagnostic(code, message, component="instruction_semantics"),)


def prove_call(
    architecture: ArchitectureDescriptor,
    instruction: InstructionRecord,
) -> CallSemanticEvidence:
    """Return exact CALL proof or a typed reason why caller continuation is not admissible."""

    if not isinstance(architecture, ArchitectureDescriptor):
        raise TypeError("architecture must be ArchitectureDescriptor")
    if type(instruction) is not InstructionRecord:
        raise TypeError("instruction must be exactly InstructionRecord")

    if architecture.instruction_encoding != FIXED32_ENCODING:
        return CallSemanticEvidence(
            CallSemanticStatus.UNSUPPORTED,
            None,
            _diagnostic(
                "instruction_encoding_unsupported",
                f"instruction encoding {architecture.instruction_encoding!r} has no admitted CALL proof",
            ),
        )
    if instruction.byte_size != 4:
        return CallSemanticEvidence(
            CallSemanticStatus.CORRUPT,
            None,
            _diagnostic(
                "instruction_encoding_contract",
                "hsx.fixed32/1 CALL-site InstructionRecord must have byte_size=4",
            ),
        )
    checked = architecture.validate(instruction.address, Permission.EXECUTE)
    if (
        instruction.address.space != architecture.pc_space
        or checked.status is not AddressStatus.VALID
    ):
        return CallSemanticEvidence(
            CallSemanticStatus.CORRUPT,
            None,
            _diagnostic(
                "instruction_encoding_contract",
                "instruction semantic evidence must name a valid executable pc-space address",
            ),
        )
    if instruction.encoded_word is None:
        return CallSemanticEvidence(
            CallSemanticStatus.UNAVAILABLE,
            None,
            _diagnostic(
                "instruction_semantics_unavailable",
                "InstructionRecord has no encoded_word for exact CALL proof",
            ),
        )

    opcode = (instruction.encoded_word >> 24) & 0xFF
    if opcode not in FIXED32_KNOWN_OPCODES:
        return CallSemanticEvidence(
            CallSemanticStatus.CORRUPT,
            None,
            _diagnostic(
                "instruction_encoding_contract",
                f"primary opcode 0x{opcode:02x} is outside the canonical hsx.fixed32/1 table",
            ),
        )
    if opcode == FIXED32_CALL_OPCODE:
        return CallSemanticEvidence(CallSemanticStatus.CALL, opcode, ())
    return CallSemanticEvidence(
        CallSemanticStatus.NOT_CALL,
        opcode,
        _diagnostic(
            "call_site_not_call",
            f"checked call-site instruction opcode 0x{opcode:02x} is not CALL",
        ),
    )


__all__ = [
    "CallSemanticEvidence",
    "CallSemanticStatus",
    "FIXED32_CALL_OPCODE",
    "FIXED32_ENCODING",
    "FIXED32_KNOWN_OPCODES",
    "prove_call",
]
