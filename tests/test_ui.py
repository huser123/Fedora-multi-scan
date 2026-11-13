from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox

from hpscan.ui import MainWindow


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    import hpscan.ui as ui
    monkeypatch.setattr(ui, "QSettings", lambda *a: QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    widget = MainWindow(demo=True)
    qtbot.addWidget(widget)
    widget.output.setText(str(tmp_path / "scans"))
    widget.paper.setCurrentText("A6")
    widget.dpi.setCurrentText("150")
    widget.show()
    widget.activateWindow()
    qtbot.wait(50)
    yield widget
    if widget.worker:
        widget.worker.cancel.set()
        qtbot.waitUntil(lambda: widget.worker is None, timeout=15000)
    if widget.session:
        widget.session.release()
        widget.session = None


def wait_saved(qtbot, window, total):
    qtbot.waitUntil(lambda: window.worker is None, timeout=15000)
    assert window.session.total == total


def test_no_scan_until_space_and_manual_unit(qtbot, window):
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert window.session.total == 0
    assert window.session.current["prefix"] == "aa"
    qtbot.keyClick(window, Qt.Key.Key_Space)
    wait_saved(qtbot, window, 1)
    qtbot.keyClick(window, Qt.Key.Key_T)
    wait_saved(qtbot, window, 2)
    qtbot.keyClick(window, Qt.Key.Key_U)
    assert window.session.total == 2
    assert window.session.current["prefix"] == "ab"
    assert window.worker is None
    qtbot.keyClick(window, Qt.Key.Key_Space)
    wait_saved(qtbot, window, 3)
    qtbot.keyClick(window, Qt.Key.Key_V)
    assert window.session is None
    assert window.stack.currentIndex() == 0


def test_real_name_dialog_focus_enter_and_space(qtbot, window):
    window.naming.setCurrentIndex(1)
    def enter_name(name):
        def answer():
            dialog = window.findChild(QInputDialog)
            assert dialog is not None
            field = dialog.findChild(QLineEdit)
            assert field.hasFocus()
            qtbot.keyClicks(field, name)
            qtbot.keyClick(field, Qt.Key.Key_Return)
        QTimer.singleShot(70, answer)
    enter_name("Pistike")
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert window.session.current["prefix"] == "Pistike"
    assert window.session.total == 0
    qtbot.wait(50)
    qtbot.keyClick(window, Qt.Key.Key_Space)
    wait_saved(qtbot, window, 1)
    enter_name("Petike")
    qtbot.keyClick(window, Qt.Key.Key_U)
    assert window.session.current["prefix"] == "Petike"
    assert window.session.total == 1
    assert window.worker is None
    qtbot.wait(50)
    qtbot.keyClick(window, Qt.Key.Key_Return)
    qtbot.wait(120)
    assert window.session.total == 1
    qtbot.keyClick(window, Qt.Key.Key_Space)
    wait_saved(qtbot, window, 2)
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window.session is None


def test_fixed_custom_boundary_waits_after_name(qtbot, window, monkeypatch):
    names = iter(["Pistike", "Petike"])
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (next(names), True))
    window.naming.setCurrentIndex(1)
    window.fixed.setChecked(True)
    window.count.setValue(1)
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 1)
    qtbot.keyClick(window, Qt.Key.Key_Space)
    assert window.worker is None
    assert window.session.current["prefix"] == "Petike"
    assert window.session.total == 1
    qtbot.keyClick(window, Qt.Key.Key_Space)
    wait_saved(qtbot, window, 2)


def test_controls_and_screenshots(qtbot, window, tmp_path, monkeypatch):
    window.paper.setCurrentText("Custom")
    assert window.width.isEnabled() and window.height.isEnabled()
    window.width.setValue(105)
    window.height.setValue(148)
    window.orientation.setCurrentIndex(1)
    window.image_format.setCurrentText("PNG")
    qtbot.mouseClick(window.fixed, Qt.MouseButton.LeftButton, pos=QPoint(10, 16))
    assert window.count.isEnabled()
    window.count.setValue(2)
    qtbot.mouseClick(window.grouped, Qt.MouseButton.LeftButton, pos=QPoint(10, 16))
    assert "aa/aa.pdf" in window.layout_hint.text()
    chosen = str(tmp_path / "chosen")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: chosen)
    qtbot.mouseClick(window.browse, Qt.MouseButton.LeftButton)
    assert window.output.text() == chosen
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    window.grab().save(str(output / "beallitasok.png"))
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 1)
    with Image.open(Path(chosen) / "aa/aa_001.png") as image:
        assert image.width > image.height
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 2)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 3)
    assert window.session.current["prefix"] == "ab"
    qtbot.mouseClick(window.new, Qt.MouseButton.LeftButton)
    assert window.session.total == 3
    assert window.session.current["prefix"] == "ac"
    window.units.setCurrentRow(0)
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: urls.append(url) or True)
    qtbot.mouseClick(window.open_output, Qt.MouseButton.LeftButton)
    assert urls[0].toLocalFile() == chosen
    window.resize(740, 580)
    qtbot.wait(50)
    window.grab().save(str(output / "scanneles-kisablak.png"))
    window.resize(1120, 820)
    qtbot.wait(50)
    window.grab().save(str(output / "scanneles.png"))
    qtbot.mouseClick(window.end, Qt.MouseButton.LeftButton)
    assert window.session is None


def test_cancel_button_and_input_error(qtbot, window, monkeypatch):
    window.output.clear()
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert window.session is None
    window.output.setText(str(Path(window.preferences.fileName()).parent / "out"))
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    assert not window.next.isEnabled()
    qtbot.mouseClick(window.cancel_scan, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 0)
    assert "cancelled" in window.status.text()


def test_search_and_device_options(qtbot, window, monkeypatch):
    import hpscan.ui as ui
    monkeypatch.setattr(ui, "discover", lambda cancel: [("test:0", "SANE test device")])
    monkeypatch.setattr(ui, "inspect_device", lambda device, cancel: {"modes": ["Gray", "Color"], "sources": ["Flatbed"]})
    qtbot.mouseClick(window.demo, Qt.MouseButton.LeftButton, pos=QPoint(10, 16))
    qtbot.mouseClick(window.detect, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.worker is None)
    assert window.device_id() == "test:0"
    qtbot.mouseClick(window.inspect, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: window.worker is None)
    assert window.mode.currentText() == "Color"
    assert window.source.currentText() == "Flatbed"
    window.devices.setEditText("hpaio:/net/manual")
    assert window.device_id() == "hpaio:/net/manual"


def test_escape_in_name_dialog_cancels_only_dialog(qtbot, window):
    window.naming.setCurrentIndex(1)
    def cancel():
        dialog = window.findChild(QInputDialog)
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    QTimer.singleShot(70, cancel)
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    assert window.session is not None
    assert window.session.current is None
    assert window.session.total == 0


def test_resume_prepares_without_scan(qtbot, window):
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 1)
    window.session.release()
    window.session = None
    window.stack.setCurrentIndex(0)
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 1)
    assert window.session.current["prefix"] == "aa"
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 2)


def test_failed_scan_does_not_advance_count(qtbot, window, monkeypatch):
    import hpscan.ui as ui
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: errors.append(text))
    def fail(*args, **kwargs):
        raise RuntimeError("device offline")
    monkeypatch.setattr(ui, "scan", fail)
    qtbot.mouseClick(window.start, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(window.next, Qt.MouseButton.LeftButton)
    wait_saved(qtbot, window, 0)
    assert errors and "device offline" in errors[0]
    assert window.next.isEnabled()
