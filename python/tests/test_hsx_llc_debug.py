import importlib.util
import textwrap
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
