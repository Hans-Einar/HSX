#!/usr/bin/env python3
from __future__ import annotations
"""HSX process manager.

Provides an interactive prompt for launching/stopping the HSX VM, executive
daemon, and shell client. The manager keeps subprocesses alive, shows status,
and wraps restart/shutdown flows so that restarts happen cleanly without
leaving orphaned Python processes behind.

Commands (type `help` after launching for the list):
  start [vm|exec|shell|all]
  stop  [vm|exec|shell|all]
  restart [vm|exec|shell|all]
  status
  load <path.hxe>
  shell            # spawn a new shell window
  quit
"""


import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

DEFAULT_VM_PORT = 9999
DEFAULT_EXEC_PORT = 9998


def send_exec_request(host: str, port: int, payload: Dict[str, object]) -> Dict[str, object]:
    payload = dict(payload)
    payload.setdefault("version", 1)
    with socket.create_connection((host, port), timeout=5.0) as sock:
        with sock.makefile("w", encoding="utf-8", newline="\n") as wfile, sock.makefile(
            "r", encoding="utf-8", newline="\n"
        ) as rfile:
            wfile.write(json_dumps(payload) + "\n")
            wfile.flush()
            line = rfile.readline()
            if not line:
                raise RuntimeError("executive closed connection")
            return json.loads(line)


def json_dumps(obj: object) -> str:
    return json.dumps(obj, separators=(",", ":"))


class ManagedProcess:
    def __init__(
        self,
        name: str,
        cmd: List[str],
        cwd: Path,
        *,
        inline_runner: Optional[Callable[[], None]] = None,
    ) -> None:
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self._inline_runner = inline_runner
        self._inline_active = False

    def start(self, additional_env: Optional[Dict[str, str]] = None) -> None:
        if self._inline_runner is not None:
            if self._inline_active:
                print(f"[{self.name}] inline session already active")
                return
            print(f"[{self.name}] entering inline session. Type 'exit' to return.")
            self._inline_active = True
            try:
                self._inline_runner()
            finally:
                self._inline_active = False
                print(f"[{self.name}] inline session ended.")
            return
        if self.is_running:
            print(f"[{self.name}] already running (pid {self.process.pid})")
            return
        env = os.environ.copy()
        if additional_env:
            env.update(additional_env)
        creationflags = 0
        if self.name == "shell" and os.name == "nt":
            creationflags = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
        print(f"[{self.name}] starting: {' '.join(self.cmd)}")
        self.process = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            env=env,
            creationflags=creationflags,
        )

    def stop(self, graceful: bool = True) -> None:
        if self._inline_runner is not None:
            if not self._inline_active:
                print(f"[{self.name}] inline session not active")
            else:
                print(f"[{self.name}] inline session active; exit from shell to return")
            return
        if not self.is_running:
            print(f"[{self.name}] not running")
            return
        proc = self.process
        assert proc is not None
        print(f"[{self.name}] stopping pid {proc.pid}")
        if graceful:
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                print(f"[{self.name}] terminate timeout, killing")
                proc.kill()
        else:
            proc.kill()
            proc.wait()
        self.process = None

    @property
    def is_running(self) -> bool:
        if self._inline_runner is not None:
            return self._inline_active
        return self.process is not None and self.process.poll() is None

    def status(self) -> str:
        if self._inline_runner is not None:
            return "active (inline)" if self._inline_active else "idle (inline)"
        if self.process is None:
            return "stopped"
        code = self.process.poll()
        if code is None:
            return f"running (pid {self.process.pid})"
        return f"exited (code {code})"


class Manager:
    def __init__(self, vm_port: int, exec_port: int, host: str) -> None:
        root = Path(__file__).resolve().parents[1]
        self.host = host
        self.vm_port = vm_port
        self.exec_port = exec_port
        shell_cmd, shell_inline_runner = self._build_shell_command(root, host, exec_port)
        self.components: Dict[str, ManagedProcess] = {
            "vm": ManagedProcess(
                "vm",
                [sys.executable, str(root / "platforms" / "python" / "host_vm.py"), "--listen", str(vm_port)],
                cwd=root,
            ),
            "exec": ManagedProcess(
                "exec",
                [
                    sys.executable,
                    str(root / "python" / "execd.py"),
                    "--vm-port",
                    str(vm_port),
                    "--listen",
                    str(exec_port),
                ],
                cwd=root,
            ),
            "shell": ManagedProcess(
                "shell",
                shell_cmd,
                cwd=root,
                inline_runner=shell_inline_runner,
            ),
        }
        if shell_inline_runner is not None:
            print("[shell] no external terminal detected; running inline shell in manager console")

    def start(self, targets: List[str]) -> None:
        for name in targets:
            proc = self.components.get(name)
            if not proc:
                print(f"unknown component '{name}'")
                continue
            if name == "exec" and not self.components["vm"].is_running:
                print("[exec] VM not running; starting VM first")
                self.components["vm"].start()
                time.sleep(0.5)
            proc.start()
            if name == "vm":
                if not self._wait_for_port(self.host, self.vm_port, "vm"):
                    print("[vm] start aborted; port did not open")
                    break
            elif name == "exec":
                if not self._wait_for_port(self.host, self.exec_port, "exec"):
                    print("[exec] start aborted; port did not open")
                    break

    def stop(self, targets: List[str]) -> None:
        for name in targets:
            proc = self.components.get(name)
            if not proc:
                continue
            proc.stop()

    def restart(self, targets: List[str]) -> None:
        ordering = [name for name in ["shell", "exec", "vm"] if name in targets]
        for name in ordering:
            self.stop([name])
        time.sleep(0.2)
        self.start(ordering[::-1])  # start VM first, then exec, etc.

    def status(self) -> None:
        for name, proc in self.components.items():
            print(f"  {name:<5} : {proc.status()}")

    def shell(self) -> None:
        self.components["shell"].start()

    def load(self, path: str) -> None:
        payload = {"cmd": "load", "path": str(Path(path).resolve())}
        resp = send_exec_request(self.host, self.exec_port, payload)
        print(json.dumps(resp, indent=2, sort_keys=True))

    def shutdown_all(self) -> None:
        for name in ["shell", "exec", "vm"]:
            self.stop([name])

    def run(self) -> None:
        print("HSX manager ready. Type 'help' for commands.")
        try:
            while True:
                try:
                    line = input("manager> ").strip()
                except EOFError:
                    print()
                    break
                if not line:
                    continue
                cmd, *args = shlex.split(line)
                cmd = cmd.lower()
                if cmd in {"quit", "exit"}:
                    break
                if cmd == "help":
                    print("Commands:")
                    print("  start [vm|exec|shell|console|all]")
                    print("  stop  [vm|exec|shell|console|all]")
                    print("  restart [vm|exec|shell|console|all]")
                    print("  status")
                    print("  load <path>  (send load command to exec)")
                    print("  shell        (spawn shell client)")
                    print("  quit/exit")
                    continue
                targets = self._resolve_targets(args)
                if cmd == "start":
                    self.start(targets)
                elif cmd == "stop":
                    self.stop(targets)
                elif cmd == "restart":
                    self.restart(targets)
                elif cmd == "status":
                    self.status()
                elif cmd == "load":
                    if not args:
                        print("usage: load <path>")
                    else:
                        self.load(args[0])
                elif cmd == "shell":
                    self.shell()
                else:
                    print(f"unknown command '{cmd}'")
        finally:
            self.shutdown_all()

    def _resolve_targets(self, args: List[str]) -> List[str]:
        if not args or args == ["all"]:
            return ["vm", "exec", "shell"]
        result = []
        aliases = {"console": "shell"}
        for name in args:
            lower = name.lower()
            lower = aliases.get(lower, lower)
            if lower in {"vm", "exec", "shell"}:
                result.append(lower)
            else:
                print(f"unknown target '{name}'")
        return result

    def _build_shell_command(
        self, root: Path, host: str, port: int
    ) -> tuple[List[str], Optional[Callable[[], None]]]:
        base_cmd = [
            sys.executable,
            str(root / "python" / "shell_client.py"),
            "--host",
            host,
            "--port",
            str(port),
        ]
        inline_runner: Optional[Callable[[], None]] = None
        if os.name == "posix":
            configured = os.environ.get("HSX_SHELL_TERMINAL")
            candidates: List[List[str]] = []
            if configured:
                candidates.append(shlex.split(configured))
            for program in ("x-terminal-emulator", "xterm"):
                path = shutil.which(program)
                if path:
                    candidates.append([path])
            for prefix in candidates:
                cmd = prefix + ["-e"] + base_cmd
                return cmd, None
            inline_runner = lambda: self._run_inline_shell(root, host, port)
        elif os.name == "nt":
            comspec = os.environ.get("COMSPEC")
            candidate = Path(comspec).expanduser() if comspec else None
            if not candidate or not candidate.exists():
                which_cmd = shutil.which("cmd.exe")
                candidate = Path(which_cmd) if which_cmd else None
            if not candidate or not candidate.exists():
                inline_runner = lambda: self._run_inline_shell(root, host, port)
        return base_cmd, inline_runner

    def _run_inline_shell(self, root: Path, host: str, port: int) -> None:
        try:
            import shell_client
        except ImportError as exc:  # pragma: no cover - import guard
            print(f"[shell] unable to import shell_client: {exc}")
            return
        shell_client.cmd_loop(host, port, cwd=root)

    def _wait_for_port(self, host: str, port: int, name: str, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        last_error: Optional[Exception] = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    return True
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
        message = f"[{name}] timed out waiting for TCP port {port} on {host} ({timeout:.1f}s)"
        if last_error:
            message += f": {last_error}"
        print(message)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="HSX process manager")
    parser.add_argument("--vm-port", type=int, default=DEFAULT_VM_PORT)
    parser.add_argument("--exec-port", type=int, default=DEFAULT_EXEC_PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    manager = Manager(args.vm_port, args.exec_port, args.host)
    manager.run()


if __name__ == "__main__":
    import json

    main()
