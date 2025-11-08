import importlib.util
import json
from pathlib import Path

from python import asm as hsx_asm
from python import hld as hsx_linker
from platforms.python.host_vm import MiniVM, load_hxe


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def compile_to_hxo(ir: str, path: Path):
    asm_text = HSX_LLC.compile_ll_to_mvasm(ir, trace=False)
    lines = [line + "\n" for line in asm_text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        lines,
        for_object=True,
    )
    hsx_asm.write_hxo_object(
        path,
        code_words=code,
        rodata=rodata,
        entry=entry or 0,
        entry_symbol=entry_symbol,
        externs=externs,
        imports_decl=imports_decl,
        relocs=relocs,
        exports=exports,
        local_symbols=local_symbols,
        metadata=hsx_asm.LAST_METADATA,
    )
    return path


def compile_to_hxo_with_debug(ir: str, base_name: str, tmp_path: Path):
    asm_text = HSX_LLC.compile_ll_to_mvasm(ir, trace=False)
    dbg_data = HSX_LLC.LAST_DEBUG_INFO
    lines = [line + "\n" for line in asm_text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        lines,
        for_object=True,
    )
    hxo_path = tmp_path / f"{base_name}.hxo"
    hsx_asm.write_hxo_object(
        hxo_path,
        code_words=code,
        rodata=rodata,
        entry=entry or 0,
        entry_symbol=entry_symbol,
        externs=externs,
        imports_decl=imports_decl,
        relocs=relocs,
        exports=exports,
        local_symbols=local_symbols,
        metadata=hsx_asm.LAST_METADATA,
    )
    dbg_path = tmp_path / f"{base_name}.dbg"
    dbg_path.write_text(json.dumps(dbg_data, indent=2), encoding="utf-8")
    return hxo_path, dbg_path


def test_link_two_objects(tmp_path):
    foo_ir = """define dso_local i32 @foo() {\nentry:\n  ret i32 7\n}\n"""
    main_ir = """declare i32 @foo()\n\ndefine dso_local i32 @main() {\nentry:\n  %v = call i32 @foo()\n  ret i32 %v\n}\n"""
    foo_obj = compile_to_hxo(foo_ir, tmp_path / "foo.hxo")
    main_obj = compile_to_hxo(main_ir, tmp_path / "main.hxo")
    output = tmp_path / "linked.hxe"
    hsx_linker.link_objects([foo_obj, main_obj], output)
    header, code_bytes, rodata = load_hxe(output)
    vm = MiniVM(code_bytes, entry=header["entry"], rodata=rodata)
    while vm.running:
        vm.step()
    assert vm.regs[0] == 7


def test_emit_sym_generates_symbol_file(tmp_path):
    ir = """
    declare void @llvm.dbg.declare(metadata, metadata, metadata)
    declare void @llvm.dbg.value(metadata, metadata, metadata)

    define dso_local i32 @main(i32 %arg) !dbg !10 {
    entry:
      %val = alloca i32, align 4, !dbg !12
      call void @llvm.dbg.declare(metadata ptr %val, metadata !16, metadata !DIExpression()), !dbg !12
      store i32 %arg, ptr %val, align 4, !dbg !13
      %load = load i32, ptr %val, align 4, !dbg !14
      call void @llvm.dbg.value(metadata i32 %load, metadata !16, metadata !DIExpression()), !dbg !14
      ret i32 %load, !dbg !15
    }

    !0 = distinct !DICompileUnit(language: DW_LANG_C, file: !11, producer: "hsx", isOptimized: false, runtimeVersion: 0, emissionKind: FullDebug)
    !10 = distinct !DISubprogram(name: "main", linkageName: "main", scope: !11, file: !11, line: 1, scopeLine: 1, unit: !0, retainedNodes: !{})
    !11 = !DIFile(filename: "test.c", directory: "/project")
    !12 = !DILocation(line: 2, column: 3, scope: !10)
    !13 = !DILocation(line: 3, column: 3, scope: !10)
    !14 = !DILocation(line: 4, column: 3, scope: !10)
    !15 = !DILocation(line: 5, column: 3, scope: !10)
    !16 = !DILocalVariable(name: "tmp", scope: !10, file: !11, line: 2, type: !17)
    !17 = !DIBasicType(name: "int", size: 32, encoding: DW_ATE_signed)
    """.strip()

    hxo_path, dbg_path = compile_to_hxo_with_debug(ir, "dbg", tmp_path)
    hxe_path = tmp_path / "app.hxe"
    sym_path = tmp_path / "app.sym"

    result = hsx_linker.link_objects(
        [hxo_path],
        hxe_path,
        debug_infos=[dbg_path],
        emit_sym=sym_path,
        app_name="dbgapp",
    )

    assert sym_path.exists()
    sym_data = json.loads(sym_path.read_text())
    assert sym_data["version"] == 1
    assert sym_data["hxe_crc"] == result["crc"]
    functions = sym_data["symbols"]["functions"]
    assert functions
    fn_entry = functions[0]
    assert fn_entry["name"] == "main"
    assert fn_entry["file"] == "test.c"
    assert "address" in fn_entry and "size" in fn_entry
    instructions = sym_data.get("instructions", [])
    assert any(inst.get("line") == 5 and inst.get("ordinal") is not None for inst in instructions)
    assert any(inst.get("source_kind") == "source" for inst in instructions)
    assert any(inst.get("source_kind") == "compiler" for inst in instructions)
    assert isinstance(sym_data["symbols"].get("variables"), list)
    locals_section = sym_data["symbols"].get("locals") or []
    assert locals_section, "expected locals section populated"
    local_entry = locals_section[0]
    assert local_entry.get("name") == "tmp"
    assert local_entry.get("locations"), "expected local variable ranges"
    assert sym_data["memory_regions"], "expected memory region metadata"
