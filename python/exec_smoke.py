#!/usr/bin/env python3
"""Smoke test for HSX executive attach/run/detach workflow.

Example:
    python python/exec_smoke.py --path examples/demos/build/longrun/main.hxe
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

from executive_session import ExecutiveSession, ExecutiveSessionError


class ExecClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.session = ExecutiveSession(
            host,
            port,
            client_name="hsx-exec-smoke",
            features=["events", "stack", "disasm"],
            timeout=timeout,
        )

    def close(self) -> None:
        self.session.close()

    def request(self, payload: Dict[str, object]) -> Dict[str, object]:
        response = self.session.request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(str(response.get("error", "exec error")))
        return response

    def stack_info(self, pid: int, *, max_frames: int = 5) -> Dict[str, object]:
        try:
            info = self.session.stack_info(pid, max_frames=max_frames)
        except ExecutiveSessionError:
            return {}
        if not info:
            return {}
        return info


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
            stack_block = client.stack_info(pid)
            frames = stack_block.get("frames") if isinstance(stack_block, dict) else None
            if frames:
                lines = []
                for idx, frame in enumerate(frames[:3]):
                    func = frame.get("func_name")
                    if not func:
                        symbol = frame.get("symbol")
                        if isinstance(symbol, dict):
                            func = symbol.get("name")
                    pc = frame.get("pc")
                    if func:
                        if frame.get("func_offset"):
                            func_text = f"{func}+0x{int(frame['func_offset']):X}"
                        else:
                            func_text = func
                    elif isinstance(pc, int):
                        func_text = f"0x{pc & 0xFFFF:04X}"
                    else:
                        func_text = "<unknown>"
                    details = []
                    line_info = frame.get("line")
                    if isinstance(line_info, dict):
                        file = line_info.get("file")
                        line_no = line_info.get("line")
                        if file and line_no is not None:
                            details.append(f"{file}:{line_no}")
                        elif file:
                            details.append(file)
                    ret_pc = frame.get("return_pc")
                    if isinstance(ret_pc, int) and ret_pc:
                        details.append(f"ret=0x{ret_pc & 0xFFFF:04X}")
                    suffix = f" ({'; '.join(details)})" if details else ""
                    lines.append(f"[{idx}] {func_text}{suffix}")
                stack_line = "; ".join(lines)
                if stack_block.get("truncated"):
                    stack_line += " …"
                errors = stack_block.get("errors")
                if isinstance(errors, list) and errors:
                    stack_line += f" [errors: {', '.join(str(err) for err in errors[:2])}]"
                summary.append(f"stack -> {stack_line}")
            else:
                summary.append("stack -> unavailable")
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
