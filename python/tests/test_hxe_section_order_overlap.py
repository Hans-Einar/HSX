import struct
import zlib
from pathlib import Path

import importlib.util
import pytest

from platforms.python.host_vm import HEADER, HSX_MAGIC, HSX_VERSION, MAX_BSS_SIZE, load_hxe


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def _build_valid_image(tmp_path: Path) -> Path:
    out_path = tmp_path / "valid.hxe"
    code_words = [ASM.emit_word(ASM.OPC["RET"])]
    ASM.write_hxe(code_words, entry=0, out_path=out_path, rodata=b"")
    return out_path


def _update_crc(buf: bytearray) -> None:
    crc = zlib.crc32(buf[: HEADER.size - 4] + buf[HEADER.size :]) & 0xFFFFFFFF
    struct.pack_into(">I", buf, HEADER.size - 4, crc)


def test_entry_alignment_is_validated(tmp_path):
    image = _build_valid_image(tmp_path)
    data = bytearray(image.read_bytes())
    assert struct.unpack_from(">I", data, 0)[0] == HSX_MAGIC
    assert struct.unpack_from(">H", data, 4)[0] == HSX_VERSION

    struct.pack_into(">I", data, 8, 2)  # entry not aligned to 4
    _update_crc(data)
    mutated = tmp_path / "bad_entry_align.hxe"
    mutated.write_bytes(data)

    with pytest.raises(ValueError, match="Entry address must be 4-byte aligned"):
        load_hxe(mutated)


def test_bss_size_overflow_rejected(tmp_path):
    image = _build_valid_image(tmp_path)
    data = bytearray(image.read_bytes())

    struct.pack_into(">I", data, 20, MAX_BSS_SIZE + 4)
    _update_crc(data)
    mutated = tmp_path / "bss_overflow.hxe"
    mutated.write_bytes(data)

    with pytest.raises(ValueError, match="BSS size exceeds VM capacity"):
        load_hxe(mutated)
