from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from platforms.python.host_vm import VMController

REPO_ROOT = Path(__file__).resolve().parents[2]
ASM_TOOL = REPO_ROOT / "python" / "asm.py"
EXAMPLES_DIR = REPO_ROOT / "examples" / "tests"
STDIO_SAMPLE = EXAMPLES_DIR / "test_stdio_mailbox_c"
PRODUCER_SAMPLE = EXAMPLES_DIR / "test_mailbox_producer_c"

CLANG_AVAILABLE = shutil.which("clang") is not None


def _build_hxe(source: Path, build_dir: Path) -> Path:
    if source.is_dir():
        target = Path("build") / source.name / "main.hxe"
        target_str = target.as_posix()
        env = os.environ.copy()
        env.setdefault("PYTHON", sys.executable)
        proc = subprocess.run(
            ["make", "-C", str(EXAMPLES_DIR), target_str],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"make failed: {proc.stderr or proc.stdout}")
        return EXAMPLES_DIR / target
    build_dir.mkdir(parents=True, exist_ok=True)
    output = build_dir / (source.stem + ".hxe")
    cmd = [sys.executable, str(ASM_TOOL), str(source), "-o", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"asm.py failed: {result.stderr or result.stdout}")
    return output


def _load_task(controller: VMController, image: Path) -> int:
    existing = set(controller.tasks.keys())
    controller.load_from_path(str(image))
    new_tasks = set(controller.tasks.keys()) - existing
    assert new_tasks, "no new task after load"
    return next(iter(new_tasks))


def test_stdio_puts(tmp_path):
    if not CLANG_AVAILABLE:
        pytest.skip("clang not installed; mailbox C samples cannot be built")
    image = _build_hxe(STDIO_SAMPLE, tmp_path)
    controller = VMController()
    pid = _load_task(controller, image)

    controller.step(400)

    stdout_handle = controller.mailbox_open(0, f"svc:stdio.out@{pid}").get("handle")
    collected: list[str] = []
    try:
        while True:
            resp = controller.mailbox_recv(0, stdout_handle, max_len=128)
            if resp["mbx_status"] != 0:
                break
            collected.append(resp.get("text", ""))
    finally:
        controller.mailbox_close(0, stdout_handle)

    combined = "".join(collected)
    assert "hello from hsx stdio" in combined


def test_producer_mailbox_message(tmp_path):
    if not CLANG_AVAILABLE:
        pytest.skip("clang not installed; mailbox C samples cannot be built")
    producer_img = _build_hxe(PRODUCER_SAMPLE, tmp_path)

    controller = VMController()
    pid_producer = _load_task(controller, producer_img)
    controller.step(200)

    host_open = controller.mailbox_open(0, "app:demo")
    handle_id = host_open.get("handle")
    try:
        recv = controller.mailbox_recv(0, handle_id, max_len=64)
    finally:
        controller.mailbox_close(0, handle_id)

    assert recv["mbx_status"] == 0
    assert "ping from producer" in recv.get("text", "")
