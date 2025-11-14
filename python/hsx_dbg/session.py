"""Shared debugger session manager used by CLI and DAP front-ends."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from .backend import DebuggerBackend


BackendFactory = Callable[..., DebuggerBackend]


class DebuggerSession:
    """Owns a single debugger backend connection to the executive."""

    def __init__(
        self,
        *,
        client_name: str = "hsx-dbg",
        features: Optional[Iterable[str]] = None,
        keepalive_interval: int = 10,
        backend_factory: Optional[BackendFactory] = None,
    ) -> None:
        self.client_name = client_name
        self.features = list(features or ["events", "stack", "symbols", "memory", "watch", "disasm"])
        self.keepalive_interval = keepalive_interval
        self._backend_factory: BackendFactory = backend_factory or DebuggerBackend
        self.backend: Optional[DebuggerBackend] = None
        self._connection_config: Optional[Dict[str, Any]] = None

    def connect(
        self,
        host: str,
        port: int,
        pid: int,
        *,
        observer_mode: bool = False,
        keepalive_interval: Optional[int] = None,
        heartbeat_override: Optional[int] = None,
    ) -> DebuggerBackend:
        """Connect to the executive and attach to *pid*."""

        self.disconnect()
        backend = self._backend_factory(
            host=host,
            port=port,
            client_name=self.client_name,
            features=self.features,
            keepalive_enabled=True,
            keepalive_interval=self.keepalive_interval,
        )
        if keepalive_interval is not None:
            backend.configure(keepalive_interval=int(keepalive_interval))
        backend.attach(pid, observer=observer_mode, heartbeat_s=heartbeat_override)
        self.backend = backend
        self._connection_config = {
            "host": host,
            "port": port,
            "pid": pid,
            "observer_mode": observer_mode,
            "keepalive_interval": keepalive_interval,
            "heartbeat_override": heartbeat_override,
        }
        return backend

    def disconnect(self) -> None:
        backend = self.backend
        if not backend:
            return
        try:
            backend.stop_event_stream()
        except Exception:
            pass
        try:
            backend.disconnect()
        except Exception:
            pass
        self.backend = None

    @property
    def connection_config(self) -> Optional[Dict[str, Any]]:
        if self._connection_config is None:
            return None
        return dict(self._connection_config)
