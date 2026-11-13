"""Capture the running demo UI using only synthetic documents.

Usage: capture-screenshots.py [en|hu] [output folder]
"""
import sys
from pathlib import Path
import tempfile
import time

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit

import hpscan.ui as ui
from hpscan.i18n import tr


language = sys.argv[1] if len(sys.argv) > 1 else "en"
app = QApplication([])
app.setStyle("Fusion")
app.setFont(QFont("Sans Serif", 10))
capture_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/screenshots")
capture_dir.mkdir(parents=True, exist_ok=True)
temporary = tempfile.TemporaryDirectory(prefix="fedora-multi-scan-demo-")
ui.QSettings = lambda *a: QSettings(str(Path(temporary.name) / "settings.ini"), QSettings.Format.IniFormat)
window = ui.MainWindow(demo=True, language=language)
window.output.setText(str(Path(temporary.name) / "Scans"))
window.fixed.setChecked(True)
window.count.setValue(5)
window.resize(1120, 1200)
window.show()
window.activateWindow()


def settle():
    for _ in range(4):
        app.processEvents()
        time.sleep(0.03)


settle()
window.grab().save(str(capture_dir / "settings.png"))
window.resize(1120, 820)
window.start_session()
settle()
for _ in range(7):
    window.next_scan()
    while window.worker is not None:
        app.processEvents()
        time.sleep(0.02)
settle()
window.grab().save(str(capture_dir / "scanning.png"))
window.session.finish()
window.session = None
window.stack.setCurrentIndex(0)
window.naming.setCurrentIndex(1)
window.grouped.setChecked(True)


def capture_dialog():
    dialog = window.findChild(QInputDialog)
    field = dialog.findChild(QLineEdit)
    field.setText(tr("Alice"))
    settle()
    dialog.grab().save(str(capture_dir / "name-dialog.png"))
    dialog.accept()


QTimer.singleShot(100, capture_dialog)
window.start_session()
settle()
assert window.session.total == 0
window.session.finish()
window.session = None
window.close()
temporary.cleanup()
print("Screenshots captured from the demo UI; no scans after accepting a name.")
