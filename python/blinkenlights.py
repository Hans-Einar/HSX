#!/usr/bin/env python3
"""HSX Blinkenlights control panel (pygame prototype).

Launches a pygame window that connects to the HSX executive JSON RPC
interface (same protocol as `python/shell_client.py`). Each running task is
displayed in a scrollable list with register readouts and per-task controls.
"""

import argparse
import json
import socket
import sys
import time
from typing import Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:  # pragma: no cover - tkinter optional
    tk = None

try:
    import pygame
except ImportError:  # pragma: no cover - pygame optional
    pygame = None


class ShellRPC:
    """Minimal persistent JSON-RPC client for the executive server."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.rfile = None
        self.wfile = None
        self.current_pid: Optional[int] = None

    def close(self) -> None:
        if self.rfile:
            try:
                self.rfile.close()
            finally:
                self.rfile = None
        if self.wfile:
            try:
                self.wfile.close()
            finally:
                self.wfile = None
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _connect(self) -> None:
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock = sock
        self.rfile = sock.makefile("r", encoding="utf-8", newline="\n")
        self.wfile = sock.makefile("w", encoding="utf-8", newline="\n")

    def request(self, payload: Dict[str, object]) -> Dict[str, object]:
        if self.sock is None:
            self._connect()
        assert self.wfile and self.rfile
        try:
            payload = dict(payload)
            payload.setdefault("version", 1)
            data = json.dumps(payload, separators=(",", ":"))
            self.wfile.write(data + "\n")
            self.wfile.flush()
            line = self.rfile.readline()
            if not line:
                raise RuntimeError("connection closed")
            resp = json.loads(line)
        except (OSError, json.JSONDecodeError):
            self._connect()
            data = json.dumps(payload, separators=(",", ":"))
            self.wfile.write(data + "\n")
            self.wfile.flush()
            line = self.rfile.readline()
            if not line:
                raise RuntimeError("connection closed")
            resp = json.loads(line)
        if resp.get("status") != "ok":
            raise RuntimeError(str(resp.get("error", "exec error")))
        return resp

    def info(self) -> Dict[str, object]:
        return self.request({"cmd": "info"}).get("info", {})

    def ps(self) -> List[Dict[str, object]]:
        response = self.request({"cmd": "ps"}).get("tasks", {})
        if isinstance(response, dict):
            self.current_pid = response.get("current_pid")
            return response.get("tasks", [])
        return response

    def dumpregs(self, pid: int) -> Dict[str, object]:
        return self.request({"cmd": "dumpregs", "pid": pid}).get("registers", {})

    def pause(self, pid: int) -> None:
        self.request({"cmd": "pause", "pid": pid})

    def resume(self, pid: int) -> None:
        self.request({"cmd": "resume", "pid": pid})

    def kill(self, pid: int) -> None:
        self.request({"cmd": "kill", "pid": pid})

    def clock_status(self) -> Dict[str, object]:
        return self.request({"cmd": "clock"}).get("clock", {})

    def clock_start(self) -> Dict[str, object]:
        return self.request({"cmd": "clock", "op": "start"}).get("clock", {})

    def clock_stop(self) -> Dict[str, object]:
        return self.request({"cmd": "clock", "op": "stop"}).get("clock", {})

    def clock_step(self, steps: Optional[int] = None, pid: Optional[int] = None) -> Dict[str, object]:
        payload: Dict[str, object] = {"cmd": "clock", "op": "step"}
        if steps is not None:
            payload["steps"] = steps
        if pid is not None:
            payload["pid"] = pid
        return self.request(payload)

    def clock_rate(self, hz: float) -> Dict[str, object]:
        return self.request({"cmd": "clock", "op": "rate", "rate": hz}).get("clock", {})

    def attach(self) -> Dict[str, object]:
        return self.request({"cmd": "attach"}).get("info", {})

    def detach(self) -> Dict[str, object]:
        return self.request({"cmd": "detach"}).get("info", {})

    def load(self, path: str, verbose: bool = False) -> Dict[str, object]:
        payload = {"cmd": "load", "path": path}
        if verbose:
            payload["verbose"] = True
        return self.request(payload).get("image", {})


class Button:
    def __init__(self, rect: pygame.Rect, label: str, callback) -> None:
        self.rect = rect
        self.label = label
        self.callback = callback

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(surface, (70, 70, 70), self.rect, border_radius=6)
        pygame.draw.rect(surface, (120, 120, 120), self.rect, width=2, border_radius=6)
        text = font.render(self.label, True, (230, 230, 230))
        surface.blit(text, text.get_rect(center=self.rect.center))

    def handle(self, pos) -> bool:
        if self.rect.collidepoint(pos):
            self.callback()
            return True
        return False


class BlinkenlightsApp:
    SIDEBAR_WIDTH = 220
    TASK_HEIGHT = 150
    TASK_MARGIN = 12
    POLL_INTERVAL = 0.5

    def __init__(self, host: str, port: int, refresh: float) -> None:
        self.host = host
        self.port = port
        self.refresh = refresh
        self.rpc = ShellRPC(host, port)
        pygame.init()
        pygame.display.set_caption("HSX Blinkenlights")
        self.font = pygame.font.SysFont("Consolas", 16)
        self.small_font = pygame.font.SysFont("Consolas", 12)
        self.screen = pygame.display.set_mode((1100, 640))
        self.clock = pygame.time.Clock()
        self.running = True
        self.last_poll = 0.0
        self.scroll_offset = 0
        self.tasks: List[Dict[str, object]] = []
        self.task_regs: Dict[int, Dict[str, object]] = {}
        self.global_buttons: List[Button] = []
        self.sidebar_surface = pygame.Surface((self.SIDEBAR_WIDTH, self.screen.get_height()))
        self.status_message: str = ""
        self.status_timestamp: float = 0.0
        self.current_pid: Optional[int] = None
        self._build_sidebar()
        self._initial_attach()

    def _initial_attach(self) -> None:
        try:
            info = self.rpc.attach()
            program = info.get("program")
            if program:
                self.set_status(f"Attached to {program}")
            else:
                self.set_status("Attached")
        except RuntimeError as exc:
            self.set_status(f"Attach failed: {exc}")
        finally:
            self.manual_refresh()

    def _build_sidebar(self) -> None:
        btn_specs = [
            ("Attach", self._attach_cmd),
            ("Detach", self._detach_cmd),
            ("Load", self._load_cmd),
            ("Refresh", self.manual_refresh),
            ("Clock Start", self._clock_start_cmd),
            ("Clock Stop", self._clock_stop_cmd),
            ("Clock Step x100", lambda: self._clock_step_cmd(100)),
        ]
        top = 40
        for label, cb in btn_specs:
            rect = pygame.Rect(20, top, self.SIDEBAR_WIDTH - 40, 40)
            self.global_buttons.append(self._make_button(rect, label, cb))
            top += 55

    def _make_button(self, rect: pygame.Rect, label: str, callback) -> Button:
        def wrapped():
            try:
                result = callback()
                if result:
                    self.set_status(str(result))
                else:
                    self.set_status(f"{label} OK")
            except RuntimeError as exc:
                self.set_status(f"{label} failed: {exc}")
            self.manual_refresh()

        return Button(rect, label, wrapped)

    def _attach_cmd(self) -> None:
        info = self.rpc.attach()
        program = info.get("program")
        if program:
            return f"Attached to {program}"
        return "Attached"

    def _detach_cmd(self) -> None:
        self.rpc.detach()
        return "Detached"

    def _load_cmd(self) -> None:
        if tk is None:
            raise RuntimeError("tkinter not available for file dialog")
        root = tk.Tk()
        root.withdraw()
        try:
            path = filedialog.askopenfilename(title="Select HSX image", filetypes=[("HSX Executable", "*.hxe"), ("All files", "*.*")])
        finally:
            root.destroy()
        if not path:
            raise RuntimeError("load cancelled")
        info = self.rpc.load(path)
        return f"Loaded pid {info.get('pid')}"

    def _format_clock_summary(self, status: Dict[str, object]) -> str:
        if not status:
            return "Clock status unavailable"
        state = status.get("state", "unknown")
        mode = status.get("mode", "active")
        throttled = status.get("throttled")
        rate = status.get("rate_hz")
        if isinstance(rate, (int, float)) and rate and rate > 0:
            rate_text = f"{rate:g} Hz"
        else:
            rate_text = "unlimited"
        throttle_note = " throttled" if throttled else ""
        return f"Clock {state}/{mode}{throttle_note} ({rate_text})"

    def _clock_start_cmd(self) -> str:
        status = self.rpc.clock_start()
        return self._format_clock_summary(status)

    def _clock_stop_cmd(self) -> str:
        status = self.rpc.clock_stop()
        return self._format_clock_summary(status)

    def _clock_step_cmd(self, steps: int, pid: Optional[int] = None) -> str:
        resp = self.rpc.clock_step(steps, pid=pid)
        result = resp.get("result", {}) if isinstance(resp, dict) else {}
        executed = result.get("executed")
        executed_text = f"{executed}" if executed is not None else "?"
        clock = resp.get("clock", {}) if isinstance(resp, dict) else {}
        summary = self._format_clock_summary(clock if isinstance(clock, dict) else {})
        return f"{summary}; executed {executed_text} instruction(s)"

    def manual_refresh(self) -> None:
        self.last_poll = 0
        return "Refresh queued"

    def fetch_state(self) -> None:
        try:
            tasks = self.rpc.ps()
            regs_map: Dict[int, Dict[str, object]] = {}
            for task in tasks:
                pid = int(task.get("pid", -1))
                if pid < 0:
                    continue
                try:
                    regs_map[pid] = self.rpc.dumpregs(pid)
                except RuntimeError:
                    continue
            self.tasks = tasks
            self.task_regs = regs_map
            self.current_pid = self.rpc.current_pid
        except RuntimeError as exc:
            self.set_status(f"RPC error: {exc}")

    def draw_sidebar(self) -> None:
        self.sidebar_surface.fill((30, 30, 30))
        title = self.font.render("Controls", True, (255, 200, 120))
        self.sidebar_surface.blit(title, (20, 10))
        for button in self.global_buttons:
            button.draw(self.sidebar_surface, self.font)
        if self.status_message:
            status = self.small_font.render(self.status_message, True, (200, 220, 180))
            self.sidebar_surface.blit(status, (20, self.sidebar_surface.get_height() - 40))
        self.screen.blit(self.sidebar_surface, (0, 0))

    def draw_tasks(self) -> None:
        width = self.screen.get_width() - self.SIDEBAR_WIDTH
        task_area = pygame.Surface((width, self.screen.get_height()))
        task_area.fill((10, 10, 20))
        y = self.TASK_MARGIN - self.scroll_offset
        for task in self.tasks:
            pid = int(task.get("pid", -1))
            box = pygame.Rect(20, y, width - 40, self.TASK_HEIGHT)
            pygame.draw.rect(task_area, (40, 40, 60), box, border_radius=10)
            border_color = (200, 170, 60) if pid == self.current_pid else (100, 100, 140)
            pygame.draw.rect(task_area, border_color, box, width=2, border_radius=10)
            info = f"PID {pid} | {task.get('state')} | prio {task.get('priority', '?')} | q {task.get('quantum', '?')}"
            prog = task.get("program", "")
            text = self.font.render(info, True, (230, 230, 255))
            task_area.blit(text, (box.x + 12, box.y + 12))
            program_text = self.small_font.render(str(prog), True, (180, 180, 200))
            task_area.blit(program_text, (box.x + 12, box.y + 36))

            regs = self.task_regs.get(pid)
            if regs:
                reg_values = regs.get("regs", [])
                for idx, value in enumerate(reg_values[:8]):
                    self.draw_register(task_area, box.x + 12, box.y + 60 + idx * 10, idx, int(value))

            button_y = box.bottom - 40
            pause_rect = pygame.Rect(box.right - 240, button_y, 60, 28)
            resume_rect = pygame.Rect(box.right - 170, button_y, 70, 28)
            kill_rect = pygame.Rect(box.right - 90, button_y, 60, 28)
            self.draw_task_button(task_area, pause_rect, "Pause", lambda p=pid: self.rpc.pause(p))
            self.draw_task_button(task_area, resume_rect, "Resume", lambda p=pid: self.rpc.resume(p))
            self.draw_task_button(task_area, kill_rect, "Kill", lambda p=pid: self.rpc.kill(p))

            y += self.TASK_HEIGHT + self.TASK_MARGIN
        self.screen.blit(task_area, (self.SIDEBAR_WIDTH, 0))

    def draw_register(self, surface: pygame.Surface, x: int, y: int, idx: int, value: int) -> None:
        label = self.small_font.render(f"R{idx}: 0x{value & 0xFFFFFFFF:08X}", True, (200, 200, 220))
        surface.blit(label, (x, y))
        light_y = y + 14
        bit_width = 10
        spacing = 2
        value32 = value & 0xFFFFFFFF
        for bit in range(8):
            on = (value32 >> (7 - bit)) & 1
            color = (255, 120, 80) if on else (60, 60, 70)
            rect = pygame.Rect(x + bit * (bit_width + spacing), light_y, bit_width, 8)
            pygame.draw.rect(surface, color, rect)

    def draw_task_button(self, surface: pygame.Surface, rect: pygame.Rect, label: str, action) -> None:
        pygame.draw.rect(surface, (80, 80, 110), rect, border_radius=6)
        pygame.draw.rect(surface, (150, 150, 200), rect, width=2, border_radius=6)
        text = self.small_font.render(label, True, (240, 240, 240))
        surface.blit(text, text.get_rect(center=rect.center))
        # Store callback on rect for click handling
        self._task_buttons.append((rect.move(self.SIDEBAR_WIDTH, 0), label, action))

    def run(self) -> None:
        while self.running:
            now = time.monotonic()
            if now - self.last_poll > max(self.refresh, self.POLL_INTERVAL):
                self.fetch_state()
                self.last_poll = now
            if self.status_message and now - self.status_timestamp > 5.0:
                self.status_message = ""
            self._task_buttons: List[Tuple[pygame.Rect, str, object]] = []
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 4:  # scroll up
                        self.scroll_offset = max(self.scroll_offset - 30, 0)
                    elif event.button == 5:
                        self.scroll_offset += 30
                    else:
                        self.handle_click(event.pos)
            self.screen.fill((0, 0, 0))
            self.draw_sidebar()
            self.draw_tasks()
            pygame.display.flip()
            self.clock.tick(30)
        self.rpc.close()
        pygame.quit()

    def handle_click(self, pos) -> None:
        if pos[0] < self.SIDEBAR_WIDTH:
            for button in self.global_buttons:
                if button.handle(pos):
                    break
        else:
            for rect, label, cb in self._task_buttons:
                if rect.collidepoint(pos):
                    try:
                        cb()
                        self.set_status(f"{label} OK")
                    except RuntimeError as exc:
                        self.set_status(f"{label} failed: {exc}")
                    self.manual_refresh()
                    break

    def set_status(self, message: str) -> None:
        self.status_message = str(message)
        self.status_timestamp = time.monotonic()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HSX blinkenlights panel")
    parser.add_argument("--host", default="127.0.0.1", help="executive host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9998, help="executive port (default 9998)")
    parser.add_argument("--refresh", type=float, default=0.75, help="seconds between polls")
    args = parser.parse_args(argv)

    if pygame is None:
        print("pygame is required for blinkenlights; install with `pip install pygame`.", file=sys.stderr)
        return 1

    app = BlinkenlightsApp(args.host, args.port, args.refresh)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n[blinkenlights] exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
