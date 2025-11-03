import importlib.util
import json
from pathlib import Path

from python import asm as hsx_asm
from python import hld as hsx_linker
from python import hsx_mailbox_constants as mbx_const
from python.hsx_value_constants import HSX_VAL_FLAG_PERSIST, HSX_VAL_AUTH_PUBLIC
from python.hsx_command_constants import HSX_CMD_FLAG_PIN, HSX_CMD_AUTH_USER
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


def test_hsx_llc_emits_value_and_command_directives(tmp_path):
    ir = """
; #pragma hsx_value(sensor_speed, group=1, id=5, flags=PERSIST, auth=PUBLIC, init=42.0, unit="rpm")
; #pragma hsx_command(reset_button, group=1, id=9, handler=reset_handler, flags=PIN, auth=USER, help="Reset motor")
define dso_local i32 @main() {
entry:
  %1 = call i32 @reset_handler()
  ret i32 %1
}

define dso_local i32 @reset_handler() {
entry:
  ret i32 0
}
"""
    asm_text = HSX_LLC.compile_ll_to_mvasm(ir)
    value_lines = [line for line in asm_text.splitlines() if line.startswith(".value ")]
    cmd_lines = [line for line in asm_text.splitlines() if line.startswith(".cmd ")]
    assert value_lines and cmd_lines, "expected both .value and .cmd directives"
    value_payload = json.loads(value_lines[0].split(None, 1)[1])
    assert value_payload["group"] == 1
    assert value_payload["value"] == 5
    assert value_payload["flags"] == HSX_VAL_FLAG_PERSIST
    assert value_payload["auth"] == HSX_VAL_AUTH_PUBLIC
    assert value_payload["unit"] == "rpm"
    cmd_payload = json.loads(cmd_lines[0].split(None, 1)[1])
    assert cmd_payload["group"] == 1
    assert cmd_payload["cmd"] == 9
    assert cmd_payload["flags"] == HSX_CMD_FLAG_PIN
    assert cmd_payload["auth"] == HSX_CMD_AUTH_USER
    assert cmd_payload["handler"] == "reset_handler"

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

    hxo_path = tmp_path / "value_cmd.hxo"
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

    hxe_path = tmp_path / "value_cmd.hxe"
    hsx_linker.link_objects([hxo_path], hxe_path)
    header, _, _ = load_hxe(hxe_path)
    metadata = header["metadata"]
    value_meta = metadata["values"][0]
    assert value_meta["group_id"] == 1
    assert value_meta["value_id"] == 5
    assert value_meta["flags"] == HSX_VAL_FLAG_PERSIST
    assert value_meta["auth_level"] == HSX_VAL_AUTH_PUBLIC
    command_meta = metadata["commands"][0]
    assert command_meta["group_id"] == 1
    assert command_meta["cmd_id"] == 9
    assert command_meta["flags"] & HSX_CMD_FLAG_PIN
    assert command_meta["auth_level"] == HSX_CMD_AUTH_USER
    assert isinstance(command_meta["handler_offset"], int)
