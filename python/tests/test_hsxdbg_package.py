import importlib


def test_hsxdbg_package_exports():
    module = importlib.import_module("python.hsxdbg")
    assert hasattr(module, "HSXTransport")
    assert hasattr(module, "SessionManager")
    assert hasattr(module, "EventBus")
    assert hasattr(module, "RuntimeCache")
    assert hasattr(module, "CommandClient")
    assert module.__version__.startswith("0.")
