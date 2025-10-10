#!/usr/bin/env python3
from __future__ import annotations
"""Helper invoked from Makefile to assemble/link HSX test samples.

This wrapper keeps the Makefile portable across shells by avoiding
shell-specific loops or variable assignments.
"""


import argparse
import subprocess
import sys
from pathlib import Path
from typing import List


def run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)


def build(main_mvasm: Path, output: Path, asm_tool: Path, linker_tool: Path, extras: List[Path]) -> None:
    python_exe = Path(sys.executable)
    if extras:
        main_obj = output.with_suffix('.hxo')
        run([str(python_exe), str(asm_tool), str(main_mvasm), '--emit-hxo', '-o', str(main_obj)])
        extra_objs = []
        build_dir = output.parent
        for lib in extras:
            obj = build_dir / (lib.stem + '.hxo')
            run([str(python_exe), str(asm_tool), str(lib), '--emit-hxo', '-o', str(obj)])
            extra_objs.append(str(obj))
        run([str(python_exe), str(linker_tool), '-o', str(output), *extra_objs, str(main_obj)])
    else:
        run([str(python_exe), str(asm_tool), str(main_mvasm), '-o', str(output)])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--main', dest='main_mvasm', required=True)
    parser.add_argument('--out', dest='output', required=True)
    parser.add_argument('--asm', dest='asm_tool', required=True)
    parser.add_argument('--linker', dest='linker_tool', required=True)
    parser.add_argument('--extra', dest='extras', action='append', default=[])
    args = parser.parse_args()

    main_mvasm = Path(args.main_mvasm)
    output = Path(args.output)
    asm_tool = Path(args.asm_tool)
    linker_tool = Path(args.linker_tool)
    extras = [Path(x) for x in args.extras if x]

    build(main_mvasm, output, asm_tool, linker_tool, extras)


if __name__ == '__main__':
    main()
