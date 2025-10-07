#!/usr/bin/env python3
"""Simple HSX executive client prototype.

Connects to the HSX VM RPC server (see `platforms/python/host_vm.py --listen`),
optionally loads a `.hxe` image, and drives instruction stepping while reporting
basic runtime statistics. This is an initial scaffold so downstream tooling can
coordinate scheduling, halting, and inspection.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from vmclient import VMClient, _check_ok


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
        data = json.dumps(payload, separators=(",", ":"))
        self._wfile.write(data + "\n")
        self._wfile.flush()
        line = self._rfile.readline()
        if not line:
            raise RuntimeError("VM connection closed")
        return json.loads(line)

    def attach(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "attach"})).get("info", {})

    def detach(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "detach"})).get("info", {})

    def pause(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "pause"}))

    def resume(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "resume"}))

    def ping(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "ping"}))

    def info(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "info"})).get("info", {})

    def load(self, path: str, verbose: bool = False) -> Dict[str, Any]:
        payload = {"cmd": "load", "path": path}
        if verbose:
            payload["verbose"] = True
        return _check_ok(self.request(payload)).get("image", {})

    def step(self, cycles: int) -> Dict[str, Any]:
        resp = _check_ok(self.request({"cmd": "step", "cycles": cycles}))
        return resp.get("result", {})

    def read_regs(self) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "read_regs"})).get("registers", {})

    def write_regs(self, registers: Dict[str, Any]) -> Dict[str, Any]:
        return _check_ok(self.request({"cmd": "write_regs", "registers": registers})).get("registers", {})

    def read_mem(self, addr: int, length: int) -> bytes:
        resp = _check_ok(self.request({"cmd": "read_mem", "addr": addr, "length": length}))
        hex_bytes = resp.get("data", "")
        return bytes.fromhex(hex_bytes)

    def write_mem(self, addr: int, data: bytes) -> None:
        _check_ok(self.request({"cmd": "write_mem", "addr": addr, "data": data.hex()}))


class ExecutiveRunner:
    def __init__(self, client: VMClient, *, step_cycles: int = 500, max_cycles: Optional[int] = None) -> None:
        self.client = client
        self.step_cycles = max(1, step_cycles)
        self.max_cycles = max_cycles

    def run(self) -> None:
        total_cycles = 0
        while True:
            result = self.client.step(self.step_cycles)
            executed = int(result.get("executed", 0))
            total_cycles += executed
            running = bool(result.get("running", False))
            pc = result.get("pc")
            cycles = result.get("cycles")
            sleep_pending = bool(result.get("sleep_pending"))
            events = result.get("events") or []
            print(f"[exec] step executed={executed} running={running} pc={pc} cycles={cycles} sleep={sleep_pending}")
            for event in events:
                print(f"[event] {event}")

            if self.max_cycles is not None and total_cycles >= self.max_cycles:
                print(f"[exec] max cycles {self.max_cycles} reached")
                break
            if not running:
                print("[exec] VM reports task halted")
                break

            time.sleep(0.001)  # yield to host briefly to avoid tight loop


def main() -> None:
    parser = argparse.ArgumentParser(description="HSX executive client prototype")
    parser.add_argument("--vm-host", default="127.0.0.1", help="HSX VM host (default: 127.0.0.1)")
    parser.add_argument("--vm-port", type=int, default=9999, help="HSX VM port")
    parser.add_argument("--program", help="Optional .hxe to load before stepping")
    parser.add_argument("--step", type=int, default=500, help="Cycles per step command (default: 500)")
    parser.add_argument("--max-cycles", type=int, help="Stop after this many cycles")
    parser.add_argument("--verbose-load", action="store_true", help="Request verbose header info on load")
    args = parser.parse_args()

    client = VMClient(args.vm_host, args.vm_port)
    attached = False
    try:
        pong = client.ping()
        print(f"[exec] VM ping -> {pong.get('reply')}")
        info = client.info()
        print(f"[exec] VM info: {info}")

        if args.program:
            image_info = client.load(str(Path(args.program)))
            print(f"[exec] loaded image: {image_info}")

        attach_info = client.attach()
        attached = True
        print(f"[exec] attach info: {attach_info}")
        client.resume()

        runner = ExecutiveRunner(client, step_cycles=args.step, max_cycles=args.max_cycles)
        runner.run()
    finally:
        if attached:
            try:
                client.detach()
            except Exception as exc:
                print(f"[exec] detach error: {exc}", file=sys.stderr)
        client.close()


if __name__ == "__main__":
    main()

