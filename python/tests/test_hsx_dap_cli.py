"""Subprocess tests that exercise the hsx DAP entrypoint with real DAP messages."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = REPO_ROOT / "python"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def _send_message(proc: subprocess.Popen[str], payload: Dict) -> None:
    raw = json.dumps(payload)
    header = f"Content-Length: {len(raw)}\r\n\r\n"
    proc.stdin.write(header)
    proc.stdin.write(raw)
    proc.stdin.flush()


def _read_message(proc: subprocess.Popen[str]) -> Dict:
    header = ""
    while True:
        line = proc.stdout.readline()
        if not line:
            stderr_output = proc.stderr.read()
            raise RuntimeError(f"DAP adapter closed stdout: {stderr_output.strip()}")
        line = line.strip()
        if not line:
            break
        header += line + "\n"
    if not header:
        raise RuntimeError("Expected Content-Length header")
    length = 0
    for entry in header.splitlines():
        if entry.lower().startswith("content-length:"):
            _, value = entry.split(":", 1)
            length = int(value.strip())
    body = proc.stdout.read(length)
    return json.loads(body)


def _read_response(proc: subprocess.Popen[str], expected: str) -> Dict:
    while True:
        message = _read_message(proc)
        if message.get("type") != "response":
            continue
        if message.get("command") == expected:
            return message


@pytest.mark.skipif(sys.platform.startswith("win"), reason="uses POSIX-only stdin/stdout piping reliably")
def test_dap_entrypoint_handles_initialize_and_launch(tmp_path: Path) -> None:
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
        "python/hsx-dap.py",
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
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )
    try:
        _send_message(proc, {"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        initialize_response = _read_response(proc, "initialize")
        assert initialize_response["success"] is True

        launch_arguments = {
            "pid": 1,
            "host": "127.0.0.1",
            "port": 9998,
            "symPath": str(sym_path),
        }
        _send_message(proc, {"seq": 2, "type": "request", "command": "launch", "arguments": launch_arguments})
        launch_response = _read_response(proc, "launch")
        assert launch_response["success"] is True

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

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
