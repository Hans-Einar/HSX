"""Simple event bus for hsxdbg."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


EventHandler = Callable[[dict], None]


@dataclass
class EventSubscription:
    categories: Optional[List[str]] = None
    pid: Optional[int] = None
    queue_size: int = 256
    handler: EventHandler = lambda event: None
    _queue: queue.Queue = field(init=False)

    def __post_init__(self) -> None:
        self._queue = queue.Queue(maxsize=self.queue_size)

    def push(self, event: dict) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Drop oldest event to keep bus responsive
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(event)

    def dispatch(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break
            self.handler(event)


class EventBus:
    """Fan-out filtered events to subscribers."""

    def __init__(self) -> None:
        self._subs: Dict[int, EventSubscription] = {}
        self._lock = threading.Lock()
        self._next_token = 1
        self._worker: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._interval = 0.01

    def subscribe(self, sub: EventSubscription) -> int:
        with self._lock:
            token = self._next_token
            self._next_token += 1
            self._subs[token] = sub
            return token

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._subs.pop(token, None)

    def publish(self, event: dict) -> None:
        with self._lock:
            subscriptions = list(self._subs.values())
        for sub in subscriptions:
            cat_ok = not sub.categories or event.get("type") in sub.categories
            pid_ok = sub.pid is None or event.get("pid") == sub.pid
            if cat_ok and pid_ok:
                sub.push(event)

    def pump(self) -> None:
        """Dispatch queued events on all subscriptions."""
        with self._lock:
            tokens = list(self._subs.keys())
        for token in tokens:
            sub = self._subs.get(token)
            if sub:
                sub.dispatch()

    def start(self, interval: float = 0.01) -> None:
        """Start background dispatcher that periodically pumps the bus."""

        self._interval = interval
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self._stop_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=0.5)
        self._worker = None

    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            self.pump()
        self.pump()
