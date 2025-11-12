#!/usr/bin/env python3
"""Wrapper that ensures the repo root is on sys.path before running hsx_dap.main."""

from __future__ import annotations

import os
import pathlib
import sys
from typing import Iterable


def _iter_candidate_roots() -> Iterable[pathlib.Path]:
    yield pathlib.Path(__file__).resolve().parents[2]
    for env_key in ("HSX_REPO_ROOT", "HSX_WORKSPACE_ROOT"):
        env_value = os.environ.get(env_key)
        if env_value:
            yield pathlib.Path(env_value)


def _bootstrap_paths() -> None:
    visited = set()
    for candidate in _iter_candidate_roots():
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in visited:
            continue
        visited.add(resolved)
        python_dir = resolved / "python"
        if python_dir.is_dir():
            sys.path.insert(0, str(resolved))
            sys.path.insert(0, str(python_dir))
            print(f"[hsx-dap] Using repo root {resolved}", flush=True)
            return
    raise RuntimeError(
        "Unable to locate HSX python modules. Set HSX_REPO_ROOT to your workspace path.",
    )


def main() -> int:
    print("hsx-dap argv:", sys.argv, flush=True)
    _bootstrap_paths()
    from python.hsx_dap import main as dap_main  # noqa: WPS433

    return dap_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
