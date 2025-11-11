"""hsx-dbg CLI entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List

from .commands import build_registry
from .context import DebuggerContext
from .parser import split_command
from .repl import DebuggerREPL

LOG = logging.getLogger("hsx_dbg.cli")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HSX CLI Debugger")
    parser.add_argument("--host", default="127.0.0.1", help="Executive host")
    parser.add_argument("--port", type=int, default=9998, help="Executive port")
    parser.add_argument("--json", action="store_true", help="Emit JSON output when supported")
    parser.add_argument("--log-level", default=os.environ.get("HSX_DBG_LOG", "INFO"), help="Logging level (default INFO)")
    parser.add_argument(
        "-c",
        "--command",
        help="Execute a single command non-interactively (quote the command string)",
    )
    parser.add_argument(
        "--history",
        type=Path,
        default=Path.home() / ".hsx-dbg-history",
        help="Path to command history file (prompt_toolkit mode)",
    )
    parser.add_argument(
        "--keepalive-interval",
        type=int,
        help="Override keepalive interval (seconds)",
    )
    parser.add_argument(
        "--no-keepalive",
        action="store_true",
        help="Disable automatic keepalive pings",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    ctx = DebuggerContext(
        host=args.host,
        port=args.port,
        json_output=args.json,
        keepalive_enabled=not args.no_keepalive,
        keepalive_interval=args.keepalive_interval,
    )
    registry = build_registry()
    if args.command:
        return _run_single_command(ctx, registry, args.command)
    repl = DebuggerREPL(ctx, registry, history_path=str(args.history))
    try:
        return repl.run()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print()
        return 0


def _run_single_command(ctx: DebuggerContext, registry, command_line: str) -> int:
    argv = split_command(command_line)
    if not argv:
        return 0
    cmd_name, *cmd_args = argv
    if cmd_name.startswith("#parse-error"):
        print(f"Parse error: {' '.join(cmd_args)}")
        return 1
    command = registry.get(cmd_name)
    if not command:
        print(f"Unknown command: {cmd_name}")
        return 1
    try:
        return command.run(ctx, cmd_args)
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # pragma: no cover - defensive
        LOG.exception("command failed")
        print(f"Command '{cmd_name}' failed: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
