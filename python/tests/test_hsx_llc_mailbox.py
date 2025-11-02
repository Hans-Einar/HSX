import importlib.util
import json
from pathlib import Path

from python import asm as hsx_asm
from python import hld as hsx_linker
from python import hsx_mailbox_constants as mbx_const
from platforms.python.host_vm import load_hxe


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc_mailbox", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def test_hsx_llc_emits_mailbox_directive_and_roundtrips(tmp_path):
    ir = """
; #pragma hsx_mailbox(target="app:telemetry", capacity=96, mode="RDWR|FANOUT")
define dso_local i32 @main() {
entry:
  ret i32 0
}
"""
    asm_text = HSX_LLC.compile_ll_to_mvasm(ir)
    mailbox_lines = [line for line in asm_text.splitlines() if line.startswith(".mailbox ")]
    assert mailbox_lines, "expected .mailbox directive in MVASM output"
    payload = json.loads(mailbox_lines[0].split(None, 1)[1])
    assert payload["target"] == "app:telemetry"
    assert payload["capacity"] == 96
    assert payload["mode_mask"] == mbx_const.HSX_MBX_MODE_RDWR | mbx_const.HSX_MBX_MODE_FANOUT

    lines = [line + "\n" for line in asm_text.splitlines()]
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

    hxo_path = tmp_path / "mailbox.hxo"
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

    hxe_path = tmp_path / "mailbox.hxe"
    hsx_linker.link_objects([hxo_path], hxe_path)
    header, _, _ = load_hxe(hxe_path)
    metadata = header["metadata"]
    assert metadata["mailboxes"], "Expected mailbox metadata in linked HXE"
    mailbox = metadata["mailboxes"][0]
    assert mailbox["target"] == "app:telemetry"
    assert mailbox["capacity"] == 96
    expected_mode = mbx_const.HSX_MBX_MODE_RDWR | mbx_const.HSX_MBX_MODE_FANOUT
    assert mailbox["mode_mask"] == expected_mode
