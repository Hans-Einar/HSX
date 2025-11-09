import json
from pathlib import Path

from python.hsx_dap import SymbolMapper


def test_symbol_mapper_matches_directory_and_filename(tmp_path):
    payload = {
        "instructions": [
            {
                "file": "src/foo.c",
                "directory": "/work/tree",
                "line": 12,
                "pc": 64,
            },
            {
                "file": "src/foo.c",
                "directory": "/work/tree",
                "line": 12,
                "pc": 68,
            },
            {
                "file": "drivers/bar.c",
                "directory": "/work/tree",
                "line": 3,
                "pc": 96,
            },
        ]
    }
    sym_path = tmp_path / "test.sym"
    sym_path.write_text(json.dumps(payload), encoding="utf-8")

    mapper = SymbolMapper(sym_path)

    assert mapper.lookup("/work/tree/src/foo.c", 12) == [64, 68]
    # filename-only lookup should still succeed
    assert mapper.lookup("foo.c", 12) == [64, 68]
    assert mapper.lookup(Path("/work/tree/drivers/bar.c"), 3) == [96]


def test_symbol_mapper_handles_windows_paths(tmp_path):
    payload = {
        "instructions": [
            {
                "file": r"src\main.c",
                "directory": r"C:\projects\hsx",
                "line": 7,
                "pc": 4,
            }
        ]
    }
    sym_path = tmp_path / "win.sym"
    sym_path.write_text(json.dumps(payload), encoding="utf-8")

    mapper = SymbolMapper(sym_path)
    assert mapper.lookup(r"C:\projects\hsx\src\main.c", 7) == [4]
    assert mapper.lookup("src/main.c", 7) == [4]
