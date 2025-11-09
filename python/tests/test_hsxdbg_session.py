from unittest.mock import MagicMock

from python.hsxdbg import SessionConfig, SessionManager


def test_session_reopen_closes_opens_and_resubscribes():
    transport = MagicMock()
    session = SessionManager(transport=transport, session_config=SessionConfig())
    session.state.session_id = "old-session"
    session._event_filters = {"pid": [1]}
    session._ack_thread = object()
    session._ack_interval = 0.25

    session.close = MagicMock()
    session.open = MagicMock()
    session.subscribe_events = MagicMock()

    session.reopen()

    session.close.assert_called_once()
    session.open.assert_called_once()
    session.subscribe_events.assert_called_once_with({"pid": [1]}, auto_ack=True, ack_interval=0.25)
