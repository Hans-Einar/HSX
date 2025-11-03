import json
from pathlib import Path

import pytest

from python import asm as hsx_asm
from python import hld as hsx_linker
from python import hsx_mailbox_constants as mbx_const
from python.hsx_value_constants import (
    HSX_VAL_AUTH_PUBLIC,
    HSX_VAL_AUTH_USER,
    HSX_VAL_STATUS_OK,
    HSX_VAL_FLAG_PERSIST,
)
from python.hsx_command_constants import (
    HSX_CMD_FLAG_PIN,
    HSX_CMD_STATUS_OK,
    HSX_CMD_STATUS_EPERM,
)
from python.valcmd import f16_to_float, float_to_f16
from platforms.python.host_vm import HXEMetadata, VMController, load_hxe, load_hxe_bytes


SAMPLE_HXE = Path(__file__).resolve().parents[2] / "examples" / "tests" / "build" / "test_ir_half_main" / "main.hxe"


def _build_mailbox_hxe_bytes(tmp_path: Path, mailbox_entry: dict[str, object]) -> bytes:
    lines = [
        ".text",
        ".entry",
        "BRK",
        f".mailbox {json.dumps(mailbox_entry)}",
    ]
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
    return hxe_path.read_bytes()


def _build_value_cmd_hxe_bytes(tmp_path: Path) -> bytes:
    lines = [
        ".text",
        ".entry",
        "RET",
    ]
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
    metadata = {
        "values": [
            {
                "group": 1,
                "value": 2,
                "group_name": "sensors",
                "flags": HSX_VAL_FLAG_PERSIST,
                "auth": HSX_VAL_AUTH_PUBLIC,
                "init": 12.5,
                "name": "temperature",
                "unit": "degC",
                "epsilon": 0.1,
                "min": -40.0,
                "max": 125.0,
                "persist_key": 17,
            }
        ],
        "commands": [
            {
                "group": 1,
                "cmd": 7,
                "group_name": "control",
                "flags": HSX_CMD_FLAG_PIN,
                "auth": HSX_VAL_AUTH_USER,
                "handler": 0x100,
                "name": "reset",
                "help": "Soft reset",
            }
        ],
    }
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
        metadata=metadata,
    )
    hxe_path = tmp_path / "value_cmd.hxe"
    hsx_linker.link_objects([hxo_path], hxe_path)
    return hxe_path.read_bytes()


def _stream_load(controller: VMController, data: bytes, *, label: str | None = None):
    begin = controller.load_stream_begin(label=label)
    assert begin["status"] == "ok"
    pid = begin["pid"]
    offset = 0
    for size in (1, 16, 128):
        if offset >= len(data):
            break
        chunk = data[offset : offset + size]
        resp = controller.load_stream_write(pid, chunk)
        assert resp["status"] == "ok"
        offset += len(chunk)
    if offset < len(data):
        tail_resp = controller.load_stream_write(pid, data[offset:])
        assert tail_resp["status"] == "ok"
    return pid, controller.load_stream_end(pid)


def test_streaming_loader_round_trip():
    assert SAMPLE_HXE.exists(), "sample HXE missing"
    header, _, _ = load_hxe(SAMPLE_HXE)
    assert header["code_len"] > 0
    data = SAMPLE_HXE.read_bytes()
    controller = VMController()

    pid, result = _stream_load(controller, data, label=str(SAMPLE_HXE))
    assert result["status"] == "ok", (result, controller.streaming_sessions.get(pid))
    assert pid not in controller.streaming_sessions
    assert controller.tasks[pid]["state"] == "running"
    assert controller.vm is not None
    assert result["app_name"]
    assert controller.tasks[pid]["app_name"] == result["app_name"]
    assert isinstance(result.get("metadata"), dict)
    assert result.get("allow_multiple_instances") is True
    assert isinstance(controller.metadata_by_pid.get(pid), HXEMetadata)
    # Smoke a few steps to ensure the VM is operational.
    for _ in range(32):
        if not controller.vm.running:
            break
        controller.vm.step()


def test_streaming_loader_precreates_mailboxes(tmp_path):
    image = _build_mailbox_hxe_bytes(
        tmp_path,
        {
            "target": "app:telemetry",
            "capacity": 96,
            "mode_mask": mbx_const.HSX_MBX_MODE_FANOUT | mbx_const.HSX_MBX_MODE_RDWR,
        },
    )
    controller = VMController()
    pid, result = _stream_load(controller, image, label="mailbox_meta")
    assert result["status"] == "ok"
    creation = result.get("mailbox_creation")
    assert creation and creation[0]["status"] == "ok"
    descriptor_id = creation[0]["descriptor"]
    descriptors = controller.mailboxes.descriptor_snapshot()
    created = [desc for desc in descriptors if desc["descriptor_id"] == descriptor_id]
    assert created, f"mailbox descriptor {descriptor_id} missing from snapshot"
    desc = created[0]
    assert desc["name"] == "telemetry"
    assert desc["namespace"] == mbx_const.HSX_MBX_NAMESPACE_APP
    assert desc["owner_pid"] in (None, pid)
    assert desc["capacity"] == creation[0]["capacity"]
    metadata = result["metadata"]
    metadata_mailbox = metadata["mailboxes"][0]
    assert metadata_mailbox["descriptor"] == descriptor_id
    assert metadata_mailbox["queue_depth"] == creation[0]["capacity"]
    assert metadata_mailbox["mode_mask"] == creation[0]["mode_mask"]
    assert metadata.get("_mailbox_creation")[0]["descriptor"] == descriptor_id
    # Ensure descriptor already existed; binding again should succeed and retain id.
    rebind = controller.mailboxes.bind_target(pid=pid, target="app:telemetry")
    assert rebind.descriptor_id == descriptor_id


def test_value_command_metadata_roundtrip(tmp_path):
    image = _build_value_cmd_hxe_bytes(tmp_path)
    header, _, _ = load_hxe_bytes(image)
    metadata = header.get("metadata")
    assert metadata and metadata["values"] and metadata["commands"]
    value_entry = metadata["values"][0]
    assert value_entry["group_id"] == 1
    assert value_entry["value_id"] == 2
    assert value_entry["name"] == "temperature"
    assert value_entry["unit"] == "degC"
    assert value_entry["persist_key"] == 17
    assert f16_to_float(value_entry["init_raw"]) == pytest.approx(12.5, rel=1e-3)
    assert value_entry["group_name"] == "sensors"
    command_entry = metadata["commands"][0]
    assert command_entry["group_id"] == 1
    assert command_entry["cmd_id"] == 7
    assert command_entry["name"] == "reset"
    assert command_entry["help"] == "Soft reset"
    assert command_entry["group_name"] == "control"
    controller = VMController()
    pid, result = _stream_load(controller, image, label="value_cmd_meta")
    assert result["status"] == "ok"
    meta_obj = controller.metadata_by_pid.get(pid)
    assert isinstance(meta_obj, HXEMetadata)
    assert meta_obj.values and meta_obj.commands
    meta_value = meta_obj.values[0]
    assert meta_value["group_id"] == 1
    assert meta_value["value_id"] == 2
    assert meta_value["init_value"] == pytest.approx(12.5, rel=1e-3)
    assert meta_value["group_name"] == "sensors"
    meta_command = meta_obj.commands[0]
    assert meta_command["group_id"] == 1
    assert meta_command["cmd_id"] == 7
    assert meta_command["handler_offset"] == 0x100
    assert meta_command["group_name"] == "control"
    value_oid = (1 << 8) | 2
    status, value = controller.valcmd.value_get(value_oid, caller_pid=pid)
    assert status == HSX_VAL_STATUS_OK
    assert value == pytest.approx(12.5, rel=1e-3)
    value_entry = controller.valcmd.get_value_entry(value_oid)
    assert value_entry is not None
    assert value_entry.flags & HSX_VAL_FLAG_PERSIST
    assert value_entry.owner_pid == pid
    described_value = controller.valcmd.describe_value(value_oid)
    assert described_value is not None and described_value.get("group_name") == "sensors"
    status = controller.valcmd.value_set(value_oid, 18.5, caller_pid=pid)
    assert status == HSX_VAL_STATUS_OK
    assert controller.persistence_store.load(17) == float_to_f16(18.5)
    status, cmd_oid = controller.valcmd.command_lookup(1, 7)
    assert status == HSX_CMD_STATUS_OK
    status, _ = controller.valcmd.command_call(cmd_oid, caller_pid=pid)
    assert status == HSX_CMD_STATUS_EPERM
    command_entry = controller.valcmd.get_command_entry(cmd_oid)
    assert command_entry is not None
    assert command_entry.owner_pid == pid
    described_command = controller.valcmd.describe_command(cmd_oid)
    assert described_command is not None and described_command.get("group_name") == "control"


def test_linker_rejects_duplicate_value_metadata(tmp_path):
    lines = [".text", ".entry", "RET"]
    obj_args = hsx_asm.assemble(lines, for_object=True)
    metadata = {
        "values": [
            {
                "group": 1,
                "value": 1,
                "init": 0.0,
            }
        ]
    }
    hxo_paths = []
    for idx in range(2):
        hxo_path = tmp_path / f"dup_{idx}.hxo"
        hsx_asm.write_hxo_object(
            hxo_path,
            code_words=obj_args[0],
            rodata=obj_args[4],
            entry=obj_args[1] or 0,
            entry_symbol=obj_args[7],
            externs=obj_args[2],
            imports_decl=obj_args[3],
            relocs=obj_args[5],
            exports=obj_args[6],
            local_symbols=obj_args[8],
            metadata=metadata,
        )
        hxo_paths.append(hxo_path)
    hxe_path = tmp_path / "dup.hxe"
    with pytest.raises(ValueError, match="Duplicate value metadata"):
        hsx_linker.link_objects(hxo_paths, hxe_path)


def test_streaming_loader_rejects_overflow():
    data = SAMPLE_HXE.read_bytes()
    controller = VMController()
    begin = controller.load_stream_begin()
    pid = begin["pid"]
    controller.load_stream_write(pid, data)
    controller.load_stream_write(pid, b"\x00")
    result = controller.load_stream_end(pid)
    assert result["status"] == "error"
    controller.load_stream_abort(pid)
    assert pid not in controller.streaming_sessions


def test_streaming_loader_requires_complete_image():
    data = SAMPLE_HXE.read_bytes()
    controller = VMController()
    begin = controller.load_stream_begin()
    pid = begin["pid"]
    controller.load_stream_write(pid, data[:-16])
    result = controller.load_stream_end(pid)
    assert result["status"] == "error"
    controller.load_stream_abort(pid)
    assert pid not in controller.streaming_sessions
