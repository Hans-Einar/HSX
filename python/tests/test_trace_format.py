import pytest

from python import trace_format


def test_encode_normalises_trace_record() -> None:
    record = {
        "seq": "0x10",
        "pid": "7",
        "pc": "0x100",
        "opcode": "0x200",
        "regs": [0, 1, "0x2"],
        "changed_regs": ["r0", "PSW"],
        "mem_access": {"op": "READ", "address": "0x123", "width": "2", "value": "0xAA"},
        "ts": "123.5",
    }
    normalised = trace_format.encode_trace_records([record])[0]
    assert normalised["seq"] == 16
    assert normalised["pid"] == 7
    assert normalised["pc"] == 0x100
    assert normalised["opcode"] == 0x200
    assert normalised["regs"] == [0, 1, 2]
    assert normalised["changed_regs"] == ["R0", "PSW"]
    assert normalised["ts"] == pytest.approx(123.5)
    assert normalised["mem_access"]["op"] == "read"
    assert normalised["mem_access"]["address"] == 0x123
    assert normalised["mem_access"]["width"] == 2
    assert normalised["mem_access"]["value"] == 0xAA


def test_decode_converts_sequences_to_tuples() -> None:
    record = {
        "seq": 5,
        "pc": 0x200,
        "opcode": 0x300,
        "regs": [0, 1, 2],
        "changed_regs": ["R0"],
        "mem_access": {"op": "write", "address": 0x1234, "width": 4, "value": 0xCAFEBABE},
    }
    decoded = trace_format.decode_trace_records([record], default_pid=9)[0]
    assert decoded["pid"] == 9
    assert isinstance(decoded["regs"], tuple)
    assert decoded["regs"][1] == 1
    assert isinstance(decoded["changed_regs"], tuple)
    assert decoded["changed_regs"][0] == "R0"
    assert decoded["mem_access"]["op"] == "write"


def test_decode_missing_required_field_raises() -> None:
    with pytest.raises(ValueError):
        trace_format.decode_trace_records([{"pid": 1, "pc": 0x100, "opcode": 0x200}])
