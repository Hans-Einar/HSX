import importlib.util
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
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol = hsx_asm.assemble(lines)
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
    )
    return path


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
