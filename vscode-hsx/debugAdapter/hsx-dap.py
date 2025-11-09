#!/usr/bin/env python3
"""Wrapper that ensures the repo root is on sys.path before running hsx_dap.main."""

from __future__ import annotations

import pathlib
import sys


def main() -> int:
    print("hsx-dap argv:", sys.argv, flush=True)
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from python.hsx_dap import main as dap_main  # noqa: WPS433

    return dap_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
