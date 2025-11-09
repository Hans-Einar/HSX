"""Simple persistence backend used by ValCmd for FRAM-style storage."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, Optional


class PersistenceStore:
    """In-memory persistence store with optional JSON backing and debounce support."""

    def __init__(self, path: Optional[Path | str] = None):
        self._lock = threading.Lock()
        self._data: Dict[int, int] = {}
        self._timers: Dict[int, threading.Timer] = {}
        self._path: Optional[Path] = Path(path) if path else None
        if self._path and self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                self._data = {int(key): int(value) & 0xFFFF for key, value in payload.items()}
            except (ValueError, OSError):
                # If the persistence file is corrupt we start fresh.
                self._data = {}

    # ------------------------------------------------------------------ helpers

    def _write_to_disk(self) -> None:
        if not self._path:
            return
        tmp_path = self._path.with_suffix(".tmp")
        payload = {str(key): value for key, value in self._data.items()}
        tmp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._path)

    def _commit(self, key: int, raw_value: int) -> None:
        with self._lock:
            self._data[int(key)] = int(raw_value) & 0xFFFF
            self._write_to_disk()
            timer = self._timers.pop(int(key), None)
        if timer:
            timer.cancel()

    # ----------------------------------------------------------------- public API

    def load(self, key: int) -> Optional[int]:
        with self._lock:
            return self._data.get(int(key))

    def schedule_write(self, key: int, raw_value: int, debounce_ms: int = 0) -> None:
        delay = max(0.0, debounce_ms / 1000.0)
        key = int(key)
        if delay <= 0:
            self._commit(key, raw_value)
            return
        timer = threading.Timer(delay, self._commit, args=(key, raw_value))
        timer.daemon = True
        with self._lock:
            old = self._timers.pop(key, None)
            if old:
                old.cancel()
            self._timers[key] = timer
        timer.start()

    def flush(self) -> None:
        timers = []
        with self._lock:
            timers = list(self._timers.values())
        for timer in timers:
            timer.join()

    def shutdown(self) -> None:
        with self._lock:
            timers = list(self._timers.values())
            self._timers.clear()
        for timer in timers:
            timer.cancel()
        self._write_to_disk()


__all__ = ["PersistenceStore"]
