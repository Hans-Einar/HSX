import pathlib
import re
import subprocess


def test_half_main_runs():
    root = pathlib.Path(__file__).resolve().parents[2]
    bat = root / "half_main.bat"
    proc = subprocess.run(
        ["cmd", "/c", str(bat)], capture_output=True, text=True
    )
    assert proc.returncode == 0, f"Batch failed: {proc.stderr or proc.stdout}"
    out = proc.stdout
    match = re.search(r"R0\.\.R7:\s*\[([^\]]+)\]", out)
    assert match, f"No register dump found in output: {out}"
    regs = [int(x.strip()) for x in match.group(1).split(',')]
    assert regs[0] == 8, f"Expected R0=8 but got {regs[0]}"
