#!/usr/bin/env python3
"""HSX Blinkenlights control panel (pygame prototype).

Launches a pygame window that connects to the HSX executive JSON RPC
interface (same protocol as `python/shell_client.py`). Each running task is
displayed in a scrollable list with register readouts and per-task controls.
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Tuple

from executive_session import ExecutiveSession, ExecutiveSessionError

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:  # pragma: no cover - tkinter optional
    tk = None

try:
    import pygame
except ImportError:  # pragma: no cover - pygame optional
    pygame = None


_EVENT_FILTER = {
    "categories": [
        "debug_break",
        "scheduler",
        "mailbox_wait",
        "mailbox_wake",
        "mailbox_timeout",
        "mailbox_error",
        "warning",
    ]
}


class ShellRPC:
    """Session-aware wrapper for the executive RPC server."""

    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.session = ExecutiveSession(
            host,
            port,
            client_name="hsx-blinkenlights",
            features=["events", "stack", "symbols", "disasm"],
            max_events=512,
            timeout=timeout,
            event_buffer=512,
        )
        # Start streaming non-trace events so the UI can poll the buffer.
        self.session.start_event_stream(filters=_EVENT_FILTER, callback=None, ack_interval=10)
        self.current_pid: Optional[int] = None

    def close(self) -> None:
        self.session.close()

    def request(self, payload: Dict[str, object]) -> Dict[str, object]:
        response = self.session.request(payload)
        if response.get("status") != "ok":
            raise RuntimeError(str(response.get("error", "exec error")))
        return response

    def recent_events(self, limit: int = 20) -> List[Dict[str, object]]:
        return self.session.get_recent_events(limit)

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

    def stack_info(self, pid: int, *, max_frames: int = 6, refresh: bool = True) -> Dict[str, object]:
        try:
            info = self.session.stack_info(pid, max_frames=max_frames, refresh=refresh)
        except ExecutiveSessionError as exc:
            raise RuntimeError(str(exc)) from exc
        if not info:
            return {}
        return info


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
    TASK_HEIGHT = 230
    TASK_MARGIN = 12
    POLL_INTERVAL = 0.5
    STACK_SUMMARY_COUNT = 4
    STACK_DETAIL_COUNT = 8
    STACK_MAX_FRAMES = 16

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
        self.task_stacks: Dict[int, Dict[str, object]] = {}
        self.stack_state: Dict[int, Dict[str, object]] = {}
        self._stack_click_targets: List[Tuple[pygame.Rect, int, int]] = []
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

    def toggle_stack(self, pid: int) -> str:
        state = self.stack_state.setdefault(pid, {"expanded": False, "offset": 0, "selected": 0})
        expanded = bool(state.get("expanded"))
        if expanded:
            state["expanded"] = False
            state["offset"] = 0
            state["selected"] = 0
            self.last_poll = 0
            return f"Stack collapsed for pid {pid}"
        try:
            info = self.rpc.stack_info(pid, max_frames=self.STACK_MAX_FRAMES, refresh=True)
        except RuntimeError as exc:
            return f"Stack fetch failed: {exc}"
        if info:
            self.task_stacks[pid] = info
        state["expanded"] = True
        state["offset"] = 0
        state["selected"] = 0
        self.last_poll = 0
        return f"Stack expanded for pid {pid}"

    def scroll_stack(self, pid: int, delta: int) -> str:
        state = self.stack_state.get(pid)
        stack = self.task_stacks.get(pid)
        if not state or not state.get("expanded") or not stack:
            return "No stack to scroll"
        frames = stack.get("frames") or []
        if not frames:
            return "No stack to scroll"
        current = int(state.get("offset", 0))
        target = current + delta
        max_offset = max(0, len(frames) - self.STACK_DETAIL_COUNT)
        target = max(0, min(max_offset, target))
        if target == current:
            if delta < 0 and current == 0:
                return "Top of stack"
            if delta > 0 and current == max_offset:
                return "End of captured stack"
            return "Stack unchanged"
        state["offset"] = target
        selected = int(state.get("selected", 0))
        if selected < target:
            state["selected"] = target
        elif selected >= target + self.STACK_DETAIL_COUNT:
            state["selected"] = min(target + self.STACK_DETAIL_COUNT - 1, len(frames) - 1)
        self.last_poll = 0
        direction = "up" if delta < 0 else "down"
        return f"Stack scrolled {direction} (offset {target})"

    def select_stack_frame(self, pid: int, frame_idx: int) -> str:
        state = self.stack_state.setdefault(pid, {"expanded": False, "offset": 0, "selected": 0})
        frames = self.task_stacks.get(pid, {}).get("frames") or []
        if not state.get("expanded"):
            message = self.toggle_stack(pid)
            if not state.get("expanded"):
                return message or "Stack unavailable"
            frames = self.task_stacks.get(pid, {}).get("frames") or []
            if not frames:
                return "Stack unavailable"
        if not frames:
            return "Stack unavailable"
        frame_idx = max(0, min(int(frame_idx), len(frames) - 1))
        state["selected"] = frame_idx
        offset = int(state.get("offset", 0))
        if frame_idx < offset:
            offset = frame_idx
        elif frame_idx >= offset + self.STACK_DETAIL_COUNT:
            offset = max(0, frame_idx - self.STACK_DETAIL_COUNT + 1)
        max_offset = max(0, len(frames) - self.STACK_DETAIL_COUNT)
        state["offset"] = max(0, min(offset, max_offset))
        self.last_poll = 0
        return f"Stack frame {frame_idx} selected"

    def fetch_state(self) -> None:
        try:
            tasks = self.rpc.ps()
            regs_map: Dict[int, Dict[str, object]] = {}
            stacks_map: Dict[int, Dict[str, object]] = {}
            visible_pids: set[int] = set()
            for task in tasks:
                pid = int(task.get("pid", -1))
                if pid < 0:
                    continue
                visible_pids.add(pid)
                state = self.stack_state.setdefault(pid, {"expanded": False, "offset": 0, "selected": 0})
                try:
                    regs_map[pid] = self.rpc.dumpregs(pid)
                except RuntimeError:
                    regs_map.pop(pid, None)
                refresh_stack = bool(state.get("expanded"))
                try:
                    stack = self.rpc.stack_info(pid, max_frames=self.STACK_MAX_FRAMES, refresh=refresh_stack)
                    if not stack:
                        stack = self.rpc.stack_info(pid, max_frames=self.STACK_MAX_FRAMES, refresh=False)
                except RuntimeError:
                    stack = {}
                if stack:
                    frames = stack.get("frames") or []
                    stacks_map[pid] = stack
                    if frames:
                        max_offset = max(0, len(frames) - self.STACK_DETAIL_COUNT)
                        state["offset"] = max(0, min(int(state.get("offset", 0)), max_offset))
                        selected = int(state.get("selected", 0))
                        if selected >= len(frames):
                            selected = len(frames) - 1
                        state["selected"] = max(0, selected)
                    else:
                        state["offset"] = 0
                        state["selected"] = 0
                elif pid in self.task_stacks:
                    stacks_map[pid] = self.task_stacks[pid]
                    state["offset"] = 0
                    state["selected"] = 0
            self.tasks = tasks
            self.task_regs = regs_map
            self.task_stacks = stacks_map
            self.current_pid = self.rpc.current_pid
            for stale_pid in list(self.stack_state.keys()):
                if stale_pid not in visible_pids:
                    self.stack_state.pop(stale_pid, None)
                    self.task_stacks.pop(stale_pid, None)
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
            self.draw_stack(task_area, box, pid)

            state = self.stack_state.get(pid, {"expanded": False, "offset": 0, "selected": 0})
            expanded = bool(state.get("expanded"))
            stack_frames = self.task_stacks.get(pid, {}).get("frames") or []
            stack_button_label = "Stack+" if not expanded else "Stack-"
            button_specs = [
                ("Pause", 68, lambda p=pid: self.rpc.pause(p)),
                ("Resume", 72, lambda p=pid: self.rpc.resume(p)),
                (stack_button_label, 72, lambda p=pid: self.toggle_stack(p)),
                ("Kill", 60, lambda p=pid: self.rpc.kill(p)),
            ]
            if expanded and stack_frames and len(stack_frames) > self.STACK_DETAIL_COUNT:
                button_specs.append(("S▲", 40, lambda p=pid: self.scroll_stack(p, -1)))
                button_specs.append(("S▼", 40, lambda p=pid: self.scroll_stack(p, 1)))

            spacing = 8
            total_width = sum(width for _, width, _ in button_specs) + spacing * (len(button_specs) - 1)
            start_x = max(box.x + 12, box.right - total_width - 12)
            button_y = box.bottom - 40
            for label, width, callback in button_specs:
                rect = pygame.Rect(start_x, button_y, width, 28)
                self.draw_task_button(task_area, rect, label, callback)
                start_x += width + spacing

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

    def draw_stack(self, surface: pygame.Surface, box: pygame.Rect, pid: int) -> None:
        state = self.stack_state.setdefault(pid, {"expanded": False, "offset": 0, "selected": 0})
        stack = self.task_stacks.get(pid)
        stack_x = box.x + 210
        stack_y = box.y + 60
        header = self.small_font.render("Stack:", True, (200, 210, 240))
        surface.blit(header, (stack_x, stack_y - 14))

        if not stack:
            message = "stack unsupported" if not self.rpc.session.supports_stack() else "(no stack data yet)"
            rendered = self.small_font.render(message, True, (180, 180, 200))
            surface.blit(rendered, (stack_x, stack_y))
            return

        frames = stack.get("frames") or []
        if not frames:
            rendered = self.small_font.render("(stack empty)", True, (180, 180, 200))
            surface.blit(rendered, (stack_x, stack_y))
            return

        line_height = 14
        expanded = bool(state.get("expanded"))
        max_visible = self.STACK_DETAIL_COUNT if expanded else self.STACK_SUMMARY_COUNT
        offset = int(state.get("offset", 0)) if expanded else 0
        max_offset = max(0, len(frames) - max_visible)
        if offset > max_offset:
            offset = max_offset
            state["offset"] = offset
        frames_slice = frames[offset: offset + max_visible]
        y_cursor = stack_y
        selected_idx = int(state.get("selected", 0))
        if selected_idx < 0 or selected_idx >= len(frames):
            selected_idx = 0
            state["selected"] = selected_idx

        for local_idx, frame in enumerate(frames_slice):
            actual_idx = offset + local_idx
            pc = int(frame.get("pc", 0))
            func = frame.get("func_name")
            if not func:
                symbol = frame.get("symbol")
                if isinstance(symbol, dict):
                    func = symbol.get("name")
            if not func:
                func = f"0x{pc & 0xFFFF:04X}"
            offset_val = frame.get("func_offset")
            if isinstance(offset_val, int) and offset_val:
                func_label = f"{func}+0x{offset_val:X}"
            else:
                func_label = func
            line_top = y_cursor
            primary_line = f"[{actual_idx:02}] {func_label} @ 0x{pc & 0xFFFF:04X}"
            highlight = actual_idx == selected_idx
            primary_color = (255, 240, 200) if highlight else ((255, 220, 160) if actual_idx == 0 else (210, 210, 220))
            primary_render = self.small_font.render(primary_line, True, primary_color)
            surface.blit(primary_render, (stack_x, y_cursor))
            clickable_width = max(120, box.right - stack_x - 12)
            line_rect = pygame.Rect(stack_x, line_top, clickable_width, line_height)
            self._stack_click_targets.append((line_rect, pid, actual_idx))
            y_cursor += line_height

            if expanded:
                detail_parts = []
                line_info = frame.get("line")
                if isinstance(line_info, dict):
                    file = line_info.get("file")
                    line_no = line_info.get("line")
                    if file and line_no is not None:
                        detail_parts.append(f"{file}:{line_no}")
                    elif file:
                        detail_parts.append(file)
                    elif line_no is not None:
                        detail_parts.append(f"line {line_no}")
                ret_pc = frame.get("return_pc")
                if isinstance(ret_pc, int) and ret_pc:
                    detail_parts.append(f"ret 0x{ret_pc & 0xFFFF:04X}")
                sp_val = frame.get("sp")
                if isinstance(sp_val, int):
                    detail_parts.append(f"sp 0x{sp_val & 0xFFFFFFFF:08X}")
                details_text = "; ".join(detail_parts)
                if details_text:
                    detail_render = self.small_font.render(f"    {details_text}", True, (180, 190, 210))
                    surface.blit(detail_render, (stack_x, y_cursor))
                    y_cursor += line_height

        truncated = bool(stack.get("truncated"))
        errors = stack.get("errors") or []
        if truncated:
            truncated_render = self.small_font.render("… truncated …", True, (235, 180, 120))
            surface.blit(truncated_render, (stack_x, y_cursor))
            y_cursor += line_height
        for err in errors[:2]:
            err_render = self.small_font.render(f"warn: {err}", True, (235, 160, 120))
            surface.blit(err_render, (stack_x, y_cursor))
            y_cursor += line_height
        if expanded and len(frames) > max_visible:
            range_text = f"Showing {offset + 1}-{offset + len(frames_slice)} of {len(frames)}"
            range_render = self.small_font.render(range_text, True, (190, 200, 215))
            surface.blit(range_render, (stack_x, y_cursor))
            y_cursor += line_height
        if expanded and frames:
            selected_frame = frames[selected_idx]
            summary_parts = []
            sp_val = selected_frame.get("sp")
            fp_val = selected_frame.get("fp")
            if isinstance(sp_val, int):
                summary_parts.append(f"sp=0x{sp_val & 0xFFFFFFFF:08X}")
            if isinstance(fp_val, int):
                summary_parts.append(f"fp=0x{fp_val & 0xFFFFFFFF:08X}")
            ret_pc = selected_frame.get("return_pc")
            if isinstance(ret_pc, int) and ret_pc:
                summary_parts.append(f"ret=0x{ret_pc & 0xFFFF:04X}")
            if summary_parts:
                selected_render = self.small_font.render(f"Selected frame: {'; '.join(summary_parts)}", True, (215, 225, 200))
                surface.blit(selected_render, (stack_x, y_cursor))

    def run(self) -> None:
        while self.running:
            now = time.monotonic()
            if now - self.last_poll > max(self.refresh, self.POLL_INTERVAL):
                self.fetch_state()
                self.last_poll = now
            if self.status_message and now - self.status_timestamp > 5.0:
                self.status_message = ""
            self._task_buttons: List[Tuple[pygame.Rect, str, object]] = []
            self._stack_click_targets = []
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
            handled = False
            for rect, label, cb in self._task_buttons:
                if rect.collidepoint(pos):
                    try:
                        result = cb()
                        if result:
                            self.set_status(str(result))
                        else:
                            self.set_status(f"{label} OK")
                    except RuntimeError as exc:
                        self.set_status(f"{label} failed: {exc}")
                    self.manual_refresh()
                    handled = True
                    break
            if not handled:
                for rect, pid, frame_idx in self._stack_click_targets:
                    if rect.collidepoint(pos):
                        message = self.select_stack_frame(pid, frame_idx)
                        if message:
                            self.set_status(message)
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
