import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python.shell_client import _build_payload, _pretty_sched


def test_stdio_payload_includes_pid_stream_mode(tmp_path: Path) -> None:
    payload = _build_payload("stdio", ["7", "out", "drop"], tmp_path)
    assert payload["cmd"] == "stdio_fanout"
    assert payload["pid"] == 7
    assert payload["stream"] == "out"
    assert payload["mode"] == "drop"


def test_stdio_rejects_invalid_pid() -> None:
    with pytest.raises(ValueError):
        _build_payload("stdio", ["drop"], Path.cwd())


def test_mbox_payload_optional_pid(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["3"], tmp_path)
    assert payload["cmd"] == "mailbox_snapshot"
    assert payload["_filter_pid"] == 3
    assert "_filter_namespace" not in payload


def test_mbox_allows_all_keyword(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["all"], tmp_path)
    assert payload["cmd"] == "mailbox_snapshot"
    assert "_filter_pid" not in payload
    assert "_filter_namespace" not in payload


def test_mbox_namespace_keyword(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["shared"], tmp_path)
    assert payload["_filter_namespace"] == "shared"


def test_mbox_namespace_explicit(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["ns", "App"], tmp_path)
    assert payload["_filter_namespace"] == "app"


def test_mbox_owner_keyword(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["owner", "0x10"], tmp_path)
    assert payload["_filter_pid"] == 0x10


def test_mbox_pid_assignment(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["pid=5"], tmp_path)
    assert payload["_filter_pid"] == 5


def test_mbox_invalid_namespace(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _build_payload("mbox", ["ns", "invalid"], tmp_path)


def test_watch_list_payload(tmp_path: Path) -> None:
    payload = _build_payload("watch", ["list", "5"], tmp_path)
    assert payload == {"cmd": "watch", "op": "list", "pid": 5}


def test_watch_add_payload_with_options(tmp_path: Path) -> None:
    payload = _build_payload("watch", ["add", "7", "main", "--type", "symbol", "--length", "2"], tmp_path)
    assert payload["cmd"] == "watch"
    assert payload["op"] == "add"
    assert payload["pid"] == 7
    assert payload["expr"] == "main"
    assert payload["type"] == "symbol"
    assert payload["length"] == 2


def test_watch_remove_payload(tmp_path: Path) -> None:
    payload = _build_payload("watch", ["remove", "9", "3"], tmp_path)
    assert payload == {"cmd": "watch", "op": "remove", "pid": 9, "id": 3}


def test_sched_payload_pid(tmp_path: Path) -> None:
    payload = _build_payload("sched", ["7", "priority", "2"], tmp_path)
    assert payload["pid"] == 7
    assert payload["priority"] == 2


def test_sched_payload_stats(tmp_path: Path) -> None:
    payload = _build_payload("sched", ["stats", "10"], tmp_path)
    assert payload["cmd"] == "sched"
    assert payload.get("limit") == "10"
    assert "pid" not in payload


def test_load_payload_resolves_relative_path(tmp_path: Path) -> None:
    payload = _build_payload("load", ["prog.hxe"], tmp_path)
    assert Path(payload["path"]).parent == tmp_path.resolve()


def test_dbg_attach_payload(tmp_path: Path) -> None:
    payload = _build_payload("dbg", ["attach", "7"], tmp_path)
    assert payload["cmd"] == "dbg"
    assert payload["op"] == "attach"
    assert payload["pid"] == 7


def test_dbg_bp_add_payload(tmp_path: Path) -> None:
    payload = _build_payload("dbg", ["bp", "add", "3", "0x120"], tmp_path)
    assert payload["cmd"] == "dbg"
    assert payload["op"] == "bp"
    assert payload["action"] == "add"
    assert payload["pid"] == 3
    assert payload["addr"] == 0x120


def test_pretty_sched_stats(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "ok",
        "scheduler": {
            "counters": {1: {"step": 2, "rotate": 1}},
            "trace": [
                {"event": "step", "ts": 123.0, "pid": 1},
                {"event": "rotate", "ts": 123.1, "pid": 2},
            ],
        },
    }
    _pretty_sched(payload)
    output = capsys.readouterr().out
    assert "pid 1" in output
    assert "step" in output
    assert "[rotate]" in output


def test_pretty_sched_task_update(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "ok",
        "task": {"pid": 7, "priority": 5, "quantum": 3},
    }
    _pretty_sched(payload)
    output = capsys.readouterr().out
    assert "sched task update" in output
    assert "pid" in output
