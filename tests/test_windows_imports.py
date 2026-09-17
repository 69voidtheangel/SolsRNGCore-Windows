import sys

def test_windows_platform_module_imports():
    from solsrng_core.platform.windows.environment import detect_environment
    assert callable(detect_environment)

def test_config_uses_windows_backend():
    from solsrng_core.config import _from_dict
    cfg = _from_dict({"anti_afk": {"backend": "windows"}})
    assert cfg.anti_afk.backend == "windows"

def test_main_refuses_non_windows():
    import main
    if sys.platform != "win32":
        assert main.main() == 2
