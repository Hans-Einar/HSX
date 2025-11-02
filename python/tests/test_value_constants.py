"""Test that value constants load correctly from the C header."""
import pytest
from python.hsx_value_constants import CONSTANTS, header_path


def test_value_header_exists():
    """Verify the value header file exists."""
    assert header_path().exists(), f"Value header not found: {header_path()}"


def test_value_constants_loaded():
    """Verify value constants were loaded."""
    assert len(CONSTANTS) > 0, "No constants loaded from value header"


def test_value_module_id():
    """Verify the value module ID is correct."""
    assert CONSTANTS["HSX_VAL_MODULE_ID"] == 0x07


def test_value_function_ids():
    """Verify value function IDs are defined."""
    assert CONSTANTS["HSX_VAL_FN_REGISTER"] == 0x00
    assert CONSTANTS["HSX_VAL_FN_LOOKUP"] == 0x01
    assert CONSTANTS["HSX_VAL_FN_GET"] == 0x02
    assert CONSTANTS["HSX_VAL_FN_SET"] == 0x03
    assert CONSTANTS["HSX_VAL_FN_LIST"] == 0x04
    assert CONSTANTS["HSX_VAL_FN_SUB"] == 0x05
    assert CONSTANTS["HSX_VAL_FN_PERSIST"] == 0x06


def test_value_status_codes():
    """Verify value status codes are defined."""
    assert CONSTANTS["HSX_VAL_STATUS_OK"] == 0x0000
    assert CONSTANTS["HSX_VAL_STATUS_ENOENT"] == 0x0001
    assert CONSTANTS["HSX_VAL_STATUS_EPERM"] == 0x0002
    assert CONSTANTS["HSX_VAL_STATUS_ENOSPC"] == 0x0003
    assert CONSTANTS["HSX_VAL_STATUS_EINVAL"] == 0x0004
    assert CONSTANTS["HSX_VAL_STATUS_EEXIST"] == 0x0005
    assert CONSTANTS["HSX_VAL_STATUS_EBUSY"] == 0x0006


def test_value_flags():
    """Verify value flags are defined."""
    assert CONSTANTS["HSX_VAL_FLAG_RO"] == 0x01
    assert CONSTANTS["HSX_VAL_FLAG_PERSIST"] == 0x02
    assert CONSTANTS["HSX_VAL_FLAG_STICKY"] == 0x04
    assert CONSTANTS["HSX_VAL_FLAG_PIN"] == 0x08
    assert CONSTANTS["HSX_VAL_FLAG_BOOL"] == 0x10


def test_value_auth_levels():
    """Verify authorization levels are defined."""
    assert CONSTANTS["HSX_VAL_AUTH_PUBLIC"] == 0x00
    assert CONSTANTS["HSX_VAL_AUTH_USER"] == 0x01
    assert CONSTANTS["HSX_VAL_AUTH_ADMIN"] == 0x02
    assert CONSTANTS["HSX_VAL_AUTH_FACTORY"] == 0x03


def test_value_persist_modes():
    """Verify persistence modes are defined."""
    assert CONSTANTS["HSX_VAL_PERSIST_VOLATILE"] == 0x00
    assert CONSTANTS["HSX_VAL_PERSIST_LOAD"] == 0x01
    assert CONSTANTS["HSX_VAL_PERSIST_SAVE"] == 0x02


def test_value_descriptor_types():
    """Verify descriptor type tags are defined."""
    assert CONSTANTS["HSX_VAL_DESC_GROUP"] == 0x01
    assert CONSTANTS["HSX_VAL_DESC_NAME"] == 0x02
    assert CONSTANTS["HSX_VAL_DESC_UNIT"] == 0x03
    assert CONSTANTS["HSX_VAL_DESC_RANGE"] == 0x04
    assert CONSTANTS["HSX_VAL_DESC_PERSIST"] == 0x05


def test_value_limits():
    """Verify registry limits are defined."""
    assert CONSTANTS["HSX_VAL_MAX_VALUES"] == 256
    assert CONSTANTS["HSX_VAL_STRING_TABLE_SIZE"] == 4096
    assert CONSTANTS["HSX_VAL_GROUP_ALL"] == 0xFF
