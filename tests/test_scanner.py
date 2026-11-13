import os
import sys
import threading

import pytest
from PIL import Image

from hpscan.model import Settings
from hpscan.scanner import ScanCancelled, host_environment, inspect_device, run_command, scan


def test_demo_real_600dpi_a4(tmp_path):
    settings = Settings(output=str(tmp_path), demo=True)
    path = tmp_path / "scan.png"
    scan(settings, path, threading.Event())
    with Image.open(path) as image:
        assert image.size == (4961, 7016)
        assert image.info["dpi"][0] == pytest.approx(600, abs=0.02)


def test_cancel(tmp_path):
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ScanCancelled):
        scan(Settings(output=str(tmp_path), demo=True), tmp_path / "raw", cancel)
    assert not (tmp_path / "raw").exists()


def test_subprocess_cancel():
    cancel = threading.Event()
    timer = threading.Timer(0.2, cancel.set)
    timer.start()
    try:
        with pytest.raises(ScanCancelled):
            run_command([sys.executable, "-c", "import time; time.sleep(10)"], cancel=cancel)
    finally:
        timer.cancel()


def test_subprocess_error():
    with pytest.raises(RuntimeError, match="bad device"):
        run_command([sys.executable, "-c", "import sys; print('bad device', file=sys.stderr); sys.exit(2)"])


def test_frozen_environment(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/frozen")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib64")
    assert host_environment()["LD_LIBRARY_PATH"] == "/usr/lib64"
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    assert "LD_LIBRARY_PATH" not in host_environment()


def test_sane_test_backend(tmp_path, monkeypatch):
    import shutil
    if not shutil.which("scanimage"):
        pytest.skip("scanimage nincs telepítve")
    config = tmp_path / "sane"
    config.mkdir()
    (config / "dll.conf").write_text("test\n")
    (config / "test.conf").write_text("number_of_devices 1\n")
    monkeypatch.setenv("SANE_CONFIG_DIR", str(config))
    options = inspect_device("test:0")
    assert "Color" in options["modes"]
    settings = Settings(output=str(tmp_path), device="test:0", width=105, height=148, dpi=150)
    path = tmp_path / "raw.pnm"
    scan(settings, path, threading.Event())
    with Image.open(path) as image:
        assert image.width == pytest.approx(620, abs=5)
        assert image.height == pytest.approx(874, abs=5)
