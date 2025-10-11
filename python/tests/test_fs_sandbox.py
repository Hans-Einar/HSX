from platforms.python.host_vm import FSStub


def test_fs_open_rejects_traversal_and_absolute_paths():
    fs = FSStub()

    assert fs.open("../../etc/passwd") == fs.err_invalid_path
    assert fs.open("C:/windows/system32") == fs.err_invalid_path
    assert fs.open(r"\\network\\share") == fs.err_invalid_path

    fd = fs.open("data/log.txt")
    assert fd >= 0
    assert fs.close(fd) == 0
