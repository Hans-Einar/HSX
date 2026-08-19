"""Subprocess tests that exercise the hsx DAP entrypoint with real DAP messages."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "python"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
PRODUCTION_WRAPPER = REPO_ROOT / "vscode-hsx" / "debugAdapter" / "hsx-dap.py"


def _send_message(proc: subprocess.Popen[bytes], payload: Dict) -> None:
    raw = json.dumps(payload).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    assert proc.stdin is not None
    proc.stdin.write(header + raw)
    proc.stdin.flush()


def _read_framed_message(reader: BinaryIO) -> Optional[Dict]:
    first_line = reader.readline()
    if not first_line:
        return None
    prefix = b"Content-Length: "
    if not first_line.startswith(prefix) or not first_line.endswith(b"\r\n"):
        raise AssertionError(f"unframed DAP stdout bytes: {first_line!r}")
    raw_length = first_line[len(prefix) : -2]
    if not raw_length.isdigit():
        raise AssertionError(f"invalid DAP Content-Length header: {first_line!r}")
    length = int(raw_length)
    while True:
        line = reader.readline()
        if not line:
            raise AssertionError("DAP stdout ended inside the header block")
        if line == b"\r\n":
            break
        if not line.endswith(b"\r\n") or b":" not in line:
            raise AssertionError(f"invalid DAP header line: {line!r}")
    body = reader.read(length)
    if len(body) != length:
        raise AssertionError(f"DAP stdout ended inside a {length}-byte payload")
    message = json.loads(body.decode("utf-8"))
    if not isinstance(message, dict):
        raise AssertionError("DAP payload must be a JSON object")
    return message


def _read_message(proc: subprocess.Popen[bytes]) -> Dict:
    assert proc.stdout is not None
    message = _read_framed_message(proc.stdout)
    if message is None:
        assert proc.stderr is not None
        stderr_output = proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DAP adapter closed stdout: {stderr_output.strip()}")
    return message


def _assert_only_framed_messages(data: bytes) -> None:
    stream = io.BytesIO(data)
    while _read_framed_message(stream) is not None:
        pass


def _read_response(proc: subprocess.Popen[bytes], expected: str) -> Dict:
    while True:
        message = _read_message(proc)
        if message.get("type") != "response":
            continue
        if message.get("command") == expected:
            return message


def test_strict_framing_rejects_non_dap_preamble() -> None:
    framed = b'Content-Length: 2\r\n\r\n{}'
    with pytest.raises(AssertionError, match="unframed DAP stdout bytes"):
        _assert_only_framed_messages(b"[hsx-dap] diagnostic\n" + framed)


@pytest.mark.parametrize("session_command", ["launch", "attach"])
def test_production_dap_entrypoint_handles_initialize_and_session(
    tmp_path: Path,
    session_command: str,
) -> None:
    log_file = tmp_path / "hsx-dap.log"
    sym_path = FIXTURE_DIR / "sample_debug.sym"
    env = os.environ.copy()
    python_paths = [str(REPO_ROOT), str(REPO_ROOT / "python")]
    existing_path = env.get("PYTHONPATH")
    if existing_path:
        python_paths.append(existing_path)
    env["PYTHONPATH"] = os.pathsep.join([entry for entry in python_paths if entry])
    env["HSX_DAP_BACKEND_FACTORY"] = "python.tests.dap_stubs:create_backend"
    env["PYTHONUNBUFFERED"] = "1"
    cmd: List[str] = [
        sys.executable,
        str(PRODUCTION_WRAPPER),
        "--pid",
        "1",
        "--host",
        "127.0.0.1",
        "--port",
        "9998",
        "--log-file",
        str(log_file),
        "--log-level",
        "DEBUG",
    ]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
        env=env,
    )
    try:
        _send_message(proc, {"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        initialize_response = _read_message(proc)
        assert initialize_response["type"] == "response"
        assert initialize_response["command"] == "initialize"
        assert initialize_response["success"] is True
        initialized_event = _read_message(proc)
        assert initialized_event["type"] == "event"
        assert initialized_event["event"] == "initialized"

        session_arguments = {
            "pid": 1,
            "host": "127.0.0.1",
            "port": 9998,
            "symPath": str(sym_path),
        }
        _send_message(
            proc,
            {"seq": 2, "type": "request", "command": session_command, "arguments": session_arguments},
        )
        session_response = _read_response(proc, session_command)
        assert session_response["success"] is True

        _send_message(
            proc,
            {
                "seq": 3,
                "type": "request",
                "command": "setBreakpoints",
                "arguments": {"source": {"path": "sample.c"}, "breakpoints": [{"line": 10}]},
            },
        )
        break_response = _read_response(proc, "setBreakpoints")
        assert break_response["success"] is True
        assert break_response["body"]["breakpoints"][0]["verified"] is True

        assert proc.stdin is not None
        proc.stdin.close()
        assert proc.wait(timeout=5) == 0
        assert proc.stdout is not None
        _assert_only_framed_messages(proc.stdout.read())

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
