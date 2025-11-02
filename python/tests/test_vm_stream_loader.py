import json
import struct
import zlib
from pathlib import Path

from python import hsx_mailbox_constants as mbx_const
from platforms.python.host_vm import (
    CRC_FIELD_OFFSET,
    HEADER_V2,
    HSX_MAGIC,
    HSX_VERSION_V2,
    HXEMetadata,
    META_ENTRY_STRUCT,
    METADATA_SECTION_MAILBOX,
    VMController,
    load_hxe,
)


SAMPLE_HXE = Path(__file__).resolve().parents[2] / "examples" / "tests" / "build" / "test_ir_half_main" / "main.hxe"


def _pad_app_name(name: str) -> bytes:
    raw = name.encode("ascii")
    if len(raw) >= 32:
        return raw[:31] + b"\x00"
    return raw + b"\x00" + b"\x00" * (31 - len(raw))


def _build_mailbox_hxe_bytes(mailboxes: list[dict[str, object]]) -> bytes:
    code_bytes = bytes.fromhex("60000000")
    rodata_bytes = b""
    header_size = HEADER_V2.size
    code_offset = header_size
    ro_offset = code_offset + len(code_bytes)
    table_offset = ro_offset + len(rodata_bytes)
    meta_entries = len(mailboxes)
    meta_table_size = META_ENTRY_STRUCT.size
    section_offset = table_offset + meta_table_size
    payload = json.dumps({"version": 1, "mailboxes": mailboxes}).encode("utf-8")
    total_size = section_offset + len(payload)
    image = bytearray(total_size)
    header_tuple = (
        HSX_MAGIC,
        HSX_VERSION_V2,
        0,  # flags
        0,  # entry
        len(code_bytes),
        len(rodata_bytes),
        0,  # bss_size
        0,  # req_caps
        0,  # crc placeholder
        _pad_app_name("mailbox_demo"),
        table_offset,
        1 if meta_entries else 0,
        b"\x00" * 24,
    )
    image[:header_size] = HEADER_V2.pack(*header_tuple)
    image[code_offset:code_offset + len(code_bytes)] = code_bytes
    if meta_entries:
        meta_entry = META_ENTRY_STRUCT.pack(
            METADATA_SECTION_MAILBOX,
            section_offset,
            len(payload),
            meta_entries,
        )
        image[table_offset:table_offset + META_ENTRY_STRUCT.size] = meta_entry
        image[section_offset:section_offset + len(payload)] = payload
    crc_input = image[:CRC_FIELD_OFFSET] + image[header_size:]
    crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    struct.pack_into(">I", image, CRC_FIELD_OFFSET, crc)
    return bytes(image)


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


def test_streaming_loader_precreates_mailboxes():
    image = _build_mailbox_hxe_bytes(
        [
            {
                "target": "app:telemetry",
                "capacity": 96,
                "mode_mask": mbx_const.HSX_MBX_MODE_FANOUT | mbx_const.HSX_MBX_MODE_RDWR,
            }
        ]
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
