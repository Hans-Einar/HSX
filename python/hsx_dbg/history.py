"""Persistent command history helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional


class HistoryStore:
    """Simple file-backed history list with size limits."""

    def __init__(self, path: Optional[str], *, limit: int = 1000) -> None:
        self.limit = max(1, int(limit or 1))
        self.path = Path(path).expanduser() if path else None
        self.entries: List[str] = []
        self._dirty = False
        if self.path:
            self._load()

    def _load(self) -> None:
        if not self.path:
            return
        try:
            data = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except Exception:
            return
        lines = [line.strip() for line in data.splitlines() if line.strip()]
        self.entries = lines[-self.limit :]

    def append(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        if self.entries and self.entries[-1] == text:
            return
        self.entries.append(text)
        if len(self.entries) > self.limit:
            self.entries = self.entries[-self.limit :]
        self._dirty = True
        self._persist()

    def extend(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.append(line)

    def _persist(self) -> None:
        if not self._dirty or not self.path:
            return
        try:
            if not self.path.parent.exists():
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("\n".join(self.entries) + "\n", encoding="utf-8")
            self._dirty = False
        except Exception:
            # Swallow persistence errors; failure to write history should not break the CLI.
            self._dirty = False

    def snapshot(self) -> List[str]:
        return list(self.entries)

