"""Completion tests for hsx-dbg."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

try:  # pragma: no cover - optional dependency guard
    from prompt_toolkit.document import Document
except Exception:  # pragma: no cover - optional dependency guard
    pytest.skip("prompt_toolkit not available", allow_module_level=True)

from hsx_dbg.commands import build_registry
from hsx_dbg.completion import DebuggerCompleter
from hsx_dbg.context import DebuggerContext


class _StubSymbolIndex:
    def __init__(self, names: List[str]):
        self._names = names

    def complete_symbols(self, prefix: str = "") -> List[str]:
        if not prefix:
            return list(self._names)
        return [name for name in self._names if name.lower().startswith(prefix.lower())]


def _build_context() -> DebuggerContext:
    ctx = DebuggerContext()
    ctx._symbol_index = _StubSymbolIndex(["main", "loop", "memcpy"])  # type: ignore[attr-defined]
    return ctx


def test_command_completion_offers_break():
    ctx = _build_context()
    registry = build_registry()
    completer = DebuggerCompleter(ctx, registry)
    doc = Document("br", cursor_position=2)
    results = {c.text for c in completer.get_completions(doc, None)}
    assert "break" in results


def test_symbol_completion_for_break_add():
    ctx = _build_context()
    registry = build_registry()
    completer = DebuggerCompleter(ctx, registry)
    doc = Document("break add 1 ma", cursor_position=len("break add 1 ma"))
    results = {c.text for c in completer.get_completions(doc, None)}
    assert "main" in results


def test_disasm_symbol_completion_when_no_prefix():
    ctx = _build_context()
    registry = build_registry()
    completer = DebuggerCompleter(ctx, registry)
    doc = Document("disasm 1 ", cursor_position=len("disasm 1 "))
    results = {c.text for c in completer.get_completions(doc, None)}
    assert "main" in results


def test_path_completion_for_symbols(tmp_path):
    sym_file = tmp_path / "demo.sym"
    sym_file.write_text("{}", encoding="utf-8")
    ctx = _build_context()
    registry = build_registry()
    completer = DebuggerCompleter(ctx, registry)
    text = f"symbols {sym_file.as_posix()[:-1]}"
    doc = Document(text, cursor_position=len(text))
    results = {c.text for c in completer.get_completions(doc, None)}
    assert any(entry.endswith("demo.sym") for entry in results)


def test_register_completion_matches_prefix():
    ctx = _build_context()
    registry = build_registry()
    completer = DebuggerCompleter(ctx, registry)
    doc = Document("break add 1 R", cursor_position=len("break add 1 R"))
    results = {c.text for c in completer.get_completions(doc, None)}
    assert "R00" in results
