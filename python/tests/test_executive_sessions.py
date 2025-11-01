import pytest

from python.execd import ExecutiveState, SessionError


class DummyVM:
    def attach(self):
        return {}

    def detach(self):
        return {}

    def info(self, pid=None):
        return {}

    def ps(self):
        return {}

    def restart(self, targets):
        return {}


def make_state():
    return ExecutiveState(DummyVM(), step_batch=1)


def test_session_open_records_pid_lock_and_warnings():
    state = make_state()
    session = state.session_open(
        client="hsxdbg",
        capabilities={"features": ["events", "watch"], "max_events": 512},
        pid_lock=3,
    )
    session_id = session["id"]
    assert session["client"] == "hsxdbg"
    assert session["pid_lock"] == 3
    # unsupported feature should be rejected with a warning
    assert "unsupported_feature:watch" in session.get("warnings", [])
    # requested max_events honoured within limits
    assert session["max_events"] == 512
    assert state.pid_locks[3] == session_id


def test_session_open_clamps_max_events_and_heartbeat():
    state = make_state()
    session = state.session_open(
        client="hsxdbg",
        capabilities={"max_events": 4096},
        pid_lock=None,
        heartbeat_s=1,
    )
    assert session["pid_lock"] is None
    warnings = session.get("warnings", [])
    assert any(w.startswith("max_events_clamped") for w in warnings)
    assert any(w.startswith("heartbeat_clamped") for w in warnings)
    assert session["heartbeat_s"] >= state.session_heartbeat_min
    assert session["max_events"] == state.session_events_max


def test_session_open_conflicting_pid_lock_raises():
    state = make_state()
    state.session_open(pid_lock=7)
    with pytest.raises(SessionError) as excinfo:
        state.session_open(pid_lock=7)
    assert "pid_locked:7" in str(excinfo.value)


def test_session_keepalive_updates_last_seen():
    state = make_state()
    payload = state.session_open(pid_lock=None)
    session_id = payload["id"]
    record = state.sessions[session_id]
    record.last_seen -= 10
    before = record.last_seen
    state.session_keepalive(session_id)
    after = state.sessions[session_id].last_seen
    assert after > before


def test_session_keepalive_unknown_session_errors():
    state = make_state()
    with pytest.raises(SessionError):
        state.session_keepalive("missing")


def test_session_timeout_releases_lock():
    state = make_state()
    payload = state.session_open(pid_lock=5, heartbeat_s=1)
    session_id = payload["id"]
    record = state.sessions[session_id]
    record.last_seen -= (record.heartbeat_s + 1)
    state._last_session_prune = 0
    state.prune_sessions()
    assert session_id not in state.sessions
    assert 5 not in state.pid_locks


def test_session_close_releases_locks_and_blocks_further_calls():
    state = make_state()
    payload = state.session_open(pid_lock=9)
    session_id = payload["id"]
    state.session_close(session_id)
    assert session_id not in state.sessions
    assert 9 not in state.pid_locks
    with pytest.raises(SessionError):
        state.session_close(session_id)


def test_ensure_pid_access_respects_owner():
    state = make_state()
    owner = state.session_open(pid_lock=11)["id"]
    observer = state.session_open(pid_lock=None)["id"]
    # owner access succeeds
    state.ensure_pid_access(11, owner)
    # observer and sessionless callers are blocked
    with pytest.raises(SessionError):
        state.ensure_pid_access(11, observer)
    with pytest.raises(SessionError):
        state.ensure_pid_access(11, None)
    # unrelated pid remains accessible
    state.ensure_pid_access(42, observer)
