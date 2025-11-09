import importlib.util
from pathlib import Path

from python import asm as hsx_asm
from python import hld as hsx_linker
from platforms.python.host_vm import load_hxe


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc_stdlib", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()
STDLIB_PATH = Path(__file__).resolve().parents[2] / "lib" / "hsx_std" / "stdlib.mvasm"


def _assemble_to_hxo(source_text: str, path: Path) -> Path:
    lines = [line + "\n" for line in source_text.splitlines()]
    (
        code,
        entry,
        externs,
        imports_decl,
        rodata,
        relocs,
        exports,
        entry_symbol,
        local_symbols,
    ) = hsx_asm.assemble(lines, for_object=True)
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


def test_stdlib_metadata_is_embedded(tmp_path):
    ir = """
    define dso_local i32 @main() {
    entry:
      ret i32 0
    }
    """
    asm_text = HSX_LLC.compile_ll_to_mvasm(ir)
    app_hxo = _assemble_to_hxo(asm_text, tmp_path / "app.hxo")

    stdlib_source = STDLIB_PATH.read_text(encoding="utf-8")
    stdlib_hxo = _assemble_to_hxo(stdlib_source, tmp_path / "stdlib.hxo")

    hxe_path = tmp_path / "with_stdlib.hxe"
    hsx_linker.link_objects([stdlib_hxo, app_hxo], hxe_path)

    header, _, _ = load_hxe(hxe_path)
    metadata = header["metadata"]

    assert metadata["values"], "expected stdlib values"
    value_names = {entry.get("name") for entry in metadata["values"]}
    assert "sys.version" in value_names
    assert "sys.health" in value_names

    assert metadata["commands"], "expected stdlib commands"
    command_names = {entry.get("name") for entry in metadata["commands"]}
    assert "sys.reset" in command_names

    mailbox_targets = {entry.get("target") for entry in metadata.get("mailboxes", [])}
    assert "svc:log" in mailbox_targets
    assert "app:telemetry" in mailbox_targets
