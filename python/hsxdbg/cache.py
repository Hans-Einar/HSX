"""Runtime cache helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class RuntimeCache:
    registers: Dict[str, int] = field(default_factory=dict)
    memory_blocks: Dict[int, bytes] = field(default_factory=dict)
    symbols: Dict[str, Dict] = field(default_factory=dict)
    instructions: Dict[int, Dict] = field(default_factory=dict)

    def update_registers(self, regs: Dict[str, int]) -> None:
        self.registers.update(regs)

    def cache_memory(self, base: int, data: bytes) -> None:
        self.memory_blocks[base] = data

    def lookup_instruction(self, pc: int) -> Optional[Dict]:
        return self.instructions.get(pc)

    def store_instruction(self, pc: int, meta: Dict) -> None:
        self.instructions[pc] = meta
