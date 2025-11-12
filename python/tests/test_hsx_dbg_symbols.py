"""Tests for hsx-dbg symbol index helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from hsx_dbg.symbols import SymbolIndex


def _write_sym(tmp_path: Path) -> Path:
    data = {
        "instructions": [
            {
                "pc": 0x10,
                "file": "src/demo.c",
                "directory": "/repo/examples",
                "line": 5,
                "column": 2,
                "function": "demo",
            },
            {
                "pc": 0x14,
                "file": "src/demo.c",
                "line": 6,
                "function": "demo",
            },
        ],
        "symbols": {
            "functions": [{"name": "demo", "address": 0x10}],
            "locals": [{"function": "demo", "name": "counter", "storage": "stack", "offset": -4}],
            "variables": [{"name": "global_flag", "address": 0x300}],
        },
    }
    sym_path = tmp_path / "demo.sym"
    sym_path.write_text(json.dumps(data), encoding="utf-8")
    return sym_path


def test_symbol_index_lookup_and_pc(tmp_path):
    sym = SymbolIndex(_write_sym(tmp_path))
    hits = sym.lookup("src/demo.c", 5)
    assert hits == [0x10]
    pc_meta = sym.lookup_pc(0x10)
    assert pc_meta and pc_meta["file"] == "src/demo.c" and pc_meta["line"] == 5


def test_symbol_index_locals_and_globals(tmp_path):
    sym = SymbolIndex(_write_sym(tmp_path))
    locals_list = sym.locals_for_function("demo")
    assert locals_list and locals_list[0]["name"] == "counter"
    globals_list = sym.globals_list()
    assert globals_list and globals_list[0]["name"] == "global_flag"
