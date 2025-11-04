import importlib.util
import json
import subprocess
import textwrap
import sys
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc_debug", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def test_parse_ir_captures_debug_metadata():
    llvm_ir = textwrap.dedent(
        """
        ; ModuleID = 'sample'
        source_filename = "sample.c"

        define dso_local i32 @foo() !dbg !10 {
        entry:
          ret i32 0, !dbg !11
        }

        !10 = distinct !DISubprogram(name: "foo",
            linkageName: "foo",
            scope: !9,
            file: !12,
            line: 5,
            scopeLine: 5,
            unit: !1,
            retainedNodes: !{})
        !12 = !DIFile(filename: "sample.c",
            directory: "/tmp/project")
        !11 = !DILocation(line: 6, column: 3, scope: !10)
        """
    ).strip("\n")

    ir = HSX_LLC.parse_ir(llvm_ir.splitlines())
    debug = ir.get("debug", {})

    assert ir["functions"], "expected at least one parsed function"
    first_fn = ir["functions"][0]
    assert first_fn["name"] == "foo"
    assert first_fn.get("dbg") == "!10"

    files = debug.get("files", {})
    assert "!12" in files
    file_info = files["!12"]
    assert file_info["filename"] == "sample.c"
    assert file_info["directory"] == "/tmp/project"

    subprograms = debug.get("subprograms", {})
    assert "!10" in subprograms
    sub = subprograms["!10"]
    assert sub["name"] == "foo"
    assert sub["file"] == "!12"
    assert sub["line"] == 5

    debug_functions = debug.get("functions", [])
    assert len(debug_functions) == 1
    debug_entry = debug_functions[0]
    assert debug_entry["function"] == "foo"
    assert debug_entry["line"] == 5
    assert debug_entry["file"]["filename"] == "sample.c"


def test_compile_records_last_debug_info():
    llvm_ir = textwrap.dedent(
        """
        define dso_local i32 @foo() !dbg !1 {
        entry:
          ret i32 0, !dbg !2
        }

        !1 = distinct !DISubprogram(name: "foo", linkageName: "foo", file: !3, line: 4, scopeLine: 4, unit: !0, retainedNodes: !{})
        !2 = !DILocation(line: 5, column: 3, scope: !1)
        !3 = !DIFile(filename: "sample.c", directory: "/tmp/project")
        """
    ).strip("\n")

    HSX_LLC.compile_ll_to_mvasm(llvm_ir, trace=False)
    debug_info = HSX_LLC.LAST_DEBUG_INFO
    assert debug_info is not None
    assert debug_info.get("version") == 1
    assert debug_info["functions"]
    func = debug_info["functions"][0]
    assert func["function"] == "foo"
    assert isinstance(func["mvasm_start_line"], int) and func["mvasm_start_line"] >= 1
    assert isinstance(func["mvasm_end_line"], int) and func["mvasm_end_line"] >= func["mvasm_start_line"]
    assert isinstance(func.get("mvasm_start_ordinal"), int)
    assert isinstance(func.get("mvasm_end_ordinal"), int)
    line_map = debug_info.get("line_map")
    assert line_map, "expected instruction line map entries"
    assert line_map[0].get("mvasm_ordinal") is not None
    assert any(entry.get("source_line") == 5 for entry in line_map)
    llvm_map = debug_info.get("llvm_to_mvasm")
    assert llvm_map, "expected llvm_to_mvasm entries"
    entry = next((item for item in llvm_map if item.get("function") == "foo"), None)
    assert entry is not None
    assert entry.get("mvasm_lines"), "expected MVASM line coverage"
    assert entry.get("mvasm_ordinals"), "expected MVASM ordinal coverage"


def test_emit_debug_flag_writes_json(tmp_path):
    llvm_ir = textwrap.dedent(
        """
        define dso_local i32 @foo() !dbg !1 {
        entry:
          ret i32 0, !dbg !2
        }

        !1 = distinct !DISubprogram(name: "foo", linkageName: "foo", file: !3, line: 4, scopeLine: 4, unit: !0, retainedNodes: !{})
        !2 = !DILocation(line: 5, column: 3, scope: !1)
        !3 = !DIFile(filename: "sample.c", directory: "/tmp/project")
        """
    ).strip("\n")

    root = Path(__file__).resolve().parents[1]
    ir_path = tmp_path / "input.ll"
    asm_path = tmp_path / "output.asm"
    dbg_path = tmp_path / "output.dbg.json"
    ir_path.write_text(llvm_ir, encoding="utf-8")
    cmd = [
        sys.executable,
        str(root / "hsx-llc.py"),
        str(ir_path),
        "-o",
        str(asm_path),
        "--emit-debug",
        str(dbg_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr or result.stdout
    dbg_data = json.loads(dbg_path.read_text(encoding="utf-8"))
    assert dbg_data["version"] == 1
    assert dbg_data["functions"]
    emitted = dbg_data["functions"][0]
    assert emitted["function"] == "foo"
    assert isinstance(emitted["mvasm_start_line"], int) and emitted["mvasm_start_line"] >= 1
    assert isinstance(emitted["mvasm_end_line"], int) and emitted["mvasm_end_line"] >= emitted["mvasm_start_line"]
    assert dbg_data.get("line_map"), "expected line_map in emitted debug file"
    assert dbg_data["line_map"][0].get("mvasm_ordinal") is not None
    assert dbg_data.get("llvm_to_mvasm"), "expected llvm_to_mvasm mapping in debug file"
    assert dbg_data["llvm_to_mvasm"][0].get("mvasm_ordinals")
