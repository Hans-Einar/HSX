from pathlib import Path

import pytest

from python.shell_client import _build_payload


def test_stdiofanout_payload_includes_mode_stream_pid(tmp_path: Path) -> None:
    payload = _build_payload("stdiofanout", ["drop", "out", "7"], tmp_path)
    assert payload["cmd"] == "stdio_fanout"
    assert payload["mode"] == "drop"
    assert payload["stream"] == "out"
    assert payload["pid"] == "7"


def test_stdiofanout_requires_mode() -> None:
    with pytest.raises(ValueError):
        _build_payload("stdiofanout", [], Path.cwd())


def test_load_payload_resolves_relative_path(tmp_path: Path) -> None:
    payload = _build_payload("load", ["prog.hxe"], tmp_path)
    assert Path(payload["path"]).parent == tmp_path.resolve()
