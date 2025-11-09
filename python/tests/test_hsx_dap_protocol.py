import io

from python.hsx_dap import DAPProtocol


def test_dap_protocol_send_event_formats_headers():
    output = io.BytesIO()
    proto = DAPProtocol(io.BytesIO(), output)
    proto.send_event("initialized", {"foo": "bar"})
    output.seek(0)
    payload = output.read().decode("utf-8")
    assert "Content-Length:" in payload
    assert '"event": "initialized"' in payload or '"event":"initialized"' in payload


def test_dap_protocol_read_message_roundtrip():
    body = {"seq": 1, "type": "request", "command": "initialize", "arguments": {}}
    encoded = json_dumps(body).encode("utf-8")
    message = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii") + encoded
    proto = DAPProtocol(io.BytesIO(message), io.BytesIO())
    parsed = proto.read_message()
    assert parsed["command"] == "initialize"


def json_dumps(payload):
    import json

    return json.dumps(payload, separators=(",", ":"))
