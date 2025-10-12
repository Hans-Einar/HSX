from pathlib import Path

import pytest

from python.shell_client import _build_payload


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


def test_mbox_allows_all_keyword(tmp_path: Path) -> None:
    payload = _build_payload("mbox", ["all"], tmp_path)
    assert payload["cmd"] == "mailbox_snapshot"
    assert "_filter_pid" not in payload


def test_load_payload_resolves_relative_path(tmp_path: Path) -> None:
    payload = _build_payload("load", ["prog.hxe"], tmp_path)
    assert Path(payload["path"]).parent == tmp_path.resolve()
