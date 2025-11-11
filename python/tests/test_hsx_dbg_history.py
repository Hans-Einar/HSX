"""Tests for hsx-dbg history helpers."""

from __future__ import annotations

from pathlib import Path

from hsx_dbg.history import HistoryStore


def test_history_store_loads_existing_file(tmp_path):
    path = tmp_path / "history.txt"
    path.write_text("one\ntwo\n", encoding="utf-8")
    store = HistoryStore(str(path), limit=5)
    assert store.snapshot() == ["one", "two"]
    store.append("three")
    assert store.snapshot()[-1] == "three"
    assert "three" in path.read_text(encoding="utf-8")


def test_history_store_limits_entries(tmp_path):
    path = tmp_path / "history.txt"
    store = HistoryStore(str(path), limit=3)
    for idx in range(5):
        store.append(f"cmd{idx}")
    assert store.snapshot() == ["cmd2", "cmd3", "cmd4"]
    text = path.read_text(encoding="utf-8").strip().splitlines()
    assert text == ["cmd2", "cmd3", "cmd4"]


def test_history_store_ignores_duplicate_adjacent(tmp_path):
    path = tmp_path / "history.txt"
    store = HistoryStore(str(path), limit=10)
    store.append("test")
    store.append("test")
    assert store.snapshot() == ["test"]
