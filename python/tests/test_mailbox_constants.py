from python import hsx_mailbox_constants as mbx


def test_mailbox_header_roundtrip():
    assert mbx.HSX_MBX_MODULE_ID == 0x05
    assert mbx.HSX_MBX_FLAG_STDOUT == 0x0001
    assert mbx.HSX_MBX_FLAG_STDERR == 0x0002
    assert mbx.HSX_MBX_TIMEOUT_INFINITE == 0xFFFF
    assert mbx.HSX_MBX_PREFIX_PID == "pid:"
    assert mbx.CONSTANTS["HSX_MBX_MODE_RDWR"] == 0x03
    assert mbx.HSX_MBX_FN_OPEN == 0x00
    assert mbx.HSX_MBX_FN_CLOSE == 0x06
    assert mbx.HSX_MBX_STATUS_OK == 0x0000
    assert mbx.HSX_MBX_STATUS_WOULDBLOCK == 0x0001
    assert mbx.HSX_MBX_STATUS_TIMEOUT == 0x0007
