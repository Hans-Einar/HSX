"""
hsxdbg - Shared debugger toolkit for HSX front-ends.

This package is the common surface for all debugger clients (CLI, VS Code,
automation).  It provides transport/session abstractions, event dispatch, a
state cache, and typed command helpers.  Each module is implemented in its
own file to keep responsibilities clear:

    transport.py  → connection & RPC framing
    session.py    → capability negotiation, PID locking
    events.py     → event dispatch utilities
    cache.py      → cached runtime state (registers, symbols, memory views)
    commands.py   → high level wrappers around executive RPCs

Implementation follows the plan captured in `main/05--Implementation/vscodeDebugStackPlan.md`.
"""

from .transport import HSXTransport, TransportConfig, TransportError  # noqa: F401
from .session import SessionManager, SessionConfig, SessionState  # noqa: F401
from .events import (  # noqa: F401
    BaseEvent,
    DebugBreakEvent,
    EventBus,
    EventSubscription,
    MailboxEvent,
    SchedulerEvent,
    StdStreamEvent,
    TaskStateEvent,
    TraceStepEvent,
    WarningEvent,
    WatchUpdateEvent,
    parse_event,
)
from .cache import RuntimeCache  # noqa: F401
from .commands import CommandClient  # noqa: F401

__all__ = [
    "HSXTransport",
    "TransportConfig",
    "TransportError",
    "SessionManager",
    "SessionConfig",
    "SessionState",
    "EventBus",
    "EventSubscription",
    "BaseEvent",
    "TraceStepEvent",
    "DebugBreakEvent",
    "SchedulerEvent",
    "TaskStateEvent",
    "MailboxEvent",
    "WatchUpdateEvent",
    "StdStreamEvent",
    "WarningEvent",
    "parse_event",
    "RuntimeCache",
    "CommandClient",
]

__version__ = "0.1.0-dev"
