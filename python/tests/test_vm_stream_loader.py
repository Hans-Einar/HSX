from pathlib import Path

from platforms.python.host_vm import VMController, load_hxe, HXEMetadata


SAMPLE_HXE = Path(__file__).resolve().parents[2] / "examples" / "tests" / "build" / "test_ir_half_main" / "main.hxe"


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
