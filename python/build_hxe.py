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
    """Build HXE by assembling to objects and linking.
    
    Following standard toolchain practice:
    1. Assembler always emits .hxo object files
    2. Linker always creates .hxe executables from object files
    
    This ensures a single, consistent path for HXE creation.
    """
    python_exe = Path(sys.executable)
    build_dir = output.parent
    
    # Assemble main file to object
    main_obj = build_dir / (main_mvasm.stem + '.hxo')
    run([str(python_exe), str(asm_tool), str(main_mvasm), '-o', str(main_obj)])
    
    # Assemble extra libraries to objects
    extra_objs = []
    for lib in extras:
        obj = build_dir / (lib.stem + '.hxo')
        run([str(python_exe), str(asm_tool), str(lib), '-o', str(obj)])
        extra_objs.append(str(obj))
    
    # Link all objects into final executable
    run([str(python_exe), str(linker_tool), '-o', str(output), *extra_objs, str(main_obj)])


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
