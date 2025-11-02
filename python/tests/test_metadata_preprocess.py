import pytest

from python.execd import ExecutiveState
from python import hsx_mailbox_constants as mbx_const


class MetadataVM:
    def __init__(self, *, fail_bind: bool = False) -> None:
        self.fail_bind = fail_bind
        self.bound = []

    def mailbox_bind(self, pid: int, target: str, *, capacity=None, mode: int = 0):
        if self.fail_bind:
            return {"status": "error", "error": "EEXIST"}
        self.bound.append((pid, target, capacity, mode))
        capacity_value = capacity if capacity is not None else mbx_const.HSX_MBX_DEFAULT_RING_CAPACITY
        return {
            "status": "ok",
            "mbx_status": mbx_const.HSX_MBX_STATUS_OK,
            "descriptor": len(self.bound),
            "capacity": capacity_value,
            "mode": mode,
        }


def _make_state(vm: MetadataVM) -> ExecutiveState:
    return ExecutiveState(vm, step_batch=1)


def test_register_metadata_success():
    vm = MetadataVM()
    state = _make_state(vm)
    metadata = {
        "values": [
            {
                "group_id": 1,
                "value_id": 2,
                "flags": 0x05,
                "auth_level": 2,
                "init_value": 1.5,
                "name": "rpm",
                "unit": "rpm",
                "epsilon": 0.1,
                "min": 0.0,
                "max": 100.0,
                "persist_key": 0x1234,
            }
        ],
        "commands": [
            {
                "group_id": 1,
                "cmd_id": 4,
                "flags": 0x01,
                "auth_level": 1,
                "handler_offset": 0x100,
                "name": "reset",
                "help": "Reset motor",
            }
        ],
        "mailboxes": [
            {
                "name": "app:motor.telemetry",
                "queue_depth": 16,
                "flags": 0,
            }
        ],
    }

    state._register_metadata(pid=1, metadata=metadata)

    values = state.value_registry[1]
    assert (1, 2) in values
    assert values[(1, 2)]["flags"] == 0x05
    assert values[(1, 2)]["init_value"] == pytest.approx(1.5)

    commands = state.command_registry[1]
    assert (1, 4) in commands
    assert commands[(1, 4)]["handler_offset"] == 0x100

    mailboxes = state.mailbox_registry[1]
    assert "app:motor.telemetry" in mailboxes
    entry = mailboxes["app:motor.telemetry"]
    assert entry["mode"] == mbx_const.HSX_MBX_MODE_RDWR
    assert entry["capacity"] == 16

    assert vm.bound == [(1, "app:motor.telemetry", 16, mbx_const.HSX_MBX_MODE_RDWR)]


def test_register_metadata_duplicate_value_raises():
    state = _make_state(MetadataVM())
    metadata = {
        "values": [
            {"group_id": 1, "value_id": 1},
            {"group_id": 1, "value_id": 1},
        ],
        "commands": [],
        "mailboxes": [],
    }
    with pytest.raises(ValueError, match="metadata_value_duplicate"):
        state._register_metadata(1, metadata)


def test_register_metadata_mailbox_bind_failure():
    vm = MetadataVM(fail_bind=True)
    state = _make_state(vm)
    metadata = {
        "values": [],
        "commands": [],
        "mailboxes": [
            {"name": "app:failing", "queue_depth": 0, "flags": 0},
        ],
    }
    with pytest.raises(RuntimeError, match="metadata_mailbox_bind_failed"):
        state._register_metadata(1, metadata)
    assert 1 not in state.mailbox_registry
