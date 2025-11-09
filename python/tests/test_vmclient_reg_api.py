from python import vmclient


def _make_client(response_builder):
    client = object.__new__(vmclient.VMClient)

    def fake_request(self, payload):
        return response_builder(payload)

    client.request = fake_request.__get__(client, vmclient.VMClient)
    return client


def test_reg_get_uses_vm_reg_get_command():
    captured = {}

    def responder(payload):
        captured.update(payload)
        return {"version": 1, "status": "ok", "value": 0x12345678}

    client = _make_client(responder)
    value = vmclient.VMClient.reg_get(client, 5, pid=2)
    assert captured["cmd"] == "vm_reg_get"
    assert captured["reg"] == 5
    assert captured["pid"] == 2
    assert value == 0x12345678


def test_reg_set_masks_value_and_uses_command():
    captured = {}

    def responder(payload):
        captured.update(payload)
        return {"version": 1, "status": "ok", "value": payload.get("value")}

    client = _make_client(responder)
    value = vmclient.VMClient.reg_set(client, 7, 0x1FFFFFFFF)
    assert captured["cmd"] == "vm_reg_set"
    assert captured["reg"] == 7
    assert "pid" not in captured
    assert captured["value"] == 0x1FFFFFFFF & 0xFFFFFFFF
    assert value == 0x1FFFFFFFF & 0xFFFFFFFF


def test_trace_last_uses_vm_trace_last_command():
    captured = {}

    def responder(payload):
        captured.update(payload)
        return {"version": 1, "status": "ok", "trace": {"pc": 0x100}}

    client = _make_client(responder)
    trace = vmclient.VMClient.trace_last(client, pid=1)
    assert captured["cmd"] == "vm_trace_last"
    assert captured["pid"] == 1
    assert trace["pc"] == 0x100
