import json
from pathlib import Path

from python import asm as hsx_asm
from python import hld as hsx_linker
from python import hsx_mailbox_constants as mbx_const
from platforms.python.host_vm import HXEMetadata, VMController, load_hxe


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

