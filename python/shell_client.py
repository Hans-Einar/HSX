#!/usr/bin/env python3
import argparse
import json
import os
import socket
import sys
from pathlib import Path


def _pretty_dumpregs(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    regs = payload.get("registers", {})
    print("dumpregs:")
    print(f"  status : {payload.get('status')}  version: {payload.get('version', '?')}")
    _render_register_block(regs)


def _pretty_info(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    info = payload.get("info", {})
    print("info:")
    print(f"  status    : {payload.get('status')}  version: {payload.get('version', '?')}")
    print(f"  loaded    : {info.get('loaded')}  program: {info.get('program')}")
    print(f"  running   : {info.get('running')}  paused: {info.get('paused')}  attached: {info.get('attached')}")
    print(f"  pc        : {info.get('pc')}  sleep_pending: {info.get('sleep_pending')}")
    current = info.get('current_pid')
    if current is not None:
        print(f"  current_pid: {current}")
    context = info.get('active_context')
    if isinstance(context, dict):
        print("  active_context:")
        _render_context(context, indent="    ")
    tasks = info.get('tasks', [])
    if tasks:
        print("  tasks:")
        header = "      PID   State      Prio  Quantum  Cycles     Sleep  Program"
        print(header)
        print("      " + "-" * (len(header) - 6))
        for task in tasks:
            pid = task.get("pid")
            state = task.get("state")
            prio = task.get("priority", "-")
            quantum = task.get("quantum", "-")
            cycles = task.get("accounted_cycles", "-")
            sleep = task.get("sleep_pending", False)
            program = task.get("program", "")
            marker = "*" if current is not None and pid == current else " "
            print(f"    {marker} {pid:4}  {state:<8}  {prio:>4}  {quantum:>7}  {cycles:>8}  {str(sleep):<5}  {program}")
    selected = info.get('selected_registers')
    if isinstance(selected, dict):
        print(f"  selected_pid: {info.get('selected_pid')}")
        _render_register_block(selected, indent="  ")


def _pretty_ps(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    block = payload.get("tasks", {})
    current_pid = None
    tasks = []
    if isinstance(block, dict):
        current_pid = block.get("current_pid")
        tasks = block.get("tasks", [])
    elif isinstance(block, list):
        tasks = block
    print("ps:")
    print(f"  status    : {payload.get('status')}  version: {payload.get('version', '?')}  current_pid: {current_pid}")
    if not tasks:
        print("  (no tasks)")
        return
    header = "    PID   State      Prio  Quantum  Cycles     Sleep  Program"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for task in tasks:
        pid = task.get("pid")
        state = task.get("state")
        prio = task.get("priority", "-")
        quantum = task.get("quantum", "-")
        cycles = task.get("accounted_cycles", task.get("context", {}).get("accounted_cycles") if isinstance(task.get("context"), dict) else "-")
        sleep = task.get("sleep_pending", False)
        program = task.get("program", "")
        marker = "*" if current_pid is not None and pid == current_pid else " "
        print(f"  {marker} {pid:4}  {state:<8}  {prio:>4}  {quantum:>7}  {cycles:>8}  {str(sleep):<5}  {program}")



def _pretty_listen(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    messages = payload.get("messages", [])
    print("listen:")
    if not messages:
        print("  (no messages)")
        return
    for msg in messages:
        target = msg.get("target")
        text = msg.get("text", "")
        data_hex = msg.get("data_hex", "")
        length = msg.get("length")
        src_pid = msg.get("src_pid")
        print(f"  target={target} len={length} src={src_pid}")
        if text:
            print(f"    text: {text}")
        if data_hex and (not text or text.encode('utf-8').hex() != data_hex):
            print(f"    data_hex: {data_hex}")

PRETTY_HANDLERS = {
    'dumpregs': _pretty_dumpregs,
    'info': _pretty_info,
    'attach': _pretty_info,
    'ps': _pretty_ps,
}


def _render_context(context: dict, indent: str = "  ") -> None:
    for key in ("pid", "state", "priority", "time_slice_cycles", "accounted_cycles", "reg_base", "stack_base", "stack_limit"):
        if key in context:
            value = context[key]
            if key.endswith('_base') or key.endswith('_limit'):
                value = f"0x{int(value) & 0xFFFFFFFF:08X}"
            print(f"{indent}{key:<14}: {value}")


def _render_register_block(registers: dict, indent: str = "  ") -> None:
    print(f"{indent}pc     : 0x{registers.get('pc', 0):08X}  sp: 0x{registers.get('sp', 0):08X}")
    print(f"{indent}flags  : 0x{registers.get('flags', 0):X}    running: {registers.get('running')}")
    print(f"{indent}cycles : {registers.get('cycles', 0)}")
    context = registers.get('context', {})
    if isinstance(context, dict) and context:
        print(f"{indent}context:")
        _render_context(context, indent + "  ")
    regs_list = registers.get('regs', [])
    if regs_list:
        print(f"{indent}regs:")
        for idx, value in enumerate(regs_list):
            print(f"{indent}  R{idx:02}: 0x{value & 0xFFFFFFFF:08X}")


def send_request(host: str, port: int, payload: dict) -> dict:
    with socket.create_connection((host, port), timeout=5.0) as sock:
        with sock.makefile("w", encoding="utf-8", newline="\n") as wfile, sock.makefile("r", encoding="utf-8", newline="\n") as rfile:
            payload = dict(payload)
            payload.setdefault("version", 1)
            wfile.write(json.dumps(payload, separators=(",", ":")) + "\n")
            wfile.flush()
            line = rfile.readline()
            if not line:
                raise RuntimeError("executive closed connection")
            return json.loads(line)



def _build_payload(cmd: str, args: list[str], current_dir: Path | None = None) -> dict:
    payload_cmd = cmd
    payload: dict[str, object] = {"cmd": payload_cmd}

    if cmd in {"attach", "detach", "ps", "start_auto", "stop_auto", "shutdown", "pause", "resume", "kill", "load", "exec", "step", "listen", "send", "sched", "info", "peek", "poke", "dumpregs", "stdiofanout", "mailboxes", "mailbox_snapshot", "mailbox_open", "mailbox_close", "mailbox_bind", "mailbox_send", "mailbox_recv", "mailbox_peek", "mailbox_tap"}:
        pass

    if cmd == "info":
        if args:
            payload["pid"] = args[0]
        return payload

    if cmd == "load":
        if not args:
            raise ValueError("load requires <path>")
        base = Path(args[0])
        if current_dir is not None and not base.is_absolute():
            base = (current_dir / base)
        base = base.resolve(strict=False)
        payload["path"] = str(base)
        return payload

    if cmd == "exec":
        if not args:
            raise ValueError("exec requires <path>")
        base = Path(args[0])
        if current_dir is not None and not base.is_absolute():
            base = (current_dir / base)
        base = base.resolve(strict=False)
        payload["path"] = str(base)
        return payload

    if cmd == "step":
        if args:
            try:
                payload["cycles"] = int(args[0])
            except ValueError as exc:
                raise ValueError("step cycles must be integer") from exc
        return payload

    if cmd == "listen":
        remaining = list(args)
        for key in ("pid", "limit", "max_len"):
            if not remaining:
                break
            value = remaining[0]
            try:
                payload[key] = int(value)
            except ValueError as exc:
                raise ValueError("listen arguments must be integers") from exc
            remaining.pop(0)
        return payload

    if cmd == "send":
        if len(args) < 2:
            raise ValueError("send requires <pid> [channel] <data>")
        payload["pid"] = args[0]
        if len(args) == 2:
            payload["data"] = args[1]
        else:
            payload["channel"] = args[1]
            payload["data"] = " ".join(args[2:])
        return payload

    if cmd == "stdiofanout":
        if not args:
            raise ValueError("stdiofanout requires <mode> [stream] [pid]")
        payload["cmd"] = "stdio_fanout"
        payload["mode"] = args[0]
        if len(args) > 1:
            payload["stream"] = args[1]
        if len(args) > 2:
            payload["pid"] = args[2]
        return payload

    if cmd == "sched":
        if not args:
            raise ValueError("sched requires <pid> [priority <n>] [quantum <n>]")
        payload["pid"] = args[0]
        tokens = args[1:]
        i = 0
        while i < len(tokens):
            token = tokens[i].lower()
            if token in {"priority", "quantum"} and i + 1 < len(tokens):
                payload[token] = tokens[i + 1]
                i += 2
            else:
                raise ValueError("sched usage: sched <pid> [priority <n>] [quantum <n>]")
        return payload

    if cmd == "peek":
        if len(args) < 2:
            raise ValueError("peek requires <pid> <addr> [len]")
        payload["pid"] = args[0]
        payload["addr"] = args[1]
        if len(args) > 2:
            payload["length"] = args[2]
        return payload

    if cmd == "poke":
        if len(args) < 3:
            raise ValueError("poke requires <pid> <addr> <hexdata>")
        payload["pid"] = args[0]
        payload["addr"] = args[1]
        payload["data"] = args[2]
        return payload

    if cmd == "dumpregs":
        if not args:
            raise ValueError("dumpregs requires <pid>")
        payload["pid"] = args[0]
        return payload

    if cmd in {"pause", "resume", "kill"}:
        if not args:
            raise ValueError(f"{cmd} requires <pid>")
        payload["pid"] = args[0]
        return payload

    return payload
def cmd_loop(host: str, port: int, cwd: Path | None = None) -> None:
    current_dir = (cwd or Path.cwd()).resolve()
    print(f"Connected to executive at {host}:{port}. Type 'help' for commands.")
    while True:
        try:
            line = input('hsx> ').strip()
        except EOFError:
            print()
            break
        if not line:
            continue
        if line.lower() in {'quit', 'exit'}:
            break
        if line.lower() == 'help':
            print("Commands: info [pid], attach, detach, ps, load <path>, exec <path>, start_auto, stop_auto, step [cycles], pause <pid>, resume <pid>, kill <pid>, sched <pid> [priority <n>] [quantum <n>], restart [targets], listen [pid] [limit] [max_len], send <pid> [channel] <data>, stdiofanout <mode> [stream] [pid], peek <pid> <addr> [len], poke <pid> <addr> <hex>, dumpregs <pid>, ls [path], cd <path>, pwd, shutdown, quit")
            continue
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == 'pwd':
            print(current_dir)
            continue
        if cmd == 'ls':
            target = (current_dir / args[0]).resolve() if args else current_dir
            if not target.exists():
                print(f"ls: {target} not found")
                continue
            if target.is_file():
                print(target)
                continue
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            for entry in entries:
                name = entry.name + ('/' if entry.is_dir() else '')
                print(name)
            continue
        if cmd == 'cd':
            if not args:
                print('usage: cd <path>')
                continue
            target = (current_dir / args[0]).resolve()
            if not target.exists() or not target.is_dir():
                print(f"cd: {target} is not a directory")
                continue
            current_dir = target
            continue

        if cmd == 'restart':
            targets = [t.lower() for t in args] if args else ['vm', 'exec', 'shell']
            remote_targets = [t for t in targets if t in {'vm', 'exec'}]
            if remote_targets:
                try:
                    resp = send_request(host, port, {"cmd": "restart", "targets": remote_targets})
                except Exception as exc:
                    print(f"error: {exc}")
                else:
                    print(json.dumps(resp, indent=2, sort_keys=True))
            if 'shell' in targets:
                print('[shell] restarting')
                os.execv(sys.executable, [sys.executable] + sys.argv)
            continue

        try:
            payload = _build_payload(cmd, args, current_dir)
        except ValueError as exc:
            print(exc)
            continue

        try:
            resp = send_request(host, port, payload)
        except Exception as exc:
            print(f"error: {exc}")
            continue
        handler = PRETTY_HANDLERS.get(cmd)
        if handler:
            handler(resp)
        else:
            print(json.dumps(resp, indent=2, sort_keys=True))

def main() -> None:
    parser = argparse.ArgumentParser(description="HSX shell client")
    parser.add_argument("cmd", nargs="?", help="command to send (omit for interactive mode)")
    parser.add_argument("args", nargs="*", help="optional arguments for the command")
    parser.add_argument("--host", default="127.0.0.1", help="executive host")
    parser.add_argument("--port", type=int, default=9998, help="executive port")
    parser.add_argument("--cycles", type=int, help="cycles for step command")
    parser.add_argument("--path", help="path for load/exec commands")
    parser.add_argument("--verbose", action="store_true", help="verbose load")
    args_ns = parser.parse_args()
    if not args_ns.cmd:
        cmd_loop(args_ns.host, args_ns.port)
        return

    cmd = args_ns.cmd.lower()
    args = list(args_ns.args)

    if cmd == 'restart':
        targets = [arg.lower() for arg in args] if args else ['vm', 'exec', 'shell']
        remote_targets = [t for t in targets if t in {'vm', 'exec'}]
        if remote_targets:
            payload = {"cmd": "restart", "targets": remote_targets}
            resp = send_request(args_ns.host, args_ns.port, payload)
            print(json.dumps(resp, indent=2, sort_keys=True))
        if 'shell' in targets:
            print('[shell] restarting')
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return

    if cmd in {'load', 'exec'} and args_ns.path and not args:
        args = [args_ns.path]
    if cmd == 'step' and args_ns.cycles is not None and not args:
        args = [str(args_ns.cycles)]

    try:
        payload = _build_payload(cmd, args, Path.cwd())
    except ValueError as exc:
        parser.error(str(exc))

    if cmd == 'load' and args_ns.verbose:
        payload['verbose'] = True

    try:
        resp = send_request(args_ns.host, args_ns.port, payload)
    except Exception as exc:
        parser.error(str(exc))

    handler = PRETTY_HANDLERS.get(cmd)
    if handler:
        handler(resp)
    else:
        print(json.dumps(resp, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()









