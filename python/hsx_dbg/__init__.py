"""
hsx-dbg CLI package.

This package provides the interactive CLI debugger described in
main/04--Design/04.09--Debugger.md.  Use ``python -m hsx_dbg`` or
``python/hsx_dbg.py`` to launch the debugger.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
__version__ = "0.1.0"
