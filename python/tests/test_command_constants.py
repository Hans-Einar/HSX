"""Test that command constants load correctly from the C header."""
import pytest
from python.hsx_command_constants import CONSTANTS, header_path


def test_command_header_exists():
    """Verify the command header file exists."""
    assert header_path().exists(), f"Command header not found: {header_path()}"


def test_command_constants_loaded():
    """Verify command constants were loaded."""
    assert len(CONSTANTS) > 0, "No constants loaded from command header"


def test_command_module_id():
    """Verify the command module ID is correct."""
    assert CONSTANTS["HSX_CMD_MODULE_ID"] == 0x08


def test_command_function_ids():
    """Verify command function IDs are defined."""
    assert CONSTANTS["HSX_CMD_FN_REGISTER"] == 0x00
    assert CONSTANTS["HSX_CMD_FN_LOOKUP"] == 0x01
    assert CONSTANTS["HSX_CMD_FN_CALL"] == 0x02
    assert CONSTANTS["HSX_CMD_FN_CALL_ASYNC"] == 0x03
    assert CONSTANTS["HSX_CMD_FN_HELP"] == 0x04


def test_command_status_codes():
    """Verify command status codes are defined."""
    assert CONSTANTS["HSX_CMD_STATUS_OK"] == 0x0000
    assert CONSTANTS["HSX_CMD_STATUS_ENOENT"] == 0x0001
    assert CONSTANTS["HSX_CMD_STATUS_EPERM"] == 0x0002
    assert CONSTANTS["HSX_CMD_STATUS_ENOSPC"] == 0x0003
    assert CONSTANTS["HSX_CMD_STATUS_EINVAL"] == 0x0004
    assert CONSTANTS["HSX_CMD_STATUS_EEXIST"] == 0x0005
    assert CONSTANTS["HSX_CMD_STATUS_ENOASYNC"] == 0x0006
    assert CONSTANTS["HSX_CMD_STATUS_EFAIL"] == 0x0007


def test_command_flags():
    """Verify command flags are defined."""
    assert CONSTANTS["HSX_CMD_FLAG_PIN"] == 0x01
    assert CONSTANTS["HSX_CMD_FLAG_ASYNC"] == 0x02


def test_command_auth_levels():
    """Verify authorization levels are defined."""
    assert CONSTANTS["HSX_CMD_AUTH_PUBLIC"] == 0x00
    assert CONSTANTS["HSX_CMD_AUTH_USER"] == 0x01
    assert CONSTANTS["HSX_CMD_AUTH_ADMIN"] == 0x02
    assert CONSTANTS["HSX_CMD_AUTH_FACTORY"] == 0x03


def test_command_limits():
    """Verify registry limits are defined."""
    assert CONSTANTS["HSX_CMD_MAX_COMMANDS"] == 256
