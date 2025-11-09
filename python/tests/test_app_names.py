import struct
import zlib
import tempfile
from pathlib import Path

import pytest

from platforms.python.host_vm import (
    FLAG_ALLOW_MULTIPLE,
    HEADER_V2,
    HSX_MAGIC,
    HSX_VERSION_V2,
    CRC_FIELD_OFFSET,
    VMController,
)


def _encode_app_name(name: str) -> bytes:
    raw = name.encode("ascii")
    if len(raw) > 31:
        raw = raw[:31]
    return raw + b"\x00" * (32 - len(raw))


def build_minimal_hxe(path: Path, *, app_name: str, allow_multiple: bool) -> None:
    code_bytes = bytes.fromhex("60000000")
    header_size = HEADER_V2.size
    flags = FLAG_ALLOW_MULTIPLE if allow_multiple else 0
    header_tuple = (
        HSX_MAGIC,
        HSX_VERSION_V2,
        flags,
        0,  # entry
        len(code_bytes),
        0,  # ro_len
        0,  # bss_size
        0,  # req_caps
        0,  # crc placeholder
        _encode_app_name(app_name),
        0,  # meta_offset
        0,  # meta_count
        b"\x00" * 24,
    )
    image = bytearray(header_size + len(code_bytes))
    image[:header_size] = HEADER_V2.pack(*header_tuple)
    image[header_size:] = code_bytes
    crc_input = image[:CRC_FIELD_OFFSET] + image[header_size:]
    crc = struct.pack(">I", (0xFFFFFFFF & zlib.crc32(crc_input)))
    image[CRC_FIELD_OFFSET : CRC_FIELD_OFFSET + 4] = crc
    path.write_bytes(image)


def test_single_instance_app_name_propagates():
    with tempfile.TemporaryDirectory() as tmpdir:
        hxe_path = Path(tmpdir) / "demo.hxe"
        build_minimal_hxe(hxe_path, app_name="demo", allow_multiple=False)
        controller = VMController()

        info = controller.load_from_path(str(hxe_path))

        pid = info["pid"]
        assert controller.tasks[pid]["app_name"] == "demo"
        # ensure ps-style data is populated
        ps_snapshot = controller.task_list()
        task_entry = next(t for t in ps_snapshot["tasks"] if t["pid"] == pid)
        assert task_entry["app_name"] == "demo"


def test_conflicting_app_name_raises_when_multiple_disallowed():
    with tempfile.TemporaryDirectory() as tmpdir:
        hxe_path = Path(tmpdir) / "conflict.hxe"
        build_minimal_hxe(hxe_path, app_name="conflict", allow_multiple=False)
        controller = VMController()
        controller.load_from_path(str(hxe_path))

        with pytest.raises(ValueError, match="app_exists:conflict"):
            controller.load_from_path(str(hxe_path))


def test_multiple_instances_get_numbered_suffixes():
    with tempfile.TemporaryDirectory() as tmpdir:
        hxe_path = Path(tmpdir) / "multi.hxe"
        build_minimal_hxe(hxe_path, app_name="multi", allow_multiple=True)
        controller = VMController()

        info1 = controller.load_from_path(str(hxe_path))
        pid1 = info1["pid"]
        assert controller.tasks[pid1]["app_name"] == "multi"

        info2 = controller.load_from_path(str(hxe_path))
        pid2 = info2["pid"]
        assert controller.tasks[pid2]["app_name"] == "multi_#0"
