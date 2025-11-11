"""Symbol file helpers for hsx-dbg."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set


def _canonical_path(value: str) -> str:
    try:
        return str(Path(value)).replace("\\", "/").lower()
    except Exception:
        return str(value).replace("\\", "/").lower()


class SymbolIndex:
    """Caches line and symbol lookups from a .sym file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._line_map: Dict[str, Dict[int, List[int]]] = {}
        self._symbol_map: Dict[str, List[int]] = {}
        self._load()

    def _load(self) -> None:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        instructions = data.get("instructions") or []
        for inst in instructions:
            file_value = inst.get("file")
            line = inst.get("line")
            pc = inst.get("pc")
            if file_value is None or line is None or pc is None:
                continue
            keys: Set[str] = {
                _canonical_path(file_value),
                _canonical_path(Path(file_value).name),
            }
            directory = inst.get("directory")
            if directory:
                try:
                    full = Path(directory) / file_value
                    keys.add(_canonical_path(full))
                except Exception:
                    pass
            for key in keys:
                lines = self._line_map.setdefault(key, {})
                lines.setdefault(int(line), []).append(int(pc) & 0xFFFF)

        symbols_block = data.get("symbols") or {}
        if isinstance(symbols_block, dict):
            self._load_functions(symbols_block.get("functions") or [])
            self._load_labels(symbols_block.get("labels") or {})
            self._load_variables(symbols_block.get("variables") or [])
        elif isinstance(symbols_block, list):
            self._load_variables(symbols_block)

    def _load_functions(self, entries: Sequence[dict]) -> None:
        for entry in entries:
            name = entry.get("name")
            addr = entry.get("address")
            if not isinstance(name, str) or addr is None:
                continue
            self._symbol_map.setdefault(name, []).append(int(addr) & 0xFFFF)

    def _load_labels(self, labels: dict) -> None:
        if not isinstance(labels, dict):
            return
        for key, names in labels.items():
            try:
                addr = int(key, 0) & 0xFFFF
            except (TypeError, ValueError):
                continue
            if isinstance(names, list):
                for name in names:
                    if isinstance(name, str):
                        self._symbol_map.setdefault(name, []).append(addr)

    def _load_variables(self, entries: Sequence[dict]) -> None:
        for entry in entries:
            name = entry.get("name")
            addr = entry.get("address") or entry.get("value")
            if not isinstance(name, str) or addr is None:
                continue
            try:
                addr_int = int(addr, 0) if isinstance(addr, str) else int(addr)
            except (TypeError, ValueError):
                continue
            self._symbol_map.setdefault(name, []).append(addr_int & 0xFFFF)

    def lookup_line(self, source_path: str, line: int) -> List[int]:
        candidates: List[int] = []
        keys = {
            _canonical_path(source_path),
            _canonical_path(Path(source_path).name),
        }
        try:
            resolved = Path(source_path).resolve()
            keys.add(_canonical_path(resolved))
        except Exception:
            pass
        for key in keys:
            lines = self._line_map.get(key)
            if not lines:
                continue
            if int(line) in lines:
                candidates.extend(lines[int(line)])
        return list(dict.fromkeys(candidates))

    def lookup_symbol(self, name: str) -> List[int]:
        return list(dict.fromkeys(self._symbol_map.get(name, [])))

    def complete_symbols(self, prefix: str = "") -> List[str]:
        if not prefix:
            return sorted(self._symbol_map.keys())
        needle = prefix.lower()
        return sorted(name for name in self._symbol_map if name.lower().startswith(needle))
