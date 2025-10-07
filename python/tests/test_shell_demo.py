import os
import subprocess
import sys
from pathlib import Path


def test_shell_demo_runs(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    shell_dir = repo_root / "examples" / "demos" / "shell"

    env = os.environ.copy()
    env.setdefault("PYTHON", sys.executable)

    subprocess.run(["make", "-C", str(shell_dir), "clean"], check=True, env=env, capture_output=True, text=True)
    subprocess.run(["make", "-C", str(shell_dir)], check=True, env=env, capture_output=True, text=True)
    proc = subprocess.run(
        ["make", "-C", str(shell_dir), "run", "RUN_ARGS=--max-steps 5000"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "[UART.tx] Exec complete. Exit=" in proc.stdout
    assert "[UART.tx] 7" in proc.stdout
