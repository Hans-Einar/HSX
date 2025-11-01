#!/usr/bin/env python3
import argparse
import atexit
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
import shlex
import threading
from typing import Optional

from executive_session import ExecutiveSession

try:
    import readline  # type: ignore
except ImportError:  # pragma: no cover - platform dependent
    readline = None  # type: ignore
    try:  # pragma: no cover - optional dependency
        import pyreadline3 as readline  # type: ignore
    except ImportError:
        try:
            import pyreadline as readline  # type: ignore
        except ImportError:
            readline = None  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[1]
HELP_DIR = REPO_ROOT / "help"
SAVE_DIR = REPO_ROOT / "savefiles"
HELP_ALIASES = {
    "stdiofanout": "stdio",
    "exit": "quit",
}
COMMAND_NAMES = sorted(
    [
        "attach",
        "bp",
        "cd",
        "clock",
        "detach",
        "dbg",
        "dumpregs",
        "dmesg",
        "events",
        "exec",
        "exit",
        "help",
        "info",
        "kill",
        "mbox",
        "list",
        "listen",
        "load",
        "ls",
        "pause",
        "peek",
        "poke",
        "ps",
        "pwd",
        "quit",
        "reload",
        "restart",
        "resume",
        "save",
        "sched",
        "send",
        "shutdown",
        "stdio",
        "disasm",
        "stack",
        "symbols",
        "sym",
        "trace",
        "step",
    ]
)

_DEFAULT_EVENT_FILTER = {
    "categories": [
        "debug_break",
        "scheduler",
        "mailbox_wait",
        "mailbox_wake",
        "mailbox_timeout",
        "mailbox_error",
        "warning",
        "stdout",
        "stderr",
    ]
}

_SESSION_MANAGER: Optional[ExecutiveSession] = None
_SESSION_LOCK = threading.Lock()


def _ensure_session(host: str, port: int, *, auto_events: bool = False) -> ExecutiveSession:
    global _SESSION_MANAGER
    with _SESSION_LOCK:
        if _SESSION_MANAGER and (_SESSION_MANAGER.host != host or _SESSION_MANAGER.port != port):
            _SESSION_MANAGER.close()
            _SESSION_MANAGER = None
        if _SESSION_MANAGER is None:
            _SESSION_MANAGER = ExecutiveSession(
                host,
                port,
                client_name="hsx-shell",
                features=["events", "stack", "symbols", "disasm"],
                max_events=256,
            )
        session = _SESSION_MANAGER
    if auto_events:
        session.start_event_stream(filters=_DEFAULT_EVENT_FILTER, callback=None, ack_interval=5)
    return session


def _close_session() -> None:
    global _SESSION_MANAGER
    with _SESSION_LOCK:
        if _SESSION_MANAGER is not None:
            _SESSION_MANAGER.close()
            _SESSION_MANAGER = None


atexit.register(_close_session)

def _command_usage(name: str) -> str:
    filename = HELP_ALIASES.get(name, name)
    path = HELP_DIR / f"{filename}.txt"
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                usage = line.strip()
                if usage:
                    return usage
    except FileNotFoundError:
        pass
    return name


USAGE_BY_COMMAND = {name: _command_usage(name) for name in COMMAND_NAMES}


HISTORY_FILE = Path.home() / ".hsx_shell_history"
_HISTORY_INITIALIZED = False


def _init_history() -> None:
    global _HISTORY_INITIALIZED
    if _HISTORY_INITIALIZED or readline is None:
        return
    _HISTORY_INITIALIZED = True
    try:
        readline.set_history_length(1000)  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if HISTORY_FILE.exists():
            readline.read_history_file(str(HISTORY_FILE))  # type: ignore[attr-defined]
    except Exception:
        pass

    def _save_history() -> None:
        try:
            readline.write_history_file(str(HISTORY_FILE))  # type: ignore[attr-defined]
        except Exception:
            pass

    atexit.register(_save_history)


def _format_command_table(entries: list[str], columns: int = 3) -> str:
    if not entries:
        return ""
    column_count = min(columns, len(entries))
    rows = math.ceil(len(entries) / column_count)
    widths: list[int] = []
    for col in range(column_count):
        column_entries = [
            entries[index]
            for index in range(col * rows, min((col + 1) * rows, len(entries)))
        ]
        widths.append(max(len(text) for text in column_entries))
    lines: list[str] = []
    for row in range(rows):
        parts: list[str] = []
        for col in range(column_count):
            index = col * rows + row
            if index >= len(entries):
                continue
            text = entries[index]
            parts.append(f"{text:<{widths[col]}}")
        lines.append("  ".join(parts).rstrip())
    return "\n".join(lines)


def _print_general_help() -> None:
    print("Commands:")
    usages = [USAGE_BY_COMMAND.get(name, name) for name in COMMAND_NAMES]
    print(_format_command_table(usages))
    print("Use 'help <command>' for detailed help on a specific command.")


def _print_topic_help(topic: str) -> None:
    normalized = topic.lower()
    filename = HELP_ALIASES.get(normalized, normalized)
    path = HELP_DIR / f"{filename}.txt"
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"help: no help available for '{topic}'")
        return
    print(text.rstrip())


def _query_loaded_images(host: str, port: int) -> list[str]:
    try:
        resp = send_request(host, port, {"cmd": "ps"})
    except Exception as exc:
        raise ValueError(f"save: unable to query executive ({exc})") from exc
    block = resp.get("tasks")
    tasks: list[dict] = []
    if isinstance(block, dict):
        tasks = block.get("tasks", [])
    elif isinstance(block, list):
        tasks = block
    images: list[str] = []
    for task in tasks or []:
        program = task.get("program")
        if isinstance(program, str) and program:
            try:
                resolved = str(Path(program).resolve(strict=False))
            except Exception:
                resolved = program
            images.append(resolved)
    unique: list[str] = []
    seen: set[str] = set()
    for path in images:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _save_loaded_images(name: str, base_dir: Path, host: str, port: int) -> tuple[Path, int]:
    if not name:
        raise ValueError("save: requires bundle name")
    images = _query_loaded_images(host, port)
    if not images:
        raise ValueError("save: no .hxe images available to save")
    bundle = name if name.lower().endswith(".txt") else f"{name}.txt"
    save_dir = SAVE_DIR.resolve(strict=False)
    save_dir.mkdir(parents=True, exist_ok=True)
    target = save_dir / bundle
    with target.open("w", encoding="utf-8") as fp:
        for path in images:
            resolved = Path(path).resolve(strict=False)
            try:
                rel = resolved.relative_to(REPO_ROOT)
                fp.write(rel.as_posix() + "\n")
            except ValueError:
                fp.write(str(resolved) + "\n")
    return target, len(images)


def _resolve_load_targets(token: str, base_dir: Path) -> list[Path]:
    if not token:
        raise ValueError("load: requires <path|bundle> argument")
    raw = Path(token)
    candidate = None
    if raw.is_absolute():
        candidate = raw.resolve(strict=False)
    else:
        candidate = (base_dir / raw).resolve(strict=False)
        if not candidate.exists():
            candidate = (REPO_ROOT / raw).resolve(strict=False)
    if candidate.exists():
        return [candidate]
    if candidate.suffix == "" and (candidate.with_suffix(".hxe")).exists():
        return [candidate.with_suffix(".hxe").resolve(strict=False)]
    bundle = _resolve_saved_bundle(token, base_dir)
    if bundle:
        return bundle
    raise ValueError(f"load: no .hxe file or bundle named '{token}'")


def _resolve_saved_bundle(token: str, base_dir: Path) -> list[Path]:
    bundle_names = [f"{token}.txt", token] if not token.lower().endswith(".txt") else [token]
    search_roots = []
    base_resolved = base_dir.resolve(strict=False)
    if base_resolved not in search_roots:
        search_roots.append(base_resolved)
    save_resolved = SAVE_DIR.resolve(strict=False)
    if save_resolved not in search_roots:
        search_roots.append(save_resolved)
    candidates: list[Path] = []
    for root in search_roots:
        for name in bundle_names:
            candidate = (root / name).resolve(strict=False)
            if candidate.exists() and candidate not in candidates:
                candidates.append(candidate)
    for candidate in candidates:
        try:
            return _read_bundle_file(candidate)
        except FileNotFoundError:
            continue
    return []


def _read_bundle_file(path: Path) -> list[Path]:
    lines = path.read_text(encoding="utf-8").splitlines()
    result: list[Path] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        item = Path(line)
        if item.is_absolute():
            resolved = item.resolve(strict=False)
        else:
            resolved = None
            candidates = [
                (path.parent / item).resolve(strict=False),
                (REPO_ROOT / item).resolve(strict=False),
            ]
            for cand in candidates:
                if cand.exists():
                    resolved = cand
                    break
            if resolved is None:
                resolved = candidates[0]
        if not resolved.exists():
            raise ValueError(f"load: saved path '{line}' not found for bundle '{path.name}'")
        result.append(resolved)
    if not result:
        raise ValueError(f"load: bundle '{path.name}' does not list any .hxe files")
    return result


def _perform_load_sequence(
    host: str,
    port: int,
    paths: list[Path],
    *,
    verbose: bool = False,
    rpc_cmd: str = "load",
    symbols: Optional[str] = None,
) -> list[tuple[Path, dict]]:
    outputs: list[tuple[Path, dict]] = []
    for path in paths:
        payload: dict[str, object] = {"cmd": rpc_cmd, "path": str(path)}
        if verbose:
            payload["verbose"] = True
        if symbols and len(paths) == 1:
            payload["symbols"] = symbols
        resp = send_request(host, port, payload)
        outputs.append((path, resp))
    return outputs


def _as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
        header = "      PID   State         Prio  Quantum  Steps     Sleep     Exit  Trace  Program"
        print(header)
        print("      " + "-" * (len(header) - 6))
        for task in tasks:
            pid = task.get("pid")
            state = task.get("state")
            prio = task.get("priority", "-")
            quantum = task.get("quantum", "-")
            steps_val = task.get("accounted_steps", task.get("accounted_cycles", "-"))
            sleep = task.get("sleep_pending", False)
            exit_status = task.get("exit_status")
            exit_text = "-" if exit_status is None else str(exit_status)
            trace_text = "on" if task.get("trace") else "off"
            program = task.get("program", "")
            marker = "*" if current is not None and pid == current else " "
            print(f"    {marker} {pid:4}  {state:<12}  {prio:>4}  {quantum:>7}  {steps_val:>8}  {str(sleep):<5}  {exit_text:>8}  {trace_text:>5}  {program}")
    clock = info.get('clock')
    if isinstance(clock, dict):
        print("  clock:")
        print(f"    state       : {clock.get('state')}  mode: {clock.get('mode')}  running: {clock.get('running')}")
        print(f"    rate_hz     : {clock.get('rate_hz')}  step_size: {clock.get('step_size')}")
        print(f"    throttle    : {clock.get('throttled')} ({clock.get('throttle_reason')})  last_wait_s: {clock.get('last_wait_s')}")
        print(f"    auto        : steps={clock.get('auto_steps')}  total={clock.get('auto_total_steps')}")
        print(f"    manual      : steps={clock.get('manual_steps')}  total={clock.get('manual_total_steps')}")


def _pretty_bp(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    pid = payload.get("pid")
    breakpoints = payload.get("breakpoints", [])
    print(f"breakpoints for pid {pid}:")
    if not breakpoints:
        print("  (none)")
        return
    for addr in breakpoints:
        try:
            addr_int = int(addr)
        except (TypeError, ValueError):
            print(f"  {addr}")
        else:
            print(f"  0x{addr_int:04X} ({addr_int})")


def _pretty_events(events: list[dict]) -> None:
    for event in events:
        seq = event.get("seq", "-")
        etype = event.get("type", "?")
        pid = event.get("pid")
        ts_value = event.get("ts")
        if isinstance(ts_value, (int, float)):
            timestamp = datetime.fromtimestamp(ts_value).strftime("%H:%M:%S")
        else:
            timestamp = "?"
        data = event.get("data", {})
        if isinstance(data, dict):
            data_items = ", ".join(f"{k}={data[k]}" for k in sorted(data))
        else:
            data_items = str(data)
        pid_text = "None" if pid is None else str(pid)
        print(f"[{seq:>6}] {timestamp}  {etype:<16} pid={pid_text:<5}  {data_items}")


def _pretty_sym(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if "symbols" in payload:
        info = payload["symbols"]
        if not info or not info.get("loaded"):
            print(f"symbols for pid {info.get('pid', '?')}: (not loaded)")
            return
        print(f"symbols for pid {info.get('pid', '?')}:")
        print(f"  path : {info.get('path')}")
        print(f"  count: {info.get('count')}")
        return
    if "symbol" in payload:
        symbol = payload.get("symbol")
        if not symbol:
            print("symbol: <not found>")
            return
        print("symbol:")
        for key in ("name", "address", "offset", "size", "type", "file", "line"):
            if key in symbol and symbol[key] is not None:
                value = symbol[key]
                if key in {"address", "offset", "size"}:
                    try:
                        value_int = int(value)
                        value = f"0x{value_int:X} ({value_int})"
                    except (TypeError, ValueError):
                        pass
                print(f"  {key:<7}: {value}")
        return
    if "line" in payload:
        line = payload.get("line")
        if not line:
            print("line: <not found>")
            return
        print("line mapping:")
        print(f"  file : {line.get('file')}")
        print(f"  line : {line.get('line')}")
        addr = line.get('address')
        if isinstance(addr, int):
            print(f"  addr : 0x{addr:X} ({addr})")
        return
    print(json.dumps(payload, indent=2, sort_keys=True))


def _pretty_symbols(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    block = payload.get("symbols")
    if not isinstance(block, dict):
        print("symbols: <no data>")
        return
    pid = block.get("pid", "?")
    sym_type = block.get("type") or "all"
    total = block.get("count", 0)
    try:
        offset_value = int(block.get("offset", 0))
    except (TypeError, ValueError):
        offset_value = block.get("offset", 0)
    limit = block.get("limit")
    limit_text = "∞" if limit is None else str(limit)
    print(f"symbols pid={pid} type={sym_type} count={total} offset={offset_value} limit={limit_text}")
    entries = block.get("symbols") or []
    if not entries:
        print("  <no entries>")
        return
    for item in entries:
        name = item.get("name", "<unnamed>")
        address = item.get("address")
        addr_text = "<unknown>"
        if isinstance(address, int):
            addr_text = f"0x{address:08X}"
        elif isinstance(address, str):
            try:
                addr_text = f"0x{int(address, 0):08X}"
            except ValueError:
                addr_text = address
        size = item.get("size")
        try:
            size_value = int(size) if size is not None else None
        except (TypeError, ValueError):
            size_value = None
        size_text = "-" if size_value is None else str(size_value)
        kind = item.get("type", "-")
        file = item.get("file")
        line = item.get("line")
        details = []
        if file:
            details.append(str(file))
        if line is not None:
            details.append(f"line {line}")
        suffix = f" ({', '.join(details)})" if details else ""
        print(f"  {addr_text}  {size_text:>4}  {kind:<9}  {name}{suffix}")


def _pretty_stack(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    stack = payload.get("stack", {})
    frames = []
    truncated = False
    errors = []
    stack_base = None
    stack_limit = None
    stack_low = None
    stack_high = None
    initial_sp = None
    initial_fp = None
    if isinstance(stack, dict):
        frames = stack.get("frames") or []
        truncated = bool(stack.get("truncated"))
        errors = stack.get("errors") or []
        stack_base = stack.get("stack_base")
        stack_limit = stack.get("stack_limit")
        stack_low = stack.get("stack_low")
        stack_high = stack.get("stack_high")
        initial_sp = stack.get("initial_sp")
        initial_fp = stack.get("initial_fp")
    print("stack:")
    if stack_base is not None or stack_limit is not None:
        base_text = f"0x{int(stack_base) & 0xFFFFFFFF:08X}" if stack_base is not None else "-"
        limit_text = f"0x{int(stack_limit) & 0xFFFFFFFF:08X}" if stack_limit is not None else "-"
        low_text = f"0x{int(stack_low) & 0xFFFFFFFF:08X}" if stack_low is not None else "-"
        high_text = f"0x{int(stack_high) & 0xFFFFFFFF:08X}" if stack_high is not None else "-"
        print(f"  stack_base : {base_text}  stack_limit: {limit_text}")
        print(f"  stack_low  : {low_text}  stack_high : {high_text}")
    if initial_sp is not None or initial_fp is not None:
        sp_text = f"0x{int(initial_sp) & 0xFFFFFFFF:08X}" if initial_sp is not None else "-"
        fp_text = f"0x{int(initial_fp) & 0xFFFFFFFF:08X}" if initial_fp is not None else "-"
        print(f"  initial_sp : {sp_text}  initial_fp : {fp_text}")
    if not frames:
        print("  (no frames)")
    for idx, frame in enumerate(frames):
        frame_idx = frame.get("index", idx)
        pc = frame.get("pc", 0) or 0
        sp = frame.get("sp")
        fp = frame.get("fp")
        line = f"[{frame_idx:02}] pc=0x{pc:08X}"
        if sp is not None:
            line += f" sp=0x{int(sp) & 0xFFFFFFFF:08X}"
        if fp is not None:
            line += f" fp=0x{int(fp) & 0xFFFFFFFF:08X}"
        symbol = frame.get("symbol")
        if isinstance(symbol, dict):
            name = symbol.get("name")
            offset = symbol.get("offset")
            if name:
                if offset:
                    try:
                        off_int = int(offset)
                        line += f" {name}+0x{off_int:X}"
                    except (TypeError, ValueError):
                        line += f" {name}"
                else:
                    line += f" {name}"
        print(line)
        line_info = frame.get("line")
        if isinstance(line_info, dict):
            src = line_info.get("file")
            lineno = line_info.get("line")
            if src or lineno is not None:
                print(f"       {src or '<unknown>'}:{lineno}")
        ret_pc = frame.get("return_pc")
        if isinstance(ret_pc, int):
            print(f"       return -> 0x{ret_pc & 0xFFFFFFFF:08X}")
    if truncated:
        print("  ... truncated ...")
    if errors:
        print("  errors:")
        for item in errors:
            print(f"    - {item}")


def _pretty_disasm(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    block = payload.get("disasm", {})
    if not isinstance(block, dict):
        print("disasm: <no data>")
        return
    print("disasm:")
    pid = block.get("pid")
    base = block.get("address")
    count = block.get("count")
    requested = block.get("requested")
    mode = block.get("mode")
    cached = block.get("cached")
    truncated = block.get("truncated")
    summary = []
    if pid is not None:
        summary.append(f"pid={pid}")
    if base is not None:
        summary.append(f"base=0x{int(base) & 0xFFFFFFFF:08X}")
    if count is not None:
        summary.append(f"count={count}")
    if requested is not None and requested != count:
        summary.append(f"requested={requested}")
    if mode:
        summary.append(f"mode={mode}")
    if cached:
        summary.append("cached")
    if truncated:
        summary.append("truncated")
    if summary:
        print(f"  {'; '.join(summary)}")
    instructions = block.get("instructions") or []
    if not instructions:
        print("  (no instructions)")
        return
    for inst in instructions:
        idx = inst.get("index")
        idx_text = f"{idx:02}" if isinstance(idx, int) else "??"
        pc = inst.get("pc")
        if isinstance(pc, int):
            heading = f"  [{idx_text}] 0x{pc & 0xFFFFFFFF:08X}:"
        else:
            heading = f"  [{idx_text}] ?:"
        mnemonic = inst.get("mnemonic", "")
        if mnemonic:
            heading += f" {mnemonic}"
        operands = inst.get("operands")
        if operands:
            heading += f" {operands}"
        label = inst.get("label")
        if not label:
            symbol_block = inst.get("symbol")
            if isinstance(symbol_block, dict):
                label = symbol_block.get("name")
        if label:
            heading += f"    ; {label}"
        print(heading)
        details = []
        target = inst.get("target")
        if isinstance(target, int):
            detail = f"target=0x{target & 0xFFFFFFFF:08X}"
            target_symbol = inst.get("target_symbol")
            if isinstance(target_symbol, dict) and target_symbol.get("name"):
                detail += f" ({target_symbol['name']})"
            details.append(detail)
        line_info = inst.get("line")
        if isinstance(line_info, dict):
            src = line_info.get("file") or "<unknown>"
            lineno = line_info.get("line")
            if lineno is not None:
                details.append(f"src={src}:{lineno}")
            else:
                details.append(f"src={src}")
        if details:
            print(f"       {'; '.join(details)}")


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
    header = "    PID   State         Prio  Quantum  Steps     Sleep     Exit  Trace  Program"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for task in tasks:
        pid = task.get("pid")
        state = task.get("state")
        prio = task.get("priority", "-")
        quantum = task.get("quantum", "-")
        steps_val = task.get("accounted_steps", task.get("context", {}).get("accounted_steps") if isinstance(task.get("context"), dict) else "-")
        sleep = task.get("sleep_pending", False)
        exit_status = task.get("exit_status")
        exit_text = "-" if exit_status is None else str(exit_status)
        trace_text = "on" if task.get("trace") else "off"
        program = task.get("program", "")
        marker = "*" if current_pid is not None and pid == current_pid else " "
        print(f"  {marker} {pid:4}  {state:<12}  {prio:>4}  {quantum:>7}  {steps_val:>8}  {str(sleep):<5}  {exit_text:>8}  {trace_text:>5}  {program}")

def _pretty_clock(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    clock = payload.get("clock", {})
    print("clock:")
    if not isinstance(clock, dict) or not clock:
        print("  (no clock data)")
    else:
        state = clock.get("state")
        running = clock.get("running")
        mode = clock.get("mode")
        throttled = clock.get("throttled")
        throttle_reason = clock.get("throttle_reason")
        last_wait = clock.get("last_wait_s")
        rate_hz = clock.get("rate_hz")
        step_size = clock.get("step_size")
        auto_steps = clock.get("auto_steps")
        auto_total = clock.get("auto_total_steps")
        manual_steps = clock.get("manual_steps")
        manual_total = clock.get("manual_total_steps")
        print(f"  state       : {state}  mode: {mode}  running: {running}")
        print(f"  rate_hz     : {rate_hz}  step_size: {step_size}")
        print(f"  throttle    : {throttled} ({throttle_reason})  last_wait_s: {last_wait}")
        print(f"  auto        : steps={auto_steps}  total={auto_total}")
        print(f"  manual      : steps={manual_steps}  total={manual_total}")
    result = payload.get("result")
    if isinstance(result, dict):
        executed = result.get("executed")
        paused = result.get("paused")
        running = result.get("running")
        print("  last_step:")
        print(f"    executed : {executed}")
        print(f"    running  : {running}  paused: {paused}")
        if "steps" in result:
            print(f"    steps    : {result.get('steps')}")
        for key in ("current_pid", "sleep_pending"):
            if key in result:
                print(f"    {key:<10}: {result.get(key)}")


def _pretty_trace(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    info = payload.get("trace", {})
    print("trace:")
    print(f"  pid     : {info.get('pid')}")
    print(f"  enabled : {info.get('enabled')}")


def _pretty_listen(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    messages = payload.get("messages", []) or []
    if not messages:
        print("(no messages)")
        return
    wrote_any = False
    for msg in messages:
        text = msg.get("text")
        data_hex = msg.get("data_hex")
        if isinstance(text, str):
            sys.stdout.write(text)
            wrote_any = True
        elif isinstance(data_hex, str) and data_hex:
            try:
                data_bytes = bytes.fromhex(data_hex)
            except ValueError:
                sys.stdout.write(f"<invalid data_hex:{data_hex}>")
            else:
                sys.stdout.buffer.write(data_bytes)
                wrote_any = True
        else:
            # No textual payload; fall back to printing structured entry.
            sys.stdout.write(json.dumps(msg, sort_keys=True) + "\n")
            wrote_any = True
    if wrote_any:
        sys.stdout.flush()
    else:
        print("(no message payload)")


def _pretty_send(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    target = payload.get("target")
    length = payload.get("length")
    if length is None:
        data_hex = payload.get("data_hex")
        if isinstance(data_hex, str):
            length = len(data_hex) // 2
        else:
            data = payload.get("data")
            if isinstance(data, str):
                length = len(data.encode("utf-8"))
    length_text = str(length) if length is not None else "?"
    pid_text = None
    stdin_label = None
    if isinstance(target, str):
        parts = target.rsplit("@", 1)
        if len(parts) == 2 and parts[0].endswith("svc:stdio.in"):
            try:
                pid_text = str(int(parts[1], 0))
            except ValueError:
                pid_text = parts[1]
            stdin_label = True
    if stdin_label and pid_text is not None:
        print(f"{length_text} bytes sent to stdin on pid {pid_text}")
    elif isinstance(target, str):
        print(f"{length_text} bytes sent to {target}")
    else:
        print(f"{length_text} bytes sent")


def _pretty_list(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    block = payload.get("channels", {})
    pid = block.get("pid")
    channels = block.get("channels", [])
    print("list:")
    print(f"  pid       : {pid}")
    if not channels:
        print("  (no channels)")
        return
    header = "    Descriptor  Target                          Mode  Capacity  Depth  Bytes  Subs"
    print(header)
    print("    " + "-" * (len(header) - 4))

    for entry in channels:
        descriptor = entry.get("descriptor_id")
        descriptor_val = _as_int(descriptor, -1)
        descriptor_str = "-" if descriptor_val < 0 else str(descriptor_val)
        target = entry.get("target", "")
        mode = _as_int(entry.get("mode_mask"), 0) & 0xFFFF
        capacity = _as_int(entry.get("capacity"), 0)
        depth = _as_int(entry.get("queue_depth"), 0)
        bytes_used = _as_int(entry.get("bytes_used"), 0)
        subscribers = _as_int(entry.get("subscriber_count"), 0)
        print(
            f"  {descriptor_str:>10}  {target:<30}  0x{mode:04X}  "
            f"{capacity:8}  {depth:5}  {bytes_used:5}  {subscribers:4}"
        )


def _pretty_reload(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    block = payload.get("reload", {})
    print("reload:")
    print(f"  old_pid   : {block.get('old_pid')}")
    print(f"  new_pid   : {block.get('new_pid')}")
    print(f"  program   : {block.get('program')}")
    image = block.get("image") or {}
    if image:
        entry = _as_int(image.get("entry"), 0) & 0xFFFFFFFF
        code_len = _as_int(image.get("code_len"), 0)
        ro_len = _as_int(image.get("ro_len"), 0)
        bss = _as_int(image.get("bss"), 0)
        image_pid = image.get("pid")
        try:
            pid_display = int(image_pid)
        except (TypeError, ValueError):
            pid_display = image_pid
        print(f"  image     : pid={pid_display} entry=0x{entry:08X} code={code_len} ro={ro_len} bss={bss}")
    task = block.get("task")
    if task:
        state = task.get("state")
        program = task.get("program")
        print(f"  task      : state={state} program={program}")


def _print_stdio_streams(entries: list[dict], indent: str = "  ") -> None:
    for entry in entries:
        stream = entry.get("stream", "?")
        mode_name = entry.get("mode", "?")
        mask = _as_int(entry.get("mode_mask"), 0)
        print(f"{indent}{stream:<6}: {mode_name} (0x{mask:04X})")


def _pretty_stdio(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    config = payload.get("config", {})
    print("stdio:")
    scope = config.get("scope")
    if scope:
        print(f"  scope     : {scope}")
    pid = config.get("pid")
    if pid is not None and scope != "default":
        print(f"  pid       : {pid}")
    streams = config.get("streams") or []
    if streams:
        print("  streams:")
        _print_stdio_streams(streams, indent="    ")
    default_streams = config.get("default") or []
    if default_streams:
        print("  default:")
        _print_stdio_streams(default_streams, indent="    ")
    tasks = config.get("tasks") or []
    if tasks:
        print("  tasks:")
        for entry in tasks:
            entry_pid = entry.get("pid")
            print(f"    pid {entry_pid}:")
            _print_stdio_streams(entry.get("streams") or [], indent="      ")
    mode_name = config.get("mode")
    if mode_name:
        print(f"  mode      : {mode_name}")
    mode_mask = config.get("mode_mask")
    if mode_mask is not None:
        print(f"  mode_mask : 0x{_as_int(mode_mask):04X}")
    applied = config.get("applied") or []
    if applied:
        print("  applied:")
        for entry in applied:
            stream = entry.get("stream")
            target = entry.get("target")
            status = entry.get("mbx_status", entry.get("status"))
            line = f"    {stream or '?'}"
            if target:
                line += f" -> {target}"
            if status is not None:
                line += f" status={status}"
        print(line)


def _pretty_dbg(payload: dict) -> None:
    block = payload.get("debug") or {}
    op = block.get("op", "")
    pid = block.get("pid")
    header = f"dbg {op}" if op else "dbg"
    if pid is not None:
        header += f" pid={pid}"
    print(header)
    halted = block.get("halted")
    if halted is not None:
        print(f"  halted: {halted}")
    stop = block.get("stop")
    if isinstance(stop, dict) and stop:
        print("  last_stop:")
        for key in sorted(stop):
            print(f"    {key}: {stop[key]}")
    breakpoints = block.get("breakpoints")
    if breakpoints is not None:
        if breakpoints:
            print("  breakpoints:")
            for addr in breakpoints:
                try:
                    value = int(addr)
                except (TypeError, ValueError):
                    print(f"    {addr}")
                else:
                    print(f"    0x{value:04X}")
        else:
            print("  breakpoints: (none)")
    registers = block.get("registers")
    if isinstance(registers, dict) and registers:
        print("  registers:")
        _render_register_block(registers, indent="    ")
    result = block.get("result")
    if isinstance(result, dict) and result:
        print("  result:")
        for key in ("executed", "running", "pc", "steps", "cycles", "paused", "current_pid", "next_pid"):
            if key in result:
                print(f"    {key}: {result[key]}")
        debug_event = result.get("debug_event")
        if isinstance(debug_event, dict) and debug_event:
            print("    debug_event:")
            for key, value in debug_event.items():
                print(f"      {key}: {value}")
        events = result.get("events") or []
        if events:
            print("    events:")
            for event in events:
                print(f"      {event}")


def _pretty_sched(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload.get("task"):
        task = payload["task"]
        print("sched task update:")
        for key, value in sorted(task.items()):
            print(f"  {key:<12}: {value}")
        return
    sched = payload.get("scheduler", {})
    counters = sched.get("counters", {})
    trace = sched.get("trace", [])
    print("sched stats:")
    if counters:
        print("  counters:")
        for pid, entries in sorted(counters.items()):
            print(f"    pid {pid}:")
            for event, value in sorted(entries.items()):
                print(f"      {event:<8} : {value}")
    else:
        print("  counters: (none)")
    if trace:
        print("  trace (most recent first):")
        for entry in reversed(trace):
            pid_text = f" pid={entry['pid']}" if 'pid' in entry else ""
            extra = {k: v for k, v in entry.items() if k not in {'event', 'ts', 'pid'}}
            extra_text = f" {extra}" if extra else ""
            print(f"    [{entry['event']}] ts={entry['ts']:.6f}{pid_text}{extra_text}")
    else:
        print("  trace: (empty)")


def _pretty_dmesg(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    logs = payload.get("logs") or []
    print("dmesg:")
    if not logs:
        print("  (empty)")
        return
    for entry in logs:
        ts = entry.get("ts")
        if isinstance(ts, (int, float)):
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        else:
            timestamp = "--:--:--"
        level = (entry.get("level") or "").upper()
        message = entry.get("message", "")
        seq = entry.get("seq")
        clock_steps = entry.get("clock_steps", entry.get("clock_cycles"))
        clock_text = "-" if clock_steps is None else str(clock_steps)
        event = entry.get("event") if isinstance(entry.get("event"), dict) else None
        pid = entry.get("pid")
        if pid is None and isinstance(event, dict):
            pid = event.get("pid") or event.get("src_pid")
        if pid is None:
            pid = entry.get("current_pid")
        pid_text = "-" if pid is None else str(pid)
        event_type = message
        if isinstance(event, dict):
            event_type = event.get("type", event_type)
        print(f"  [{seq}] {pid_text} ({clock_text}) {timestamp} \"{level}\" \"{event_type}\"")
        extra = {k: v for k, v in entry.items() if k not in {"ts", "level", "message", "seq", "clock_steps", "clock_cycles"}}
        if extra:
            print(f"        {json.dumps(extra, sort_keys=True)}")


_MAILBOX_NAMESPACE_NAMES = {
    0: "pid",
    1: "svc",
    2: "app",
    3: "shared",
}

_MAILBOX_NAMESPACE_ALIASES = {
    "pid": "pid",
    "svc": "svc",
    "service": "svc",
    "app": "app",
    "application": "app",
    "shared": "shared",
    "global": "shared",
}


def _mailbox_namespace_name(value: int) -> str:
    return _MAILBOX_NAMESPACE_NAMES.get(value, str(value))


def _normalize_mailbox_namespace(token: str) -> str:
    key = token.strip().lower()
    normalized = _MAILBOX_NAMESPACE_ALIASES.get(key)
    if normalized is None:
        raise ValueError(f"unknown mailbox namespace '{token}'")
    return normalized


def _pretty_mbox(payload: dict) -> None:
    if payload.get("status") != "ok":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    descriptors = payload.get("descriptors") or []
    filter_pid = payload.get("_filter_pid")
    filter_namespace = payload.get("_filter_namespace")
    filtered: list[dict] = []
    for desc in descriptors:
        namespace_value = _as_int(desc.get("namespace"), -1)
        namespace_name = _mailbox_namespace_name(namespace_value)
        if filter_namespace is not None and namespace_name != filter_namespace:
            continue
        owner = desc.get("owner_pid")
        owner_pid = _as_int(owner, None) if owner is not None else None
        if filter_pid is not None and owner_pid != filter_pid:
            continue
        filtered.append(desc)
    print("mbox:")
    if filter_namespace is not None:
        print(f"  namespace : {filter_namespace}")
    if filter_pid is not None:
        print(f"  filter_pid: {filter_pid}")
    if not filtered:
        if filter_pid is not None and filter_namespace is not None:
            print("  (no mailboxes matching filters)")
        elif filter_pid is not None:
            print("  (no mailboxes for specified pid)")
        elif filter_namespace is not None:
            print("  (no mailboxes in selected namespace)")
        else:
            print("  (no mailboxes)")
        return
    header = "    ID  Namespace  Owner  Depth  Bytes  Mode   Name"
    print(header)
    print("    " + "-" * (len(header) - 4))
    for desc in filtered:
        descriptor_id = desc.get("descriptor_id")
        namespace = _mailbox_namespace_name(_as_int(desc.get("namespace"), -1))
        owner = desc.get("owner_pid")
        owner_str = str(owner) if owner is not None else "-"
        depth = _as_int(desc.get("queue_depth"), 0)
        bytes_used = _as_int(desc.get("bytes_used"), 0)
        mode = _as_int(desc.get("mode_mask"), 0)
        name = desc.get("name", "")
        print(f"  {descriptor_id:5}  {namespace:<9}  {owner_str:>5}  {depth:5}  {bytes_used:5}  0x{mode:04X}  {name}")

PRETTY_HANDLERS = {
    'dumpregs': _pretty_dumpregs,
    'info': _pretty_info,
    'attach': _pretty_info,
    'bp': _pretty_bp,
    'sym': _pretty_sym,
    'symbols': _pretty_symbols,
    'disasm': _pretty_disasm,
    'stack': _pretty_stack,
    'ps': _pretty_ps,
    'list': _pretty_list,
    'reload': _pretty_reload,
    'dmesg': _pretty_dmesg,
    'stdio': _pretty_stdio,
    'mbox': _pretty_mbox,
    'clock': _pretty_clock,
    'step': _pretty_clock,
    'trace': _pretty_trace,
    'listen': _pretty_listen,
    'send': _pretty_send,
    'dbg': _pretty_dbg,
    'sched': _pretty_sched,
}


def _render_context(context: dict, indent: str = "  ") -> None:
    for key in ("pid", "state", "priority", "time_slice_steps", "accounted_steps", "reg_base", "stack_base", "stack_limit", "exit_status", "trace"):
        if key in context:
            value = context[key]
            if key.endswith('_base') or key.endswith('_limit'):
                value = f"0x{int(value) & 0xFFFFFFFF:08X}"
            print(f"{indent}{key:<14}: {value}")


def _render_register_block(registers: dict, indent: str = "  ") -> None:
    print(f"{indent}pc     : 0x{registers.get('pc', 0):08X}  sp: 0x{registers.get('sp', 0):08X}")
    print(f"{indent}flags  : 0x{registers.get('flags', 0):X}    running: {registers.get('running')}")
    if 'reg_base' in registers or 'stack_base' in registers:
        reg_base = registers.get('reg_base', 0)
        stack_base = registers.get('stack_base', 0)
        stack_limit = registers.get('stack_limit', 0)
        stack_size = registers.get('stack_size')
        eff_sp = registers.get('sp_effective')
        line = f"{indent}reg_base: 0x{reg_base & 0xFFFFFFFF:08X}  stack_base: 0x{stack_base & 0xFFFFFFFF:08X}"
        line += f"  stack_limit: 0x{stack_limit & 0xFFFFFFFF:08X}"
        if stack_size is not None:
            line += f"  stack_size: 0x{int(stack_size) & 0xFFFFFFFF:08X}"
        if eff_sp is not None:
            line += f"  sp_effective: 0x{int(eff_sp) & 0xFFFFFFFF:08X}"
        print(line)
    step_count = registers.get('steps', registers.get('cycles', 0))
    print(f"{indent}steps  : {step_count}")
    context = registers.get('context', {})
    if isinstance(context, dict) and context:
        print(f"{indent}context:")
        _render_context(context, indent + "  ")
    regs_list = registers.get('regs', [])
    if regs_list:
        print(f"{indent}regs:")
        for idx, value in enumerate(regs_list):
            print(f"{indent}  R{idx:02}: 0x{value & 0xFFFFFFFF:08X}")


def send_request(host: str, port: int, payload: dict, *, auto_events: bool = False) -> dict:
    session = _ensure_session(host, port, auto_events=auto_events)
    payload = dict(payload)
    cmd = str(payload.get("cmd", "")).lower()
    use_session = not cmd.startswith("session.")
    return session.request(payload, use_session=use_session)



def _build_payload(cmd: str, args: list[str], current_dir: Path | None = None) -> dict:
    payload_cmd = cmd
    payload: dict[str, object] = {"cmd": payload_cmd}

    if cmd in {"attach", "detach", "ps", "clock", "shutdown", "pause", "resume", "kill", "load", "exec", "reload", "list", "step", "listen", "send", "sched", "info", "peek", "poke", "dumpregs", "stdio", "mbox", "mailboxes", "mailbox_snapshot", "mailbox_open", "mailbox_close", "mailbox_bind", "mailbox_send", "mailbox_recv", "mailbox_peek", "mailbox_tap", "dbg", "disasm", "stack"}:
        pass

    if cmd == "info":
        if args:
            payload["pid"] = args[0]
        return payload

    if cmd == "bp":
        return _build_bp_payload(args)
    if cmd == "symbols":
        return _build_symbols_payload(args)
    if cmd == "sym":
        return _build_sym_payload(args)
    if cmd == "disasm":
        if not args:
            raise ValueError("disasm requires <pid> [options]")
        payload["pid"] = int(args[0], 0)
        addr_set = False
        count_set = False
        mode_set = False
        i = 1
        while i < len(args):
            token = args[i]
            if token in {"--addr", "-a"}:
                i += 1
                if i >= len(args):
                    raise ValueError("disasm --addr requires a value")
                payload["addr"] = int(args[i], 0)
                addr_set = True
            elif token in {"--count", "-c"}:
                i += 1
                if i >= len(args):
                    raise ValueError("disasm --count requires a value")
                payload["count"] = int(args[i], 0)
                count_set = True
            elif token in {"--mode", "-m"}:
                i += 1
                if i >= len(args):
                    raise ValueError("disasm --mode requires a value")
                payload["mode"] = args[i]
                mode_set = True
            elif token in {"--cached", "-C"}:
                payload["mode"] = "cached"
                mode_set = True
            else:
                if not addr_set:
                    payload["addr"] = int(token, 0)
                    addr_set = True
                elif not count_set:
                    payload["count"] = int(token, 0)
                    count_set = True
                else:
                    raise ValueError("disasm usage: disasm <pid> [addr] [count] [--mode on-demand|cached]")
            i += 1
        if not mode_set:
            payload.setdefault("mode", "on-demand")
        return payload
    if cmd == "stack":
        if not args:
            raise ValueError("stack requires <pid> [frames]")
        payload["pid"] = int(args[0], 0)
        if len(args) > 1:
            payload["max"] = int(args[1], 0)
        return payload

    if cmd == "dbg":
        if not args:
            raise ValueError("dbg usage: dbg <attach|detach|regs|cont|step|break|bp> ...")
        subcmd = args[0].lower()
        tokens = args[1:]
        if subcmd in {"attach", "detach"}:
            if not tokens:
                raise ValueError(f"dbg {subcmd} requires <pid>")
            payload["op"] = subcmd
            payload["pid"] = int(tokens[0], 0)
            return payload
        if subcmd in {"regs", "registers"}:
            if not tokens:
                raise ValueError("dbg regs requires <pid>")
            payload["op"] = "regs"
            payload["pid"] = int(tokens[0], 0)
            return payload
        if subcmd in {"cont", "continue"}:
            if not tokens:
                raise ValueError("dbg cont requires <pid> [cycles]")
            payload["op"] = "cont"
            payload["pid"] = int(tokens[0], 0)
            if len(tokens) > 1:
                payload["cycles"] = int(tokens[1], 0)
            return payload
        if subcmd == "step":
            if not tokens:
                raise ValueError("dbg step requires <pid> [count]")
            payload["op"] = "step"
            payload["pid"] = int(tokens[0], 0)
            if len(tokens) > 1:
                payload["count"] = int(tokens[1], 0)
            return payload
        if subcmd == "break":
            if not tokens:
                raise ValueError("dbg break requires <pid>")
            payload["op"] = "break"
            payload["pid"] = int(tokens[0], 0)
            return payload
        if subcmd == "bp":
            if not tokens:
                raise ValueError("dbg bp usage: dbg bp <list|add|remove> ...")
            action = tokens[0].lower()
            rest = tokens[1:]
            payload["op"] = "bp"
            if action in {"list", "ls"}:
                if not rest:
                    raise ValueError("dbg bp list requires <pid>")
                payload["action"] = "list"
                payload["pid"] = int(rest[0], 0)
                return payload
            if action == "add":
                if len(rest) < 2:
                    raise ValueError("dbg bp add requires <pid> <addr>")
                payload["action"] = "add"
                payload["pid"] = int(rest[0], 0)
                payload["addr"] = int(rest[1], 0)
                return payload
            if action in {"remove", "rm", "del", "delete"}:
                if len(rest) < 2:
                    raise ValueError("dbg bp remove requires <pid> <addr>")
                payload["action"] = "remove"
                payload["pid"] = int(rest[0], 0)
                payload["addr"] = int(rest[1], 0)
                return payload
            raise ValueError(f"dbg bp unknown action '{action}'")
        if subcmd in {"list", "ls"} and tokens:
            payload["op"] = "bp"
            payload["action"] = "list"
            payload["pid"] = int(tokens[0], 0)
            return payload
        raise ValueError(f"dbg unknown subcommand '{subcmd}'")

    if cmd == "trace":
        if not args:
            raise ValueError("trace requires <pid> [on|off]")
        payload["pid"] = args[0]
        if len(args) > 1:
            payload["mode"] = args[1]
        return payload

    if cmd == "clock":
        if not args:
            return payload
        subcmd = args[0].lower()
        payload["op"] = subcmd
        tokens = args[1:]
        if subcmd in {"start", "run", "stop", "halt", "status"}:
            if tokens:
                raise ValueError("clock usage: clock start|stop|status|run|halt [no extra arguments]")
            return payload
        if subcmd == "step":
            steps_value: Optional[int] = None
            target_pid: Optional[int] = None
            i = 0
            while i < len(tokens):
                token = tokens[i]
                if token in {"-p", "--pid"}:
                    i += 1
                    if i >= len(tokens):
                        raise ValueError("clock step -p/--pid requires <pid>")
                    try:
                        target_pid = int(tokens[i], 0)
                    except ValueError as exc:
                        raise ValueError("clock step pid must be integer") from exc
                elif steps_value is None:
                    try:
                        steps_value = int(token, 0)
                    except ValueError as exc:
                        raise ValueError("clock step steps must be integer") from exc
                else:
                    raise ValueError("clock step usage: clock step [steps] [-p <pid>]")
                i += 1
            if steps_value is not None:
                payload["steps"] = steps_value
            if target_pid is not None:
                payload["pid"] = target_pid
            return payload
        if subcmd == "rate":
            if not tokens:
                raise ValueError("clock rate requires <hz>")
            try:
                payload["rate"] = float(tokens[0])
            except ValueError as exc:
                raise ValueError("clock rate must be numeric") from exc
            if len(tokens) > 1:
                raise ValueError("clock rate usage: clock rate <hz>")
            return payload
        raise ValueError("clock usage: clock [status|start|stop|step [steps] [-p <pid>]|rate <hz>]")

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
        tokens = list(args)
        steps_value: Optional[int] = None
        target_pid: Optional[int] = None
        i = 0
        while i < len(tokens):
            token = tokens[i]
            if token in {"-p", "--pid"}:
                i += 1
                if i >= len(tokens):
                    raise ValueError("step -p/--pid requires <pid>")
                try:
                    target_pid = int(tokens[i], 0)
                except ValueError as exc:
                    raise ValueError("step pid must be integer") from exc
            elif steps_value is None:
                try:
                    steps_value = int(token, 0)
                except ValueError as exc:
                    raise ValueError("step count must be integer") from exc
            else:
                raise ValueError("step usage: step [steps] [-p <pid>]")
            i += 1
        if steps_value is not None:
            payload["steps"] = steps_value
        if target_pid is not None:
            payload["pid"] = target_pid
        return payload

    if cmd == "reload":
        if not args:
            raise ValueError("reload requires <pid>")
        payload["pid"] = args[0]
        if len(args) > 1:
            flag = args[1].lower()
            if flag in {"verbose", "--verbose"}:
                payload["verbose"] = True
            else:
                raise ValueError("reload usage: reload <pid> [verbose]")
        return payload

    if cmd == "list":
        if not args:
            raise ValueError("list requires <pid>")
        payload["pid"] = args[0]
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

    if cmd == "mbox":
        payload["cmd"] = "mailbox_snapshot"
        filter_pid: int | None = None
        filter_namespace: str | None = None
        tokens = list(args)
        i = 0
        while i < len(tokens):
            raw_token = tokens[i].strip()
            lower = raw_token.lower()
            if not raw_token or lower in {"all", "*"}:
                pass
            elif lower in {"namespace", "ns"}:
                i += 1
                if i >= len(tokens):
                    raise ValueError("mbox namespace requires a value")
                filter_namespace = _normalize_mailbox_namespace(tokens[i])
            elif lower.startswith("namespace=") or lower.startswith("ns="):
                _, value = lower.split("=", 1)
                filter_namespace = _normalize_mailbox_namespace(value)
            elif lower.startswith("namespace:") or lower.startswith("ns:"):
                _, value = lower.split(":", 1)
                filter_namespace = _normalize_mailbox_namespace(value)
            elif lower in {"owner", "pid"}:
                i += 1
                if i >= len(tokens):
                    raise ValueError("mbox pid requires an integer value")
                try:
                    filter_pid = int(tokens[i], 0)
                except ValueError as exc:
                    raise ValueError("mbox pid must be an integer") from exc
            elif lower.startswith("owner=") or lower.startswith("pid="):
                try:
                    filter_pid = int(raw_token.split("=", 1)[1], 0)
                except ValueError as exc:
                    raise ValueError("mbox pid must be an integer") from exc
            elif lower.startswith("owner:") or lower.startswith("pid:"):
                try:
                    filter_pid = int(raw_token.split(":", 1)[1], 0)
                except ValueError as exc:
                    raise ValueError("mbox pid must be an integer") from exc
            elif lower in {"app", "shared", "svc"}:
                filter_namespace = _normalize_mailbox_namespace(lower)
            else:
                try:
                    filter_pid = int(raw_token, 0)
                except ValueError as exc:
                    raise ValueError("mbox usage: mbox [all|app|shared|svc|ns <name>] [pid <n>|owner <n>]") from exc
            i += 1
        if filter_pid is not None:
            payload["_filter_pid"] = filter_pid
        if filter_namespace is not None:
            payload["_filter_namespace"] = filter_namespace
        return payload

    if cmd == "dmesg":
        if args:
            try:
                payload["limit"] = int(args[0])
            except ValueError as exc:
                raise ValueError("dmesg limit must be an integer") from exc
        return payload

    if cmd == "stdio":
        payload["cmd"] = "stdio_fanout"
        tokens = list(args)
        if not tokens:
            return payload
        stream_keywords = {"in", "stdin", "out", "stdout", "err", "stderr", "both", "all"}
        if tokens:
            first = tokens[0].strip()
            lower = first.lower()
            if lower in {"default", "global", "template"}:
                payload["pid"] = "default"
                tokens.pop(0)
            elif lower in {"all", "*"}:
                tokens.pop(0)
            else:
                try:
                    payload["pid"] = int(first, 0)
                    tokens.pop(0)
                except ValueError:
                    if lower in stream_keywords:
                        pass
                    else:
                        raise ValueError("stdio usage: stdio [pid|default|all] [stream] [mode]")
        if tokens:
            payload["stream"] = tokens.pop(0)
        if tokens:
            payload["mode"] = tokens.pop(0)
        if tokens:
            raise ValueError("stdio usage: stdio [pid|default|all] [stream] [mode]")
        return payload

    if cmd == "sched":
        if not args:
            return payload
        first = args[0].lower()
        if first in {"stats", "trace"}:
            if len(args) > 1:
                payload["limit"] = args[1]
            return payload
        payload["pid"] = int(args[0], 0)
        tokens = args[1:]
        i = 0
        while i < len(tokens):
            token = tokens[i].lower()
            if token in {"priority", "quantum"} and i + 1 < len(tokens):
                payload[token] = int(tokens[i + 1], 0)
                i += 2
            else:
                raise ValueError("sched usage: sched [stats [limit]] | <pid> [priority <n>] [quantum <n>]")
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


def _build_bp_payload(args: list[str]) -> dict:
    if not args:
        raise ValueError("bp usage: bp <list|set|clear|clearall> ...")
    action = args[0].lower()
    tokens = args[1:]
    payload: dict[str, object] = {"cmd": "bp"}
    if action in {"list", "ls"}:
        if not tokens:
            raise ValueError("bp list requires <pid>")
        payload["op"] = "list"
        payload["pid"] = int(tokens[0], 0)
        return payload
    if action in {"set", "add"}:
        if len(tokens) < 2:
            raise ValueError("bp set requires <pid> <addr>")
        payload["op"] = "set"
        payload["pid"] = int(tokens[0], 0)
        payload["addr"] = int(tokens[1], 0)
        return payload
    if action in {"clear", "remove", "rm", "del", "delete"}:
        if len(tokens) < 2:
            raise ValueError("bp clear requires <pid> <addr>")
        payload["op"] = "clear"
        payload["pid"] = int(tokens[0], 0)
        payload["addr"] = int(tokens[1], 0)
        return payload
    if action in {"clear_all", "clearall", "reset"}:
        if not tokens:
            raise ValueError("bp clear_all requires <pid>")
        payload["op"] = "clear_all"
        payload["pid"] = int(tokens[0], 0)
        return payload
    raise ValueError(f"bp unknown action '{action}'")


def _build_symbols_payload(args: list[str]) -> dict:
    if not args:
        raise ValueError("symbols usage: symbols <pid> [--type functions|variables|all] [--offset N] [--limit N]")
    payload: dict[str, object] = {"cmd": "symbols", "pid": int(args[0], 0)}
    i = 1
    while i < len(args):
        token = args[i]
        if token in {"--type", "--kind", "-t"}:
            i += 1
            if i >= len(args):
                raise ValueError("symbols --type requires a value")
            payload["type"] = args[i]
        elif token in {"--offset", "-o"}:
            i += 1
            if i >= len(args):
                raise ValueError("symbols --offset requires a value")
            payload["offset"] = int(args[i], 0)
        elif token in {"--limit", "-l"}:
            i += 1
            if i >= len(args):
                raise ValueError("symbols --limit requires a value")
            payload["limit"] = int(args[i], 0)
        else:
            raise ValueError("symbols usage: symbols <pid> [--type functions|variables|all] [--offset N] [--limit N]")
        i += 1
    return payload


def _build_sym_payload(args: list[str]) -> dict:
    if not args:
        raise ValueError("sym usage: sym <info|addr|name|line|load> ...")
    subcmd = args[0].lower()
    tokens = args[1:]
    payload: dict[str, object] = {"cmd": "sym"}
    if subcmd in {"info", "i"}:
        if not tokens:
            raise ValueError("sym info requires <pid>")
        payload["op"] = "info"
        payload["pid"] = int(tokens[0], 0)
        return payload
    if subcmd in {"addr", "lookup", "lookup_addr"}:
        if len(tokens) < 2:
            raise ValueError("sym addr requires <pid> <address>")
        payload["op"] = "lookup_addr"
        payload["pid"] = int(tokens[0], 0)
        payload["address"] = tokens[1]
        return payload
    if subcmd in {"name", "lookup_name"}:
        if len(tokens) < 2:
            raise ValueError("sym name requires <pid> <symbol>")
        payload["op"] = "lookup_name"
        payload["pid"] = int(tokens[0], 0)
        payload["name"] = tokens[1]
        return payload
    if subcmd in {"line", "lookup_line"}:
        if len(tokens) < 2:
            raise ValueError("sym line requires <pid> <address>")
        payload["op"] = "lookup_line"
        payload["pid"] = int(tokens[0], 0)
        payload["address"] = tokens[1]
        return payload
    if subcmd in {"load", "set"}:
        if len(tokens) < 2:
            raise ValueError("sym load requires <pid> <path>")
        payload["op"] = "load"
        payload["pid"] = int(tokens[0], 0)
        payload["path"] = tokens[1]
        return payload
    raise ValueError(f"sym unknown subcommand '{subcmd}'")
def cmd_loop(host: str, port: int, cwd: Path | None = None, *, default_json: bool = False) -> None:
    _init_history()
    current_dir = (cwd or Path.cwd()).resolve()
    _ensure_session(host, port, auto_events=True)
    print(f"Connected to executive at {host}:{port}. Type 'help' for commands or 'help <command>' for details.")
    while True:
        try:
            line = input('hsx> ')
        except EOFError:
            print()
            break
        line = line.strip()
        if not line:
            continue
        if line.lower() in {'quit', 'exit'}:
            break
        if line.lower() == 'help':
            _print_general_help()
            continue
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(f"parse error: {exc}")
            continue
        cmd = parts[0].lower()
        raw_args = parts[1:]
        if cmd == 'stdiofanout':
            cmd = 'stdio'

        force_json = default_json
        args: list[str] = []
        for token in raw_args:
            if token == '--json':
                force_json = True
            else:
                args.append(token)

        session = _ensure_session(host, port, auto_events=True)

        if cmd == 'help':
            if args:
                _print_topic_help(args[0])
            else:
                _print_general_help()
            continue
        if cmd == 'events':
            limit = 10
            if args:
                try:
                    limit = int(args[0], 0)
                except ValueError:
                    print("usage: events [count]")
                    continue
            events = session.get_recent_events(limit)
            if not events:
                print("events: <no buffered events>")
                continue
            if force_json:
                for event in events:
                    print(json.dumps(event, indent=2, sort_keys=True))
            else:
                _pretty_events(events)
            continue
        if cmd == 'symbols':
            try:
                payload = _build_symbols_payload(args)
            except ValueError as exc:
                print(exc)
                continue
            try:
                resp = send_request(host, port, payload)
            except Exception as exc:
                print(f"error: {exc}")
                continue
            handler = PRETTY_HANDLERS.get('symbols')
            if handler and not force_json:
                handler(resp)
            else:
                print(json.dumps(resp, indent=2, sort_keys=True))
            continue
        if cmd == 'sym':
            try:
                payload = _build_sym_payload(args)
            except ValueError as exc:
                print(exc)
                continue
            try:
                resp = send_request(host, port, payload)
            except Exception as exc:
                print(f"error: {exc}")
                continue
            handler = PRETTY_HANDLERS.get('sym')
            if handler and not force_json:
                handler(resp)
            else:
                print(json.dumps(resp, indent=2, sort_keys=True))
            continue
        if cmd in {'load', 'exec'}:
            tokens = list(args)
            verbose_flag = False
            symbols_override: Optional[str] = None
            i = 0
            while i < len(tokens):
                token = tokens[i]
                if token in {'--symbols', '--sym'}:
                    if i + 1 >= len(tokens):
                        print(f"usage: {cmd} <path|bundle> [--symbols <path>] [verbose]")
                        symbols_override = None
                        tokens = []
                        break
                    symbols_override = tokens[i + 1]
                    del tokens[i:i + 2]
                    continue
                i += 1
            if tokens and tokens[-1].lower() in {"verbose", "--verbose"}:
                verbose_flag = True
                tokens = tokens[:-1]
            if not tokens:
                print(f"usage: {cmd} <path|bundle> [verbose]")
                continue
            try:
                targets = _resolve_load_targets(tokens[0], current_dir)
            except ValueError as exc:
                print(exc)
                continue
            rpc_cmd = 'exec' if cmd == 'exec' else 'load'
            sym_override_resolved = None
            if symbols_override:
                sym_path = Path(symbols_override)
                if not sym_path.is_absolute():
                    sym_path = (current_dir / sym_path).resolve(strict=False)
                else:
                    sym_path = sym_path.resolve(strict=False)
                sym_override_resolved = str(sym_path)
            try:
                results = _perform_load_sequence(host, port, targets, verbose=verbose_flag, rpc_cmd=rpc_cmd, symbols=sym_override_resolved)
            except Exception as exc:
                print(f"error: {exc}")
                continue
            for path, resp in results:
                print(f"[{rpc_cmd}] {path}")
                handler = PRETTY_HANDLERS.get(rpc_cmd)
                if handler and not force_json:
                    handler(resp)
                else:
                    print(json.dumps(resp, indent=2, sort_keys=True))
            continue
        if cmd == 'save':
            if not args:
                print("usage: save <name>")
                continue
            try:
                target, count = _save_loaded_images(args[0], current_dir, host, port)
            except ValueError as exc:
                print(exc)
                continue
            noun = "entry" if count == 1 else "entries"
            print(f"Saved {count} {noun} to {target}")
            continue
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
                    if force_json:
                        print(json.dumps(resp, indent=2, sort_keys=True))
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

        filter_pid = None
        filter_namespace = None
        if cmd == 'mbox':
            filter_pid = payload.pop("_filter_pid", None)
            filter_namespace = payload.pop("_filter_namespace", None)

        try:
            resp = send_request(host, port, payload)
        except Exception as exc:
            print(f"error: {exc}")
            continue
        if cmd == 'mbox':
            resp = dict(resp)
            if filter_pid is not None:
                resp["_filter_pid"] = filter_pid
            if filter_namespace is not None:
                resp["_filter_namespace"] = filter_namespace
        handler = PRETTY_HANDLERS.get(cmd)
        if handler and not force_json:
            handler(resp)
        else:
            print(json.dumps(resp, indent=2, sort_keys=True))

def main() -> None:
    parser = argparse.ArgumentParser(description="HSX shell client")
    parser.add_argument("cmd", nargs="?", help="command to send (omit for interactive mode)")
    parser.add_argument("args", nargs="*", help="optional arguments for the command")
    parser.add_argument("--host", default="127.0.0.1", help="executive host")
    parser.add_argument("--port", type=int, default=9998, help="executive port")
    parser.add_argument("--steps", type=int, help="steps for step command")
    parser.add_argument("--path", help="path for load/exec commands")
    parser.add_argument("--symbols", help="override symbol file for load/exec commands")
    parser.add_argument("--verbose", action="store_true", help="verbose load")
    parser.add_argument("--json", action="store_true", help="print raw JSON responses")
    args_ns = parser.parse_args()
    if not args_ns.cmd:
        cmd_loop(args_ns.host, args_ns.port, default_json=args_ns.json)
        return

    cmd = args_ns.cmd.lower()
    if cmd == 'stdiofanout':
        cmd = 'stdio'
    args = [token for token in args_ns.args if token != "--json"]
    force_json = args_ns.json

    if cmd == 'help':
        if args:
            _print_topic_help(args[0])
        else:
            _print_general_help()
        return
    if cmd == 'events':
        session = _ensure_session(args_ns.host, args_ns.port, auto_events=True)
        limit = 10
        if args:
            try:
                limit = int(args[0], 0)
            except ValueError:
                parser.error("events expects an optional integer count")
        events = session.get_recent_events(limit)
        if not events:
            print("events: <no buffered events>")
            return
        if force_json:
            for event in events:
                print(json.dumps(event, indent=2, sort_keys=True))
        else:
            _pretty_events(events)
        return
    if cmd == 'bp':
        try:
            payload = _build_bp_payload(args)
        except ValueError as exc:
            parser.error(str(exc))
        resp = send_request(args_ns.host, args_ns.port, payload)
        handler = PRETTY_HANDLERS.get('bp')
        if handler and not force_json:
            handler(resp)
        else:
            print(json.dumps(resp, indent=2, sort_keys=True))
        return
    if cmd == 'symbols':
        try:
            payload = _build_symbols_payload(args)
        except ValueError as exc:
            parser.error(str(exc))
        resp = send_request(args_ns.host, args_ns.port, payload)
        handler = PRETTY_HANDLERS.get('symbols')
        if handler and not force_json:
            handler(resp)
        else:
            print(json.dumps(resp, indent=2, sort_keys=True))
        return
    if cmd == 'sym':
        try:
            payload = _build_sym_payload(args)
        except ValueError as exc:
            parser.error(str(exc))
        resp = send_request(args_ns.host, args_ns.port, payload)
        handler = PRETTY_HANDLERS.get('sym')
        if handler and not force_json:
            handler(resp)
        else:
            print(json.dumps(resp, indent=2, sort_keys=True))
        return

    if cmd in {'load', 'exec'}:
        tokens = list(args)
        if args_ns.path and not tokens:
            tokens = [args_ns.path]
        verbose_flag = args_ns.verbose
        if tokens and tokens[-1].lower() in {"verbose", "--verbose"}:
            verbose_flag = True
            tokens = tokens[:-1]
        if not tokens:
            parser.error(f"{cmd} requires <path|bundle>")
        try:
            targets = _resolve_load_targets(tokens[0], Path.cwd())
        except ValueError as exc:
            parser.error(str(exc))
        sym_override = args_ns.symbols
        if sym_override:
            sym_path = Path(sym_override)
            if not sym_path.is_absolute():
                sym_path = (Path.cwd() / sym_path).resolve(strict=False)
            else:
                sym_path = sym_path.resolve(strict=False)
            sym_override = str(sym_path)
        try:
            results = _perform_load_sequence(
                args_ns.host,
                args_ns.port,
                targets,
                verbose=verbose_flag,
                rpc_cmd='exec' if cmd == 'exec' else 'load',
                symbols=sym_override,
            )
        except Exception as exc:
            parser.error(str(exc))
        for path, resp in results:
            print(f"[{cmd}] {path}")
            handler = PRETTY_HANDLERS.get(cmd)
            if handler and not force_json:
                handler(resp)
            else:
                print(json.dumps(resp, indent=2, sort_keys=True))
        return

    if cmd == 'save':
        if not args:
            parser.error("save requires <name>")
        try:
            target, count = _save_loaded_images(args[0], Path.cwd(), args_ns.host, args_ns.port)
        except ValueError as exc:
            parser.error(str(exc))
        noun = "entry" if count == 1 else "entries"
        print(f"Saved {count} {noun} to {target}")
        return

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

    if cmd == 'step' and args_ns.steps is not None and not args:
        args = [str(args_ns.steps)]

    try:
        payload = _build_payload(cmd, args, Path.cwd())
    except ValueError as exc:
        parser.error(str(exc))

    if cmd == 'reload' and args_ns.verbose:
        payload['verbose'] = True

    filter_pid = None
    filter_namespace = None
    if cmd == 'mbox':
        filter_pid = payload.pop("_filter_pid", None)
        filter_namespace = payload.pop("_filter_namespace", None)

    try:
        resp = send_request(args_ns.host, args_ns.port, payload)
    except Exception as exc:
        parser.error(str(exc))

    if cmd == 'mbox':
        resp = dict(resp)
        if filter_pid is not None:
            resp["_filter_pid"] = filter_pid
        if filter_namespace is not None:
            resp["_filter_namespace"] = filter_namespace

    handler = PRETTY_HANDLERS.get(cmd)
    if handler and not force_json:
        handler(resp)
    else:
        print(json.dumps(resp, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
