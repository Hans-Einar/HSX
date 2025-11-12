"""Script execution tests for hsx-dbg CLI."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from hsx_dbg.cli import _run_script
from hsx_dbg.commands import build_registry
from hsx_dbg.context import DebuggerContext


def _ctx_registry():
    ctx = DebuggerContext()
    registry = build_registry()
    return ctx, registry


def test_script_executes_commands(tmp_path):
    ctx, registry = _ctx_registry()
    script = tmp_path / "script.txt"
    script.write_text("# comment\nalias foo break\n", encoding="utf-8")
    rc = _run_script(ctx, registry, str(script))
    assert rc == 0
    assert ctx.aliases.get("foo") == "break"


def test_script_reports_failure(tmp_path):
    ctx, registry = _ctx_registry()
    script = tmp_path / "script.txt"
    script.write_text("unknowncmd\n", encoding="utf-8")
    rc = _run_script(ctx, registry, str(script))
    assert rc != 0


def test_script_missing_file_returns_error(tmp_path):
    ctx, registry = _ctx_registry()
    missing = tmp_path / "missing.txt"
    rc = _run_script(ctx, registry, str(missing))
    assert rc != 0
