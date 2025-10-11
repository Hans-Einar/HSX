import struct
import zlib
from pathlib import Path

import pytest

from python import asm as hsx_asm
from platforms.python.host_vm import (
    HEADER,
    HSX_MAGIC,
    HSX_VERSION,
    load_hxe,
    MAX_BSS_SIZE,
    MAX_CODE_LEN,
    MAX_RODATA_LEN,
)


def _build_valid_image(tmp_path: Path) -> Path:
    out_path = tmp_path / "valid.hxe"
    code = [hsx_asm.emit_word(hsx_asm.OPC["RET"])]
    hsx_asm.write_hxe(code, entry=0, out_path=out_path, rodata=b"")
    return out_path


def _update_crc(buf: bytearray) -> None:
    crc = zlib.crc32(buf[: HEADER.size - 4] + buf[HEADER.size :]) & 0xFFFFFFFF
    struct.pack_into(">I", buf, HEADER.size - 4, crc)


def test_load_hxe_detects_header_corruption(tmp_path):
    valid = _build_valid_image(tmp_path)
    load_hxe(valid)  # sanity check

    original = valid.read_bytes()

    # Bad magic
    mutated = bytearray(original)
    struct.pack_into(">I", mutated, 0, 0x0)
    bad_magic = tmp_path / "bad_magic.hxe"
    bad_magic.write_bytes(mutated)
    with pytest.raises(ValueError, match="Bad magic"):
        load_hxe(bad_magic)

    # Unsupported version
    mutated = bytearray(original)
    struct.pack_into(">H", mutated, 4, HSX_VERSION + 1)
    _update_crc(mutated)
    bad_version = tmp_path / "bad_version.hxe"
    bad_version.write_bytes(mutated)
    with pytest.raises(ValueError, match="Unsupported HSXE version"):
        load_hxe(bad_version)

    # Entry outside code
    mutated = bytearray(original)
    code_len = struct.unpack_from(">I", mutated, 12)[0]
    entry_outside = HEADER.size + code_len + 4
    struct.pack_into(">I", mutated, 8, entry_outside)
    _update_crc(mutated)
    bad_entry = tmp_path / "bad_entry.hxe"
    bad_entry.write_bytes(mutated)
    with pytest.raises(ValueError, match="Entry point outside code section"):
        load_hxe(bad_entry)

    # Code length not aligned
    mutated = bytearray(original)
    struct.pack_into(">I", mutated, 12, 2)
    _update_crc(mutated)
    misaligned = tmp_path / "misaligned.hxe"
    misaligned.write_bytes(mutated)
    with pytest.raises(ValueError, match="Code section must be 4-byte aligned"):
        load_hxe(misaligned)

    # Code length too large
    mutated = bytearray(original)
    struct.pack_into(">I", mutated, 12, MAX_CODE_LEN + 4)
    _update_crc(mutated)
    oversized = tmp_path / "oversized.hxe"
    oversized.write_bytes(mutated)
    with pytest.raises(ValueError, match="Code section exceeds VM capacity"):
        load_hxe(oversized)

    # RODATA length pushes past file end
    mutated = bytearray(original)
    struct.pack_into(">I", mutated, 16, 32)
    _update_crc(mutated)
    truncated = tmp_path / "truncated.hxe"
    truncated.write_bytes(mutated)
    with pytest.raises(ValueError, match="sections exceed file length"):
        load_hxe(truncated)

    # CRC mismatch
    mutated = bytearray(original)
    mutated[-1] ^= 0xFF
    crc_path = tmp_path / "crc_bad.hxe"
    crc_path.write_bytes(mutated)
    with pytest.raises(ValueError, match="CRC mismatch"):
        load_hxe(crc_path)

