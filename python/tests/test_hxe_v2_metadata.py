import json
import struct
import zlib

import pytest

from platforms.python.host_vm import (
    HEADER_V2,
    HSX_MAGIC,
    HSX_VERSION_V2,
    META_ENTRY_STRUCT,
    METADATA_SECTION_VALUE,
    METADATA_SECTION_MAILBOX,
    VALUE_ENTRY_STRUCT,
    MAILBOX_ENTRY_STRUCT,
    CRC_FIELD_OFFSET,
    FLAG_ALLOW_MULTIPLE,
    load_hxe_bytes,
    HXEMetadata,
)


def _pad_app_name(name: str) -> bytes:
    raw = name.encode("ascii")
    if len(raw) >= 32:
        return raw[:31] + b"\x00"
    return raw + b"\x00" + b"\x00" * (31 - len(raw))


def _build_v2_image(metadata_sections):
    code_bytes = bytes.fromhex("60000000")
    rodata_bytes = bytes.fromhex("11121314")

    header_size = HEADER_V2.size
    code_offset = header_size
    ro_offset = code_offset + len(code_bytes)
    table_offset = ro_offset + len(rodata_bytes)
    meta_table_size = len(metadata_sections) * META_ENTRY_STRUCT.size

    section_offsets = []
    current_offset = table_offset + meta_table_size
    for _, payload, _ in metadata_sections:
        section_offsets.append(current_offset)
        current_offset += len(payload)

    image = bytearray(current_offset)

    header_tuple = (
        HSX_MAGIC,
        HSX_VERSION_V2,
        FLAG_ALLOW_MULTIPLE,
        0,  # entry
        len(code_bytes),
        len(rodata_bytes),
        0,  # bss_size
        0,  # req_caps
        0,  # crc placeholder
        _pad_app_name("meta_demo"),
        table_offset,
        len(metadata_sections),
        b"\x00" * 24,
    )
    header_bytes = HEADER_V2.pack(*header_tuple)
    image[:header_size] = header_bytes
    image[code_offset:code_offset + len(code_bytes)] = code_bytes
    image[ro_offset:ro_offset + len(rodata_bytes)] = rodata_bytes

    for index, (section_type, payload, entry_count) in enumerate(metadata_sections):
        offset = section_offsets[index]
        meta_entry = META_ENTRY_STRUCT.pack(
            section_type,
            offset,
            len(payload),
            entry_count,
        )
        table_start = table_offset + index * META_ENTRY_STRUCT.size
        image[table_start:table_start + META_ENTRY_STRUCT.size] = meta_entry
        image[offset:offset + len(payload)] = payload

    crc_input = image[:CRC_FIELD_OFFSET] + image[header_size:]
    crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    struct.pack_into(">I", image, CRC_FIELD_OFFSET, crc)
    return bytes(image), code_bytes, rodata_bytes


def test_load_hxe_bytes_parses_v2_metadata():
    code_bytes = bytes.fromhex("60000000")
    rodata_bytes = bytes.fromhex("11121314")
    value_entry = VALUE_ENTRY_STRUCT.pack(
        1,  # group_id
        2,  # value_id
        0,  # flags
        0,  # auth_level
        0x3C00,  # init_value (f16 = 1.0)
        VALUE_ENTRY_STRUCT.size,  # name_offset (string table starts after entries)
        0,  # unit_offset
        0,  # epsilon
        0,  # min_val
        0x3C00,  # max_val (1.0)
        0,  # persist_key
        0,  # reserved
    )
    value_name = b"speed\x00"
    value_section = value_entry + value_name

    header_size = HEADER_V2.size
    code_offset = header_size
    ro_offset = code_offset + len(code_bytes)
    table_offset = ro_offset + len(rodata_bytes)
    section_offset = table_offset + META_ENTRY_STRUCT.size

    header_tuple = (
        HSX_MAGIC,
        HSX_VERSION_V2,
        FLAG_ALLOW_MULTIPLE,
        0,  # entry
        len(code_bytes),
        len(rodata_bytes),
        0,  # bss_size
        0,  # req_caps
        0,  # crc placeholder
        _pad_app_name("meta_demo"),
        table_offset,
        1,  # meta_count
        b"\x00" * 24,
    )
    header_bytes = bytearray(HEADER_V2.pack(*header_tuple))

    meta_entry = META_ENTRY_STRUCT.pack(
        METADATA_SECTION_VALUE,
        section_offset,
        len(value_section),
        1,
    )

    image = bytearray(section_offset + len(value_section))
    image[:header_size] = header_bytes
    image[code_offset:code_offset + len(code_bytes)] = code_bytes
    image[ro_offset:ro_offset + len(rodata_bytes)] = rodata_bytes
    image[table_offset:table_offset + len(meta_entry)] = meta_entry
    image[section_offset:section_offset + len(value_section)] = value_section

    crc_input = image[:CRC_FIELD_OFFSET] + image[header_size:]
    crc = zlib.crc32(crc_input) & 0xFFFFFFFF
    struct.pack_into(">I", image, CRC_FIELD_OFFSET, crc)

    header, code, rodata = load_hxe_bytes(bytes(image))

    assert header["version"] == HSX_VERSION_V2
    assert header["app_name"] == "meta_demo"
    assert header["allow_multiple_instances"] is True
    assert isinstance(header.get("_metadata_obj"), HXEMetadata)
    assert code == code_bytes
    assert rodata == rodata_bytes

    metadata = header["metadata"]
    assert metadata["sections"][0]["type"] == METADATA_SECTION_VALUE
    assert metadata["sections"][0]["entry_count"] == 1
    value_info = metadata["values"][0]
    assert value_info["group_id"] == 1
    assert value_info["value_id"] == 2
    assert value_info["name"] == "speed"
    assert value_info["init_value"] == 1.0
    assert value_info["max"] == 1.0


def test_load_hxe_bytes_parses_mailbox_json_metadata():
    mailbox_payload = json.dumps(
        {
            "version": 1,
            "mailboxes": [
                {
                    "target": "app:telemetry",
                    "capacity": 128,
                    "mode_mask": 0x0007,
                    "owner_pid": 2,
                    "bindings": [{"pid": 2, "flags": 5}],
                }
            ],
        }
    ).encode("utf-8")

    image, code_bytes, rodata_bytes = _build_v2_image(
        [(METADATA_SECTION_MAILBOX, mailbox_payload, 1)]
    )
    header, code, rodata = load_hxe_bytes(image)

    assert code == code_bytes
    assert rodata == rodata_bytes
    metadata = header["metadata"]
    assert metadata["mailboxes"]
    entry = metadata["mailboxes"][0]
    assert entry["target"] == "app:telemetry"
    assert entry["capacity"] == 128
    assert entry["mode_mask"] == 0x0007
    assert entry["owner_pid"] == 2
    assert entry["bindings"] == [{"pid": 2, "flags": 5}]
    assert entry.get("_source") == "json"


def test_load_hxe_bytes_parses_legacy_mailbox_metadata():
    name = b"app:legacy\x00"
    entry = MAILBOX_ENTRY_STRUCT.pack(
        MAILBOX_ENTRY_STRUCT.size,  # name offset
        32,  # queue depth
        0x0003,  # flags
        0,  # reserved
    )
    mailbox_section = entry + name
    image, _, _ = _build_v2_image(
        [(METADATA_SECTION_MAILBOX, mailbox_section, 1)]
    )
    header, _, _ = load_hxe_bytes(image)
    metadata = header["metadata"]
    assert metadata["mailboxes"]
    entry = metadata["mailboxes"][0]
    assert entry["target"] == "app:legacy"
    assert entry["capacity"] == 32
    assert entry["mode_mask"] == 0x0003
    assert entry.get("_source") == "legacy"


def test_load_hxe_bytes_rejects_invalid_mailbox_json():
    payload = b"{\"mailboxes\": [1, 2]"
    image, _, _ = _build_v2_image(
        [(METADATA_SECTION_MAILBOX, payload, 1)]
    )
    with pytest.raises(ValueError):
        load_hxe_bytes(image)
