#!/usr/bin/env python3
"""Drive the HSX VS Code debug adapter without VS Code.

This script launches the adapter in a subprocess, sends the minimal DAP
handshake (initialize → launch → configurationDone), and optionally sets a
source breakpoint so you can inspect logs or crashes outside of VS Code.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_PATHS = [str(REPO_ROOT), str(REPO_ROOT / "python")]


def _send_message(proc: subprocess.Popen[str], payload: Dict) -> None:
    raw = json.dumps(payload)
    header = f"Content-Length: {len(raw)}\r\n\r\n"
    proc.stdin.write(header)
    proc.stdin.write(raw)
    proc.stdin.flush()


def _read_message(proc: subprocess.Popen[str]) -> Dict:
    header_lines = []
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError(f"DAP adapter closed stdout. stderr:\n{proc.stderr.read()}")
        line = line.rstrip("\r\n")
        if not line:
            break
        header_lines.append(line)
    length = 0
    for line in header_lines:
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
            break
    body = proc.stdout.read(length)
    return json.loads(body)


def _read_response(proc: subprocess.Popen[str], expected_command: str) -> Dict:
    while True:
        message = _read_message(proc)
        msg_type = message.get("type")
        if msg_type == "event":
            print(f"[event] {message.get('event')}: {message.get('body')}")
            continue
        if msg_type == "response" and message.get("command") == expected_command:
            return message


def _build_env() -> Dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    entries = [entry for entry in PYTHON_PATHS if entry]
    if existing:
        entries.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(entries)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Standalone DAP driver for HSX.")
    parser.add_argument("--pid", type=int, required=True, help="PID to attach")
    parser.add_argument("--host", default="127.0.0.1", help="Executive host")
    parser.add_argument("--port", type=int, default=9998, help="Executive port")
    parser.add_argument("--sym-path", required=True, help="Path to .sym file")
    parser.add_argument("--source", help="Optional source file for breakpoint")
    parser.add_argument("--line", type=int, default=0, help="Breakpoint line number")
    parser.add_argument(
        "--continue",
        dest="do_continue",
        action="store_true",
        help="Send a continue request after configuration.",
    )
    parser.add_argument("--watch", help="Optional watch expression to evaluate after stop.")
    parser.add_argument("--log-file", default=str(REPO_ROOT / "hsx-dap-debug.log"))
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args(argv)

    adapter_entry = REPO_ROOT / "python/hsx-dap.py"
    cmd = [
        args.python,
        str(adapter_entry),
        "--pid",
        str(args.pid),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--log-file",
        args.log_file,
        "--log-level",
        "DEBUG",
    ]
    print(f"[driver] launching: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(REPO_ROOT),
        env=_build_env(),
    )
    try:
        _send_message(proc, {"seq": 1, "type": "request", "command": "initialize", "arguments": {}})
        init_response = _read_response(proc, "initialize")
        print("[driver] initialize:", init_response.get("success"))

        launch_arguments = {
            "pid": args.pid,
            "host": args.host,
            "port": args.port,
            "symPath": args.sym_path,
        }
        _send_message(proc, {"seq": 2, "type": "request", "command": "launch", "arguments": launch_arguments})
        launch_response = _read_response(proc, "launch")
        print("[driver] launch:", launch_response.get("success"))

        if args.source and args.line > 0:
            bp_args = {
                "source": {"path": args.source},
                "breakpoints": [{"line": args.line}],
            }
            _send_message(proc, {"seq": 3, "type": "request", "command": "setBreakpoints", "arguments": bp_args})
            bp_response = _read_response(proc, "setBreakpoints")
            print("[driver] setBreakpoints:", bp_response.get("body"))

        _send_message(proc, {"seq": 4, "type": "request", "command": "configurationDone", "arguments": {}})
        config_response = _read_response(proc, "configurationDone")
        print("[driver] configurationDone:", config_response.get("success"))

        seq = 5
        if args.do_continue:
            _send_message(
                proc,
                {"seq": seq, "type": "request", "command": "continue", "arguments": {"threadId": args.pid}},
            )
            seq += 1
            cont_response = _read_response(proc, "continue")
            print("[driver] continue:", cont_response.get("success"))

        print("[driver] waiting for events (Ctrl+C to exit)...")
        while True:
            message = _read_message(proc)
            msg_type = message.get("type")
            if msg_type == "event":
                event_type = message.get("event")
                print(f"[event] {event_type}: {message.get('body')}")
                if event_type == "stopped" and args.watch:
                    _send_message(
                        proc,
                        {
                            "seq": seq,
                            "type": "request",
                            "command": "evaluate",
                            "arguments": {"expression": args.watch, "context": "watch"},
                        },
                    )
                    seq += 1
                    eval_response = _read_response(proc, "evaluate")
                    print("[driver] evaluate:", eval_response.get("body"))
            elif msg_type == "response":
                print(f"[response] {message.get('command')}: {message.get('success')}")
    except KeyboardInterrupt:
        print("[driver] interrupted, terminating adapter.")
        proc.terminate()
    finally:
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
