import ast
import threading
from pathlib import Path
from string import Formatter

import pytest
from PIL import Image
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QMessageBox

import hpscan
from hpscan import i18n
from hpscan.i18n import HU, tr
from hpscan.model import Session, Settings, validate_prefix
from hpscan.scanner import scan


def source_strings():
    """Every string literal passed to tr() in the package."""
    found = set()
    for path in Path(hpscan.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr":
                first = node.args[0]
                assert isinstance(first, ast.Constant) and isinstance(first.value, str), \
                    f"{path.name}:{node.lineno}: tr() needs a string literal"
                found.add(first.value)
    return found


def fields(text):
    return sorted(name for _, name, _, _ in Formatter().parse(text) if name)


def test_every_string_is_translated_and_nothing_is_stale():
    used = source_strings()
    assert len(used) > 100
    assert used - set(HU) == set()
    assert set(HU) - used == set()


def test_translations_keep_placeholders_and_mnemonics():
    for english, hungarian in HU.items():
        assert hungarian.strip(), english
        assert fields(english) == fields(hungarian), english
        assert english.count("&") == hungarian.count("&"), english
        assert english.startswith(" ") == hungarian.startswith(" "), english


def test_language_selection():
    assert i18n.language() == "en"
    assert tr("Finish") == "Finish"
    assert i18n.set_language("hu") == "hu"
    assert tr("Finish") == "Vége"
    assert tr("Saved: {image} and {prefix}.pdf.", image="aa_001.jpg", prefix="aa") == "Mentve: aa_001.jpg és aa.pdf."
    assert i18n.set_language("xx") == "en"


def test_errors_follow_the_language(tmp_path):
    with pytest.raises(ValueError, match="valid prefix"):
        validate_prefix("a/b")
    i18n.set_language("hu")
    with pytest.raises(ValueError, match="érvényes"):
        validate_prefix("a/b")
    with pytest.raises(ValueError, match="scannert"):
        Session(Settings(output=str(tmp_path)))


def test_demo_page_in_both_languages(tmp_path):
    settings = Settings(output=str(tmp_path), demo=True, dpi=75, width=105, height=148)
    pages = []
    for code in ("en", "hu"):
        i18n.set_language(code)
        path = tmp_path / f"{code}.png"
        scan(settings, path, threading.Event())
        with Image.open(path) as image:
            pages.append(image.tobytes())
    assert pages[0] != pages[1]


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    import hpscan.ui as ui
    monkeypatch.setattr(ui, "QSettings", lambda *a: QSettings(str(tmp_path / "config.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    made = []

    def make(**options):
        widget = ui.MainWindow(demo=True, **options)
        qtbot.addWidget(widget)
        widget.show()
        made.append(widget)
        return widget
    yield make
    for widget in made:
        if widget.session:
            widget.session.release()
            widget.session = None
    ui.apply_language("en")


def test_english_is_the_default_and_the_choice_is_remembered(qtbot, window):
    first = window()
    assert first.start.text() == "Prepare session"
    assert [first.languages.itemText(i) for i in range(2)] == ["English", "Magyar"]
    first.change_language("hu")
    assert first.start.text() == "Munka előkészítése"
    assert first.languages.currentData() == "hu"
    assert "dokumentumegységek" in first.windowTitle()
    second = window()
    assert second.start.text() == "Munka előkészítése"
    third = window(language="en")
    assert third.start.text() == "Prepare session"


def test_switching_keeps_what_was_entered(qtbot, window, tmp_path):
    widget = window()
    widget.demo.setChecked(False)
    widget.devices.addItem("HP · airscan:e0:HP", "airscan:e0:HP")
    widget.devices.addItem("Test · test:0", "test:0")
    widget.devices.setCurrentIndex(1)
    widget.mode.setCurrentText("Gray")
    widget.paper.setCurrentText("Custom")
    widget.width.setValue(100)
    widget.height.setValue(200)
    widget.orientation.setCurrentIndex(1)
    widget.dpi.setCurrentText("300")
    widget.image_format.setCurrentText("PNG")
    widget.naming.setCurrentIndex(1)
    widget.fixed.setChecked(True)
    widget.count.setValue(7)
    widget.grouped.setChecked(True)
    widget.output.setText(str(tmp_path / "out"))
    widget.languages.setCurrentIndex(widget.languages.findData("hu"))
    widget.languages.activated.emit(widget.languages.currentIndex())
    assert widget.paper.currentText() == "Egyedi"
    assert widget.width.isEnabled() and (widget.width.value(), widget.height.value()) == (100, 200)
    assert widget.device_id() == "test:0"
    assert not widget.demo.isChecked() and widget.devices.isEnabled()
    assert widget.count.isEnabled() and widget.count.value() == 7
    assert "Pistike/Pistike.pdf" in widget.layout_hint.text()
    settings = widget.read_settings()
    assert (settings.mode, settings.dpi, settings.image_format, settings.landscape) == ("Gray", 300, "png", True)
    assert (settings.automatic, settings.group_folders, settings.pages_per_unit) == (False, True, 7)
    assert settings.output == str(tmp_path / "out")


def test_default_output_folder_follows_the_language(qtbot, window):
    widget = window()
    assert Path(widget.output.text()).name == "Scans"
    widget.change_language("hu")
    assert Path(widget.output.text()).name == "Scannelés"


def test_hungarian_session_and_both_sets_of_keys(qtbot, window, tmp_path):
    widget = window(language="hu")
    widget.output.setText(str(tmp_path / "scans"))
    widget.paper.setCurrentText("A6")
    widget.dpi.setCurrentText("150")
    widget.activateWindow()
    qtbot.wait(50)
    qtbot.mouseClick(widget.start, Qt.MouseButton.LeftButton)
    assert widget.next.text() == "Tovább"
    for number, key in enumerate((Qt.Key.Key_C, Qt.Key.Key_T), 1):
        qtbot.keyClick(widget, key)
        qtbot.waitUntil(lambda: widget.worker is None, timeout=15000)
        assert widget.session.total == number
    assert "oldal" in widget.heading.text() and "Mentve" in widget.status.text()
    qtbot.keyClick(widget, Qt.Key.Key_N)
    assert widget.session.current["prefix"] == "ab" and widget.session.total == 2
    widget.change_language("en")
    assert widget.next.text() == "Tovább", "the language cannot change during a session"
    qtbot.keyClick(widget, Qt.Key.Key_F)
    assert widget.session is None
