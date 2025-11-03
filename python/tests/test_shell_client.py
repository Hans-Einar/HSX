import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import python.shell_client as shell_client


def test_stdio_payload_includes_pid_stream_mode(tmp_path: Path) -> None:
    payload = shell_client._build_payload("stdio", ["7", "out", "drop"], tmp_path)
    assert payload["cmd"] == "stdio_fanout"
    assert payload["pid"] == 7
    assert payload["stream"] == "out"
    assert payload["mode"] == "drop"


def test_stdio_rejects_invalid_pid() -> None:
    with pytest.raises(ValueError):
        shell_client._build_payload("stdio", ["drop"], Path.cwd())


def test_mbox_payload_optional_pid(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["3"], tmp_path)
    assert payload["cmd"] == "mailbox_snapshot"
    assert payload["_filter_pid"] == 3
    assert "_filter_namespace" not in payload


def test_mbox_allows_all_keyword(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["all"], tmp_path)
    assert payload["cmd"] == "mailbox_snapshot"
    assert "_filter_pid" not in payload
    assert "_filter_namespace" not in payload


def test_mbox_namespace_keyword(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["shared"], tmp_path)
    assert payload["_filter_namespace"] == "shared"


def test_mbox_namespace_explicit(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["ns", "App"], tmp_path)
    assert payload["_filter_namespace"] == "app"


def test_mbox_owner_keyword(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["owner", "0x10"], tmp_path)
    assert payload["_filter_pid"] == 0x10


def test_mbox_pid_assignment(tmp_path: Path) -> None:
    payload = shell_client._build_payload("mbox", ["pid=5"], tmp_path)
    assert payload["_filter_pid"] == 5


def test_mbox_invalid_namespace(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        shell_client._build_payload("mbox", ["ns", "invalid"], tmp_path)


def test_watch_list_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("watch", ["list", "5"], tmp_path)
    assert payload == {"cmd": "watch", "op": "list", "pid": 5}


def test_watch_add_payload_with_options(tmp_path: Path) -> None:
    payload = shell_client._build_payload("watch", ["add", "7", "main", "--type", "symbol", "--length", "2"], tmp_path)
    assert payload["cmd"] == "watch"
    assert payload["op"] == "add"
    assert payload["pid"] == 7
    assert payload["expr"] == "main"
    assert payload["type"] == "symbol"
    assert payload["length"] == 2


def test_watch_remove_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("watch", ["remove", "9", "3"], tmp_path)
    assert payload == {"cmd": "watch", "op": "remove", "pid": 9, "id": 3}


def test_sched_payload_pid(tmp_path: Path) -> None:
    payload = shell_client._build_payload("sched", ["7", "priority", "2"], tmp_path)
    assert payload["pid"] == 7
    assert payload["priority"] == 2


def test_sched_payload_stats(tmp_path: Path) -> None:
    payload = shell_client._build_payload("sched", ["stats", "10"], tmp_path)
    assert payload["cmd"] == "sched"
    assert payload.get("limit") == "10"
    assert "pid" not in payload


def test_load_payload_resolves_relative_path(tmp_path: Path) -> None:
    payload = shell_client._build_payload("load", ["prog.hxe"], tmp_path)
    assert Path(payload["path"]).parent == tmp_path.resolve()


def test_dbg_attach_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("dbg", ["attach", "7"], tmp_path)
    assert payload["cmd"] == "dbg"
    assert payload["op"] == "attach"
    assert payload["pid"] == 7


def test_dbg_bp_add_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("dbg", ["bp", "add", "3", "0x120"], tmp_path)
    assert payload["cmd"] == "dbg"
    assert payload["op"] == "bp"
    assert payload["action"] == "add"
    assert payload["pid"] == 3
    assert payload["addr"] == 0x120


def test_trace_toggle_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["7"], tmp_path)
    assert payload == {"cmd": "trace", "pid": 7}


def test_trace_on_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["7", "on"], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["pid"] == 7
    assert payload["mode"] == "on"


def test_trace_records_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["7", "records", "12"], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["pid"] == 7
    assert payload["op"] == "records"
    assert payload["limit"] == 12


def test_trace_config_buffer_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["config", "buffer", "256"], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["op"] == "config"
    assert payload["buffer_size"] == 256


def test_val_get_payload_resolves_identifier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = {"oid": 0x205, "name": "speed", "group_name": "telemetry"}

    def fake_resolve(identifier: str, *, host: str, port: int) -> dict:
        assert identifier == "speed"
        assert host == "example"
        assert port == 4321
        return entry

    monkeypatch.setattr(shell_client, "_resolve_value_identifier", fake_resolve)
    shell_client._LAST_VALUE_CONTEXT = {}
    payload = shell_client._build_payload(
        "val.get",
        ["speed", "--pid", "7"],
        tmp_path,
        host="example",
        port=4321,
    )
    assert payload == {"cmd": "val.get", "oid": 0x205, "pid": 7}
    assert shell_client._LAST_VALUE_CONTEXT["oid"] == 0x205


def test_val_set_payload_coerces_numeric(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = {"oid": 0x205}
    monkeypatch.setattr(shell_client, "_resolve_value_identifier", lambda identifier, *, host, port: entry)
    shell_client._VALUE_CACHE["entries"] = [{"oid": 1}]
    payload = shell_client._build_payload("val.set", ["speed", "42"], tmp_path, host="host", port=1)
    assert payload["cmd"] == "val.set"
    assert payload["oid"] == 0x205
    assert payload["value"] == pytest.approx(42.0)
    assert shell_client._VALUE_CACHE["entries"] == []


def test_val_list_payload_filters(tmp_path: Path) -> None:
    payload = shell_client._build_payload(
        "val.list",
        ["--group", "0x2", "--name", "rpm", "--oid", "0x205"],
        tmp_path,
        host="host",
        port=2,
    )
    assert payload["cmd"] == "val.list"
    assert payload["group"] == 2
    assert payload["oid"] == 0x205
    assert payload["name"] == "rpm"


def test_resolve_value_identifier_supports_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        {"oid": 0x205, "group_id": 2, "value_id": 5, "group_name": "telemetry", "name": "speed"},
        {"oid": 0x305, "group_id": 3, "value_id": 5, "group_name": "diagnostic", "name": "speed"},
    ]

    def fake_load(kind: str, host: str, port: int, *, force: bool = False) -> list[dict]:
        assert kind == "value"
        return entries

    monkeypatch.setattr(shell_client, "_load_registry_entries", fake_load)
    entry = shell_client._resolve_value_identifier("0x205", host="host", port=3)
    assert entry["oid"] == 0x205
    entry = shell_client._resolve_value_identifier("2:5", host="host", port=3)
    assert entry["oid"] == 0x205
    entry = shell_client._resolve_value_identifier("telemetry:speed", host="host", port=3)
    assert entry["oid"] == 0x205
    with pytest.raises(ValueError):
        shell_client._resolve_value_identifier("speed", host="host", port=3)


def test_value_completion_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        {"oid": 0x205, "group_id": 2, "value_id": 5, "group_name": "telemetry", "name": "speed"},
        {"oid": 0x306, "group_id": 3, "value_id": 6, "group_name": "diagnostic", "name": "temperature"},
    ]
    monkeypatch.setattr(shell_client, "_load_registry_entries", lambda kind, host, port, *, force=False: entries)
    candidates = shell_client._value_completion_candidates("host", 9)
    assert "telemetry:speed" in candidates
    assert "speed" in candidates
    assert "2:5" in candidates
    assert "0x0205" in candidates


def test_cmd_call_payload_async_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = {"oid": 0x304, "name": "reset"}

    def fake_resolve(identifier: str, *, host: str, port: int) -> dict:
        assert identifier == "reset"
        return entry

    monkeypatch.setattr(shell_client, "_resolve_command_identifier", fake_resolve)
    payload = shell_client._build_payload(
        "cmd.call",
        ["reset", "--pid", "4", "--async"],
        tmp_path,
        host="host",
        port=9998,
    )
    assert payload == {"cmd": "cmd.call", "oid": 0x304, "pid": 4, "async": True}
    assert shell_client._LAST_COMMAND_CONTEXT["async"] is True


def test_cmd_list_payload_filters(tmp_path: Path) -> None:
    payload = shell_client._build_payload(
        "cmd.list",
        ["--group", "7", "--name", "reset", "--oid", "0x304"],
        tmp_path,
        host="host",
        port=10,
    )
    assert payload["cmd"] == "cmd.list"
    assert payload["group"] == 7
    assert payload["oid"] == 0x304
    assert payload["name"] == "reset"


def test_pretty_val_get_uses_context(capsys: pytest.CaptureFixture[str]) -> None:
    shell_client._LAST_VALUE_CONTEXT = {
        "oid": 0x205,
        "entry": {
            "name": "speed",
            "group_name": "telemetry",
            "unit": "rpm",
            "min": 0.0,
            "max": 100.0,
        },
    }
    shell_client._pretty_val_get({"status": "ok", "value": {"status": 0, "value": 12.5, "f16": 0x3C00, "pid": 1}})
    out = capsys.readouterr().out
    assert "telemetry:speed" in out
    assert "12.5" in out
    assert "rpm" in out


def test_pretty_cmd_call_async_output(capsys: pytest.CaptureFixture[str]) -> None:
    shell_client._LAST_COMMAND_CONTEXT = {
        "entry": {"name": "reset", "group_name": "maintenance"},
        "oid": 0x304,
        "async": True,
    }
    shell_client._pretty_cmd_call({"status": "ok", "command": {"status": 0, "result": "queued"}})
    out = capsys.readouterr().out
    assert "reset" in out
    assert "async" in out


def test_pretty_trace_records(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "ok",
        "trace": {
            "pid": 4,
            "capacity": 256,
            "count": 2,
            "returned": 2,
            "enabled": True,
            "records": [
                {
                    "seq": 1,
                    "ts": 123.456789,
                    "pc": 0x1020,
                    "opcode": 0xDEADBEEF,
                    "flags": 0x3,
                    "steps": 12,
                    "changed_regs": ["R0", "R2"],
                },
                {
                    "seq": 2,
                    "pc": 0x1022,
                    "opcode": 0x12345678,
                    "flags": 0,
                },
            ],
        },
    }
    shell_client._pretty_trace(payload)
    output = capsys.readouterr().out
    assert "trace records" in output
    assert "seq=1" in output and "pc=0x1020" in output
    assert "changed=R0,R2" in output
    assert "seq=2" in output


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
    shell_client._pretty_sched(payload)
    output = capsys.readouterr().out
    assert "pid 1" in output
    assert "step" in output
    assert "[rotate]" in output


def test_pretty_sched_task_update(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "ok",
        "task": {"pid": 7, "priority": 5, "quantum": 3},
    }
    shell_client._pretty_sched(payload)
    output = capsys.readouterr().out
    assert "sched task update" in output
    assert "pid" in output


def test_trace_records_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["7", "records", "12"], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["pid"] == 7
    assert payload["op"] == "records"
    assert payload["limit"] == 12


def test_trace_export_payload(tmp_path: Path) -> None:
    payload = shell_client._build_payload("trace", ["7", "export", "5"], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["op"] == "export"
    assert payload["limit"] == 5


def test_trace_import_payload(tmp_path: Path) -> None:
    records = [{"seq": 1, "pid": 7, "pc": 0x100, "opcode": 0x200}]
    data = {"format": "hsx.trace/1", "records": records}
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(json.dumps(data), encoding="utf-8")
    payload = shell_client._build_payload("trace", ["7", "import", str(trace_file)], tmp_path)
    assert payload["cmd"] == "trace"
    assert payload["op"] == "import"
    assert payload["replace"] is True
    assert payload["records"] == records


def test_trace_import_append_payload(tmp_path: Path) -> None:
    records = [{"seq": 2, "pid": 7, "pc": 0x102, "opcode": 0x201}]
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(json.dumps(records), encoding="utf-8")
    payload = shell_client._build_payload("trace", ["7", "import", str(trace_file), "--append"], tmp_path)
    assert payload["op"] == "import"
    assert payload["replace"] is False


def test_pretty_trace_records_with_format(capsys: pytest.CaptureFixture[str]) -> None:
    payload = {
        "status": "ok",
        "trace": {
            "pid": 4,
            "capacity": 256,
            "count": 2,
            "returned": 2,
            "enabled": True,
            "format": "hsx.trace/1",
            "records": [
                {
                    "seq": 1,
                    "ts": 123.456789,
                    "pc": 0x1020,
                    "opcode": 0xDEADBEEF,
                    "flags": 0x3,
                    "steps": 12,
                    "changed_regs": ["R0", "R2"],
                },
                {
                    "seq": 2,
                    "pc": 0x1022,
                    "opcode": 0x12345678,
                    "flags": 0,
                },
            ],
        },
    }
    shell_client._pretty_trace(payload)
    output = capsys.readouterr().out
    assert "trace records" in output
    assert "seq=1" in output and "pc=0x1020" in output
    assert "changed=R0,R2" in output
    assert "seq=2" in output
