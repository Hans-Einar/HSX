import os
import pathlib
import re
import subprocess
import sys


def test_half_main_runs():
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    examples_dir = repo_root / "examples" / "tests"
    env = os.environ.copy()
    env.setdefault("PYTHON", sys.executable)
    proc = subprocess.run(
        ["make", "-C", str(examples_dir), "run-test_ir_half_main"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )
    assert proc.returncode == 0, f"Make failed: {proc.stderr or proc.stdout}"
    combined = proc.stdout + proc.stderr
    match = re.search(r"R0\.\.R7:\s*\[([^\]]+)\]", combined)
    assert match, f"No register dump found in output: {combined}"
    regs = [int(x.strip()) for x in match.group(1).split(',')]
    assert regs[0] == 17152, f"Expected R0=17152 but got {regs[0]}"
