#!/usr/bin/env python3
"""Smoke test for HSX executive attach/run/detach workflow.

Example:
    python python/exec_smoke.py --path examples/demos/build/longrun/main.hxe
"""

import argparse
import json
import socket
import sys
from pathlib import Path
from typing import Dict


class ExecClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.rfile = self.sock.makefile("r", encoding="utf-8", newline="\n")
        self.wfile = self.sock.makefile("w", encoding="utf-8", newline="\n")

    def close(self) -> None:
        try:
            self.rfile.close()
        finally:
            try:
                self.wfile.close()
            finally:
                self.sock.close()

    def request(self, payload: Dict[str, object]) -> Dict[str, object]:
        payload = dict(payload)
        payload.setdefault("version", 1)
        self.wfile.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.wfile.flush()
        line = self.rfile.readline()
        if not line:
            raise RuntimeError("executive closed connection")
        resp = json.loads(line)
        if resp.get("version", 1) != 1:
            raise RuntimeError(f"unsupported protocol version {resp.get('version')}")
        if resp.get("status") != "ok":
            raise RuntimeError(str(resp.get("error", "exec error")))
        return resp


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="HSX executive smoke test")
    parser.add_argument("--host", default="127.0.0.1", help="executive host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9998, help="executive port (default 9998)")
    parser.add_argument("--path", required=True, help=".hxe image to load")
    parser.add_argument("--steps", type=int, default=1000, help="instructions to retire after loading")
    parser.add_argument("--pid", type=int, help="optional PID to single-step")
    parser.add_argument("--cycles", type=int, help=argparse.SUPPRESS)  # backwards compatibility
    args = parser.parse_args(argv)

    image_path = str(Path(args.path).resolve())

    client = ExecClient(args.host, args.port)
    summary = []
    try:
        try:
            attach_info = client.request({"cmd": "attach"}).get("info", {})
            summary.append(f"attach -> program={attach_info.get('program')}")
        except RuntimeError as exc:
            summary.append(f"attach skipped: {exc}")

        load_resp = client.request({"cmd": "load", "path": image_path})
        pid = load_resp.get("image", {}).get("pid")
        summary.append(f"load -> pid={pid}")

        ps_resp = client.request({"cmd": "ps"})
        tasks_block = ps_resp.get("tasks", {})
        if isinstance(tasks_block, dict):
            task_count = len(tasks_block.get("tasks", []))
            current_pid = tasks_block.get("current_pid")
        else:
            task_count = len(tasks_block)
            current_pid = None
        summary.append(f"ps -> {task_count} task(s), current={current_pid}")

        step_budget = args.steps
        if args.cycles is not None:
            step_budget = args.cycles
        step_payload = {"cmd": "step", "steps": step_budget}
        if args.pid is not None:
            step_payload["pid"] = args.pid
        step_resp = client.request(step_payload)
        executed = step_resp.get("result", {}).get("executed")
        summary.append(f"step -> executed={executed} instruction(s)")

        if pid is not None:
            pause_resp = client.request({"cmd": "pause", "pid": pid})
            summary.append(f"pause -> state={pause_resp.get('task', {}).get('state')}")
            resume_resp = client.request({"cmd": "resume", "pid": pid})
            summary.append(f"resume -> state={resume_resp.get('task', {}).get('state')}")
            kill_resp = client.request({"cmd": "kill", "pid": pid})
            summary.append(f"kill -> state={kill_resp.get('task', {}).get('state')}")

    finally:
        client.close()

    print("SMOKE TEST SUMMARY:")
    for line in summary:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
