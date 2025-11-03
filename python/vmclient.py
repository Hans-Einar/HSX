import json
import socket
from typing import Any, Dict, Optional


def _check_ok(response: Dict[str, Any]) -> Dict[str, Any]:
    version = response.get("version", 1)
    if version != 1:
        raise RuntimeError(f"unsupported protocol version {version}")
    if response.get("status") != "ok":
        raise RuntimeError(response.get("error", "vm error"))
    return response


class VMClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._rfile = self._sock.makefile("r", encoding="utf-8", newline="\n")
        self._wfile = self._sock.makefile("w", encoding="utf-8", newline="\n")

    def close(self) -> None:
        try:
            self._rfile.close()
            self._wfile.close()
        finally:
            self._sock.close()

    def request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(payload)
        payload.setdefault("version", 1)
        data = json.dumps(payload, separators=(",", ":"))
        self._wfile.write(data + "\n")
        self._wfile.flush()
        line = self._rfile.readline()
        if not line:
            raise RuntimeError("VM connection closed")
        return json.loads(line)

    def ping(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "ping"}))

    def info(self, pid: int | None = None) -> Dict[str, Any]:
        payload = {"cmd": "info"}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("info", {})

    def load(self, path: str, verbose: bool = False) -> Dict[str, Any]:
        payload = {"cmd": "load", "path": path}
        if verbose:
            payload["verbose"] = True
        return _check_ok(self.request(payload)).get("image", {})

    def step(self, steps: int, pid: Optional[int] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "step", "steps": steps}
        if pid is not None:
            payload["pid"] = pid
        resp = _check_ok(self.request(payload))
        return resp.get("result", {})

    def read_regs(self, pid: int | None = None) -> Dict[str, Any]:
        payload = {"cmd": "read_regs"}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("registers", {})

    def reg_get(self, reg: int, pid: int | None = None) -> int:
        payload: Dict[str, Any] = {"cmd": "vm_reg_get", "reg": int(reg)}
        if pid is not None:
            payload["pid"] = pid
        resp = _check_ok(self.request(payload))
        return int(resp.get("value", 0)) & 0xFFFFFFFF

    def reg_get_for(self, pid: int, reg: int) -> int:
        return self.reg_get(reg, pid=pid)

    def reg_set(self, reg: int, value: int, pid: int | None = None) -> int:
        payload: Dict[str, Any] = {
            "cmd": "vm_reg_set",
            "reg": int(reg),
            "value": int(value) & 0xFFFFFFFF,
        }
        if pid is not None:
            payload["pid"] = pid
        resp = _check_ok(self.request(payload))
        return int(resp.get("value", 0)) & 0xFFFFFFFF

    def reg_set_for(self, pid: int, reg: int, value: int) -> int:
        return self.reg_set(reg, value, pid=pid)

    def write_regs(self, registers: Dict[str, Any], pid: int | None = None) -> Dict[str, Any]:
        payload = {"cmd": "write_regs", "registers": registers}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("registers", {})

    def read_mem(self, addr: int, length: int, pid: int | None = None) -> bytes:
        payload = {"cmd": "read_mem", "addr": addr, "length": length}
        if pid is not None:
            payload["pid"] = pid
        resp = _check_ok(self.request(payload))
        hex_bytes = resp.get("data", "")
        return bytes.fromhex(hex_bytes)

    def write_mem(self, addr: int, data: bytes, pid: int | None = None) -> None:
        payload = {"cmd": "write_mem", "addr": addr, "data": data.hex()}
        if pid is not None:
            payload["pid"] = pid
        _check_ok(self.request(payload))

    def attach(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "attach"})).get("info", {})

    def detach(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "detach"})).get("info", {})

    def pause(self, pid: int | None = None) -> Dict[str, Any]:
        payload = {"cmd": "pause"}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload))

    def resume(self, pid: int | None = None) -> Dict[str, Any]:
        payload = {"cmd": "resume"}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload))

    def reset(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "reset"}))

    def kill(self, pid: int) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "kill", "pid": pid}))

    def ps(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "ps"}))

    def sched(self, pid: int, *, priority: int | None = None, quantum: int | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "sched", "pid": pid}
        if priority is not None:
            payload["priority"] = priority
        if quantum is not None:
            payload["quantum"] = quantum
        return _check_ok(self.request(payload)).get("task", {})

    def trace(self, pid: int, enable: Optional[bool] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "trace", "pid": pid}
        if enable is not None:
            payload["mode"] = 1 if enable else 0
        return _check_ok(self.request(payload)).get("trace", {})

    def trace_last(self, pid: int | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "vm_trace_last"}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("trace", {})

    def restart(self, targets: list[str] | None = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"cmd": "restart"}
        if targets:
            payload["targets"] = targets
        return _check_ok(self.request(payload))
    def mailbox_snapshot(self) -> list[dict]:
        return _check_ok(self.request({"cmd": "mailbox_snapshot"})).get("descriptors", [])

    def mailbox_open(self, pid: int, target: str, flags: int = 0) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_open", "pid": pid, "target": target}
        if flags:
            payload["flags"] = flags
        return _check_ok(self.request(payload))

    def mailbox_close(self, pid: int, handle: int) -> dict:
        return _check_ok(self.request({"cmd": "mailbox_close", "pid": pid, "handle": handle}))

    def mailbox_bind(self, pid: int, target: str, *, capacity: int | None = None, mode: int = 0) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_bind", "pid": pid, "target": target}
        if capacity is not None:
            payload["capacity"] = capacity
        if mode:
            payload["mode"] = mode
        return _check_ok(self.request(payload))

    def mailbox_config_stdio(self, stream: str, mode: int, update_existing: bool = True) -> dict:
        payload: Dict[str, Any] = {
            "cmd": "mailbox_config_stdio",
            "stream": stream,
            "mode": mode,
            "update_existing": 1 if update_existing else 0,
        }
        return _check_ok(self.request(payload))

    def mailbox_stdio_summary(self, *, pid: int | None = None, stream: str | None = None, default_only: bool = False) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_stdio_summary"}
        if pid is not None:
            payload["pid"] = pid
        if stream is not None:
            payload["stream"] = stream
        if default_only:
            payload["default_only"] = 1
        return _check_ok(self.request(payload)).get("summary", {})

    def val_list(
        self,
        *,
        pid: int | None = None,
        group: int | None = None,
        oid: int | None = None,
        name: str | None = None,
    ) -> list[dict]:
        payload: Dict[str, Any] = {"cmd": "val_list"}
        if pid is not None:
            payload["pid"] = pid
        if group is not None:
            payload["group"] = group
        if oid is not None:
            payload["oid"] = oid
        if name is not None:
            payload["name"] = name
        return _check_ok(self.request(payload)).get("values", [])

    def val_get(self, oid: int, *, pid: int | None = None) -> dict:
        payload: Dict[str, Any] = {"cmd": "val_get", "oid": oid}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("value", {})

    def val_set(self, oid: int, value: Any, *, pid: int | None = None) -> dict:
        payload: Dict[str, Any] = {"cmd": "val_set", "oid": oid, "value": value}
        if pid is not None:
            payload["pid"] = pid
        return _check_ok(self.request(payload)).get("value", {})

    def cmd_list(
        self,
        *,
        pid: int | None = None,
        group: int | None = None,
        oid: int | None = None,
        name: str | None = None,
    ) -> list[dict]:
        payload: Dict[str, Any] = {"cmd": "cmd_list"}
        if pid is not None:
            payload["pid"] = pid
        if group is not None:
            payload["group"] = group
        if oid is not None:
            payload["oid"] = oid
        if name is not None:
            payload["name"] = name
        return _check_ok(self.request(payload)).get("commands", [])

    def cmd_call(self, oid: int, *, pid: int | None = None, async_call: bool = False) -> dict:
        payload: Dict[str, Any] = {"cmd": "cmd_call", "oid": oid}
        if pid is not None:
            payload["pid"] = pid
        if async_call:
            payload["async"] = 1
        return _check_ok(self.request(payload)).get("command", {})

    def mailbox_send(self, pid: int, handle: int, *, data: str | None = None, data_hex: str | None = None, flags: int = 0, channel: int = 0) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_send", "pid": pid, "handle": handle, "flags": flags, "channel": channel}
        if data_hex is not None:
            payload["data_hex"] = data_hex
        elif data is not None:
            payload["data"] = data
        return _check_ok(self.request(payload))

    def mailbox_recv(self, pid: int, handle: int, *, max_len: int = 512, timeout: int = 0) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_recv", "pid": pid, "handle": handle, "max_len": max_len, "timeout": timeout}
        return _check_ok(self.request(payload))

    def mailbox_peek(self, pid: int, handle: int) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_peek", "pid": pid, "handle": handle}
        return _check_ok(self.request(payload))

    def mailbox_tap(self, pid: int, handle: int, enable: bool = True) -> dict:
        payload: Dict[str, Any] = {"cmd": "mailbox_tap", "pid": pid, "handle": handle, "enable": 1 if enable else 0}
        return _check_ok(self.request(payload))
