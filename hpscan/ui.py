from __future__ import annotations

import json
import tempfile
import threading
import traceback
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSettings, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from . import __version__
from .model import PAPERS, Session, Settings, validate_prefix
from .scanner import ScanCancelled, discover, inspect_device, scan


STYLE = """
QWidget { color: #202d28; background: #f3f4f1; font-size: 14px; }
QLabel { background: transparent; }
QGroupBox { border: 1px solid #758078; margin-top: 14px; padding: 16px 12px 10px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {
    background: #ffffff; border: 1px solid #758078; border-radius: 3px; padding: 6px; min-height: 24px;
}
QPushButton { background: #ffffff; border: 1px solid #758078; border-radius: 4px; padding: 9px 16px; min-height: 26px; }
QPushButton:hover { background: #e4e9e4; border-color: #284a3b; }
QPushButton:pressed { background: #cdd9d1; }
QPushButton:disabled { color: #5c665f; background: #e1e4df; border-color: #adb3ad; }
QPushButton[primary="true"] { color: #ffffff; background: #235740; border: 2px solid #235740; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #17432f; }
QPushButton[primary="true"]:pressed { background: #103322; }
QPushButton[primary="true"]:disabled { color: #f3f4f1; background: #53695c; border-color: #53695c; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QListWidget:focus {
    border: 2px solid #235740;
}
QCheckBox { spacing: 9px; min-height: 32px; }
QCheckBox:focus { outline: 2px solid #235740; }
QLabel[title="true"] { font-size: 25px; font-weight: 650; }
QLabel[secondary="true"] { color: #4c5d53; }
QLabel#preview { background: #dce1dc; border: 1px solid #758078; padding: 12px; }
QProgressBar { border: 1px solid #758078; text-align: center; min-height: 12px; }
QProgressBar::chunk { background: #235740; }
QListWidget::item:selected { background: #235740; color: white; }
"""


def label(text, *, title=False, secondary=False):
    widget = QLabel(text)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if title:
        widget.setProperty("title", True)
    if secondary:
        widget.setProperty("secondary", True)
    return widget


def button(text, callback, *, primary=False):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setProperty("primary", primary)
    widget.clicked.connect(callback)
    return widget


class Worker(QThread):
    result = Signal(object)
    error = Signal(str)
    cancelled = Signal()
    phase = Signal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.cancel = threading.Event()

    def run(self):
        try:
            self.result.emit(self.operation(self))
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:
            traceback.print_exc()
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.setWindowTitle(f"HP Scan · dokumentumegységek · {__version__}")
        self.resize(1120, 820)
        self.setMinimumSize(740, 580)
        self.setStyleSheet(STYLE)
        self.session = None
        self.worker = None
        self.preview_image = QPixmap()
        self.preferences = QSettings("FedoraMultiScan", "HPScan")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._setup_view(demo)
        self._scan_view()
        for key, callback in (("Ctrl+Return", self.next_scan), ("Ctrl+N", self.new_unit), ("Ctrl+Q", self.finish)):
            shortcut = QShortcut(QKeySequence(key), self, callback)
            shortcut.setAutoRepeat(False)
        self.scan_shortcuts = []
        for key, callback in (("T", self.next_scan), ("Space", self.next_scan),
                              ("U", self.new_unit), ("V", self.finish), ("Esc", self.finish)):
            shortcut = QShortcut(QKeySequence(key), self, callback)
            shortcut.setAutoRepeat(False)
            shortcut.setEnabled(False)
            self.scan_shortcuts.append(shortcut)
        self.stack.currentChanged.connect(lambda index: [s.setEnabled(index == 1) for s in self.scan_shortcuts])
        self.statusBar().showMessage("Beállítás után indítsd az első lap beolvasását.")

    def _setup_view(self, demo):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.addWidget(label("Dolgozatonként külön PDF", title=True))
        layout.addWidget(label("Állítsd be a beolvasást, majd lapcsere után elég a Tovább gombot megnyomni.", secondary=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        device_box = QGroupBox("Scanner")
        form = QFormLayout(device_box)
        self.demo = QCheckBox("Próbaüzem, scanner nélkül (szimulált lapok)")
        self.demo.setChecked(demo)
        form.addRow(self.demo)
        self.devices = QComboBox()
        self.devices.setEditable(True)
        self.devices.setMinimumContentsLength(15)
        self.devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.devices.setToolTip("A keresésből válassz eszközt, vagy add meg a teljes SANE-azonosítót, például hpaio:/net/…")
        self.devices.setEditText(self.preferences.value("device", ""))
        row = QHBoxLayout()
        row.addWidget(self.devices, 1)
        self.detect = button("Eszközök keresése", self.find_devices)
        row.addWidget(self.detect)
        device_label = QLabel("&Eszköz / SANE-azonosító:")
        device_label.setBuddy(self.devices)
        form.addRow(device_label, row)
        self.inspect = button("Eszköz beállításainak lekérése", self.get_options)
        form.addRow(self.inspect)
        self.mode = QComboBox()
        self.mode.setEditable(True)
        self.mode.addItems(["Color", "Gray", "Lineart"])
        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.addItem("")
        self.source.setToolTip("Üresen a scanner alapértelmezett forrása. Az M130nw síkágyas eszköz.")
        form.addRow("&Színmód (eszközfüggő):", self.mode)
        form.addRow("&Forrás (üres = alapérték):", self.source)
        self.device_status = label("A készüléknek bekapcsolva és USB-n vagy hálózaton elérhetőnek kell lennie.", secondary=True)
        form.addRow(self.device_status)
        self.demo.toggled.connect(self._demo_changed)
        body.addWidget(device_box)

        paper_box = QGroupBox("Lap és kép")
        form = QFormLayout(paper_box)
        self.paper = QComboBox()
        self.paper.addItems([*PAPERS, "Egyedi"])
        self.paper.currentTextChanged.connect(self._paper_changed)
        self.width = QDoubleSpinBox()
        self.width.setRange(10, 215.9)
        self.width.setDecimals(1)
        self.width.setSuffix(" mm")
        self.height = QDoubleSpinBox()
        self.height.setRange(10, 297)
        self.height.setDecimals(1)
        self.height.setSuffix(" mm")
        dimensions = QHBoxLayout()
        dimensions.addWidget(self.width)
        dimensions.addWidget(label("×"))
        dimensions.addWidget(self.height)
        self.orientation = QComboBox()
        self.orientation.addItems(["Álló", "Fekvő (90° balra forgatás mentéskor)"])
        self.dpi = QComboBox()
        self.dpi.addItems(["75", "100", "150", "200", "300", "400", "600", "1200"])
        self.dpi.setCurrentText("600")
        self.image_format = QComboBox()
        self.image_format.addItems(["JPG", "PNG"])
        form.addRow("&Papírméret:", self.paper)
        form.addRow("Szélesség × magasság:", dimensions)
        self.width.setAccessibleName("Lap szélessége milliméterben")
        self.height.setAccessibleName("Lap magassága milliméterben")
        form.addRow("&Tájolás:", self.orientation)
        form.addRow("&Felbontás (dpi):", self.dpi)
        form.addRow("&Képformátum (+ PDF):", self.image_format)
        form.addRow(label("A rövid oldal legyen az üveg szélességén. Fekvő lapnál a szöveg teteje az üveg jobb széle felé nézzen. Maximum 215,9 × 297 mm; a fekvő A4-et a program forgatja el.", secondary=True))
        self._paper_changed("A4")
        body.addWidget(paper_box)

        output_box = QGroupBox("Egységek és mentés")
        form = QFormLayout(output_box)
        self.output = QLineEdit(self.preferences.value("output", str(Path.home() / "Dokumentumok" / "Scannelés")))
        row = QHBoxLayout()
        row.addWidget(self.output, 1)
        self.browse = button("Mappa választása…", self.choose_folder)
        row.addWidget(self.browse)
        output_label = QLabel("Mentési &mappa:")
        output_label.setBuddy(self.output)
        form.addRow(output_label, row)
        self.output.setAccessibleName("Mentési mappa")
        self.naming = QComboBox()
        self.naming.addItems(["Automatikus: aa, ab, ac, …", "Egyedi: minden egység előtt megadom"])
        form.addRow("&Előtagok:", self.naming)
        self.fixed = QCheckBox("Adott számú scan után automatikusan új egység")
        self.count = QSpinBox()
        self.count.setRange(1, 9999)
        self.count.setValue(5)
        self.count.setSuffix(" oldal / egység")
        self.count.setEnabled(False)
        self.count.setAccessibleName("Scanek száma egy egységben")
        self.fixed.toggled.connect(self.count.setEnabled)
        row = QHBoxLayout()
        row.addWidget(self.fixed)
        row.addWidget(self.count)
        form.addRow(row)
        self.grouped = QCheckBox("Csoportosítás: minden egység külön almappába")
        form.addRow(self.grouped)
        self.layout_hint = label("", secondary=True)
        form.addRow(self.layout_hint)
        self.grouped.toggled.connect(self.update_hint)
        self.image_format.currentTextChanged.connect(self.update_hint)
        self.naming.currentIndexChanged.connect(self.update_hint)
        self.update_hint()
        body.addWidget(output_box)
        body.addStretch()
        self.start = button("Munka előkészítése", self.start_session, primary=True)
        layout.addWidget(self.start)
        self.stack.addWidget(page)
        self._demo_changed(demo)

    def _scan_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        self.heading = label("", title=True)
        self.summary = label("", secondary=True)
        layout.addWidget(self.heading)
        layout.addWidget(self.summary)
        splitter = QSplitter()
        left = QWidget()
        side = QVBoxLayout(left)
        side.setContentsMargins(0, 0, 12, 0)
        side.addWidget(label("Mentett egységek"))
        self.units = QListWidget()
        self.units.setAccessibleName("Mentett egységek és oldalszámok")
        self.units.currentRowChanged.connect(self.select_unit)
        side.addWidget(self.units, 1)
        self.open_output = button("Mentési mappa megnyitása", self.open_folder)
        side.addWidget(self.open_output)
        self.preview = label("Még nincs beolvasott lap. Helyezd az első lapot az üvegre.")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(220, 220)
        self.preview.setAccessibleName("A legutóbb beolvasott lap előnézete")
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self.status = label("Helyezd a következő lapot az üvegre.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        self.cancel_scan = button("Beolvasás megszakítása", self.cancel_operation)
        self.cancel_scan.setVisible(False)
        layout.addWidget(self.cancel_scan)
        row = QHBoxLayout()
        self.next = button("Tovább", self.next_scan, primary=True)
        self.next.setToolTip("Következő lap beolvasása. T vagy Space (Ctrl+Enter is használható)")
        self.new = button("Új egység", self.new_unit)
        self.new.setToolTip("Következő egység előkészítése beolvasás nélkül. U (vagy Ctrl+N)")
        self.end = button("Vége", self.finish)
        self.end.setToolTip("A munka lezárása. V vagy Esc (Ctrl+Q is használható)")
        row.addWidget(self.next, 2)
        row.addWidget(self.new, 1)
        row.addWidget(self.end, 1)
        layout.addLayout(row)
        layout.addWidget(label("T / Space: beolvasás     U: új egység     V / Esc: vége. Új egység és névmegadás után a program vár a beolvasásra.", secondary=True))
        self.stack.addWidget(page)

    def _demo_changed(self, checked):
        for widget in (self.devices, self.detect, self.inspect, self.mode, self.source):
            widget.setEnabled(not checked)

    def _paper_changed(self, name):
        custom = name == "Egyedi"
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)
        if not custom and name in PAPERS:
            self.width.setValue(PAPERS[name][0])
            self.height.setValue(PAPERS[name][1])

    def update_hint(self):
        prefix = "aa" if self.naming.currentIndex() == 0 else "Pistike"
        ext = self.image_format.currentText().lower()
        if self.grouped.isChecked():
            text = f"{prefix}/{prefix}.pdf és {prefix}/{prefix}_001.{ext}"
        else:
            text = f"{prefix}.pdf és images/{prefix}_001.{ext}"
        self.layout_hint.setText("Mentési minta: " + text)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Scannelés mentési mappája", self.output.text())
        if path:
            self.output.setText(path)

    def device_id(self):
        i = self.devices.currentIndex()
        if i >= 0 and self.devices.currentText() == self.devices.itemText(i):
            return self.devices.itemData(i) or self.devices.currentText().strip()
        return self.devices.currentText().strip()

    def busy(self):
        return self.worker is not None

    def launch(self, operation, callback, *, scanning=False):
        if self.busy():
            return
        worker = Worker(operation, self)
        self.worker = worker
        self.start.setEnabled(False)
        self.detect.setEnabled(False)
        self.inspect.setEnabled(False)
        self.demo.setEnabled(False)
        for widget in (self.next, self.new, self.end):
            widget.setEnabled(False)
        self.progress.setVisible(scanning)
        self.cancel_scan.setVisible(scanning)
        self.cancel_scan.setEnabled(True)
        worker.result.connect(callback)
        worker.error.connect(self.operation_error)
        worker.cancelled.connect(lambda: self.status.setText("A beolvasás megszakítva. A mentett lapok megmaradtak."))
        worker.phase.connect(self.status.setText)
        worker.finished.connect(self.operation_done)
        worker.start()

    def operation_done(self):
        old, self.worker = self.worker, None
        if old:
            old.deleteLater()
        self.start.setEnabled(True)
        self.demo.setEnabled(True)
        self._demo_changed(self.demo.isChecked())
        self.progress.setVisible(False)
        self.cancel_scan.setVisible(False)
        for widget in (self.next, self.new, self.end):
            widget.setEnabled(True)
        self.refresh()
        if self.session:
            self.next.setFocus()

    def operation_error(self, message):
        self.status.setText("A művelet nem fejeződött be. A már mentett lapok megmaradtak.")
        self.device_status.setText("A művelet nem sikerült. Ellenőrizd a készüléket és az illesztőprogramot.")
        QMessageBox.warning(self, "A művelet nem sikerült", message)

    def find_devices(self):
        self.device_status.setText("Scannerek keresése USB-n és a hálózaton…")
        def found(devices):
            self.devices.clear()
            for device, name in devices:
                self.devices.addItem(f"{name} · {device}", device)
            if devices:
                preferred = next((i for i, (d, n) in enumerate(devices) if "m130" in (d+n).lower()), 0)
                self.devices.setCurrentIndex(preferred)
            self.device_status.setText(f"{len(devices)} eszköz található. Kérd le a kiválasztott eszköz beállításait." if devices else "Nem található scanner. Kapcsold be a készüléket, vagy válaszd a próbaüzemet.")
        self.launch(lambda w: discover(w.cancel), found)

    def get_options(self):
        device = self.device_id()
        if not device:
            QMessageBox.information(self, "Scanner kiválasztása", "Előbb keress vagy adj meg egy scannert.")
            return
        self.device_status.setText("Scanner beállításainak lekérése…")
        def received(options):
            for combo, values in ((self.mode, options["modes"]), (self.source, options["sources"])):
                if values:
                    combo.clear()
                    combo.addItems(values)
            for text in ("Color", "Flatbed", "FlatBed", "Platen"):
                for combo in (self.mode, self.source):
                    if combo.findText(text) >= 0:
                        combo.setCurrentText(text)
            self.device_status.setText("A színmódok és a források frissültek. A felbontás és a méret támogatását a tényleges beolvasás is ellenőrzi.")
        self.launch(lambda w: inspect_device(device, w.cancel), received)

    def read_settings(self):
        output = self.output.text().strip()
        if not output:
            raise ValueError("Válassz mentési mappát.")
        return Settings(output=output, device=self.device_id(), demo=self.demo.isChecked(),
                        width=self.width.value(), height=self.height.value(), landscape=self.orientation.currentIndex() == 1,
                        dpi=int(self.dpi.currentText()), image_format=self.image_format.currentText().lower(),
                        automatic=self.naming.currentIndex() == 0, group_folders=self.grouped.isChecked(),
                        pages_per_unit=self.count.value() if self.fixed.isChecked() else 0,
                        mode=self.mode.currentText().strip(), source=self.source.currentText().strip())

    def start_session(self):
        if self.busy():
            return
        try:
            settings = self.read_settings()
            pending = Session.unfinished(settings.output)
            resume = None
            if pending:
                answer = QMessageBox.question(self, "Félbehagyott munka", "Ebben a mappában félbehagyott munka van. Folytatod a legutóbbit az eredeti beállításaival?\n\nIgen: folytatás. Nem: új munka, a meglévő fájlok megtartásával.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
                if answer == QMessageBox.StandardButton.Cancel:
                    return
                if answer == QMessageBox.StandardButton.Yes:
                    resume = pending[0]
                    saved = json.loads(resume.read_text())
                    settings = Settings(**saved["settings"])
                    settings.output = self.output.text().strip()
            self.session = Session(settings, resume)
            self.preferences.setValue("output", str(self.session.root))
            self.preferences.setValue("device", settings.device)
            self.stack.setCurrentIndex(1)
            self.statusBar().showMessage("Beolvasás: T / Space. Új egység: U. Befejezés: V / Esc.")
            self.refresh()
            if resume:
                self.status.setText("A félbehagyott munka helyreállítása…")
                self.launch(lambda w: self.session.recover(), lambda _: self.status.setText("Munka helyreállítva. Lapcsere után nyomd meg a Tovább gombot."), scanning=True)
            else:
                self.ensure_unit()
                self.refresh()
                self.status.setText("A munka előkészítve. Helyezd a lapot az üvegre, majd Tovább, T vagy Space.")
                self.next.setFocus()
        except Exception as exc:
            QMessageBox.warning(self, "A munka nem indult el", str(exc))

    def ensure_unit(self, force=False):
        if not self.session:
            return False
        if not force and not self.session.needs_unit:
            return True
        if self.session.current and not self.session.current["pages"]:
            return True
        prefix = None
        if not self.session.settings.automatic:
            while True:
                prefix, ok = QInputDialog.getText(self, "Új egység előtagja", "Név / előtag (például Pistike):")
                self.activateWindow()
                self.next.setFocus()
                if not ok:
                    return False
                try:
                    prefix = validate_prefix(prefix)
                    if self.session.prefix_used(prefix):
                        raise ValueError("Ez az előtag már foglalt ebben a mappában. Adj másik nevet.")
                    break
                except ValueError as exc:
                    QMessageBox.warning(self, "Érvénytelen előtag", str(exc))
        self.session.start_unit(prefix)
        return True

    def next_scan(self):
        if not self.session or self.busy() or self.stack.currentIndex() != 1:
            return
        try:
            prompted = self.session.needs_unit and not self.session.settings.automatic
            if not self.ensure_unit():
                return
            if prompted:
                self.refresh()
                self.status.setText("Az új egység előkészítve. Helyezd a lapot az üvegre, majd Tovább, T vagy Space.")
                return
        except Exception as exc:
            self.operation_error(str(exc))
            return
        self.refresh()
        self.status.setText("Beolvasás folyamatban. A lapot még ne mozdítsd el.")
        def operation(worker):
            session = self.session
            session.recover()
            if session.needs_unit:
                raise ValueError("A helyreállítás során az egység megtelt. Nyomd meg újra a Tovább gombot az új egységhez.")
            # A nyers lap is a céllemezen van, így mentési hiba után kinyerhető.
            fd, name = tempfile.mkstemp(prefix="raw-", suffix=".pnm", dir=session.meta)
            import os
            os.close(fd)
            raw = Path(name)
            try:
                warnings = scan(session.settings, raw, worker.cancel, session.total + 1)
                if worker.cancel.is_set():
                    raise ScanCancelled()
                worker.phase.emit("Kép és PDF mentése. A lapot már kicserélheted.")
                path = session.add_page(raw)
            except ScanCancelled:
                raw.unlink(missing_ok=True)
                raise
            except Exception as exc:
                if raw.stat().st_size == 0:
                    raw.unlink(missing_ok=True)
                else:
                    raise RuntimeError(f"{exc}\n\nA nyers beolvasás megmaradt itt:\n{raw}") from exc
                raise
            else:
                raw.unlink(missing_ok=True)
                return path, warnings
        def saved(result):
            path, warnings = result
            self.show_preview(path)
            limit = self.session.settings.pages_per_unit
            text = f"Mentve: {path.name} és {self.session.current['prefix']}.pdf."
            if self.session.needs_unit and limit:
                text += f" Az egység kész ({limit} oldal). A Tovább már új egységet indít."
            else:
                text += " Cseréld ki a lapot, majd Tovább vagy Új egység."
            if warnings and not self.session.settings.demo:
                text += " Scanner üzenete: " + warnings[-1000:]
            self.status.setText(text)
        self.launch(operation, saved, scanning=True)

    def new_unit(self):
        if not self.session or self.busy():
            return
        try:
            if self.ensure_unit(force=True):
                self.refresh()
                self.status.setText("Az új egység előkészítve. Helyezd a lapot az üvegre, majd Tovább, T vagy Space.")
        except Exception as exc:
            self.operation_error(str(exc))

    def cancel_operation(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_scan.setEnabled(False)
            self.status.setText("Megszakítás kérése… A már megkezdett mentés befejeződik.")

    def refresh(self):
        if not self.session:
            return
        session = self.session
        unit = session.current
        title = f"{unit['prefix']} · {len(unit['pages'])} oldal" if unit else "Első egység"
        if session.settings.demo:
            title = "Próbaüzem · " + title
        self.heading.setText(title)
        s = session.settings
        self.summary.setText(f"Összesen {session.total} oldal · {s.dpi} dpi · {s.width:g} × {s.height:g} mm · {'fekvő' if s.landscape else 'álló'} · {s.image_format.upper()} + PDF\n{session.root}")
        self.units.blockSignals(True)
        self.units.clear()
        for u in session.data["units"]:
            state = "kész" if u["closed"] or (s.pages_per_unit and len(u["pages"]) >= s.pages_per_unit) else "aktuális"
            if u["pdf_pages"] != len(u["pages"]):
                state = "PDF helyreállításra vár"
            self.units.addItem(f"{u['prefix']}.pdf\n{len(u['pages'])} oldal · {state}")
        self.units.setCurrentRow(self.units.count() - 1)
        self.units.blockSignals(False)
        if unit and unit["pages"]:
            self.show_preview(session.image_path(unit, len(unit["pages"])))
        self.next.setText("Tovább · új egység" if session.needs_unit and unit else "Tovább")

    def select_unit(self, row):
        if self.session and not self.busy() and 0 <= row < len(self.session.data["units"]):
            unit = self.session.data["units"][row]
            if unit["pages"]:
                self.show_preview(self.session.image_path(unit, len(unit["pages"])))

    def show_preview(self, path):
        try:
            with Image.open(path) as image:
                image.thumbnail((1200, 1400))
                image = image.convert("RGB")
                qimage = QImage(image.tobytes(), image.width, image.height, image.width * 3, QImage.Format.Format_RGB888).copy()
            self.preview_image = QPixmap.fromImage(qimage)
            self.scale_preview()
        except Exception as exc:
            self.preview.setText("Az előnézet nem nyitható meg: " + str(exc))

    def scale_preview(self):
        if not self.preview_image.isNull():
            size = self.preview.size()
            size.setWidth(max(40, size.width() - 28))
            size.setHeight(max(40, size.height() - 28))
            self.preview.setPixmap(self.preview_image.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "preview"):
            self.scale_preview()

    def open_folder(self):
        if self.session:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.session.root)))

    def finish(self):
        if self.busy():
            return
        if not self.session:
            self.close()
            return
        try:
            total = self.session.total
            self.session.finish()
            self.session = None
            QMessageBox.information(self, "A munka befejeződött", f"{total} oldal mentve. Az egységek PDF-jei és képei a választott mappában vannak.")
            self.preview_image = QPixmap()
            self.preview.clear()
            self.preview.setText("Még nincs beolvasott lap.")
            self.stack.setCurrentIndex(0)
            self.statusBar().showMessage("A munka befejeződött. Új munkát indíthatsz.")
        except Exception as exc:
            self.operation_error(str(exc))

    def closeEvent(self, event):
        if self.busy():
            self.cancel_operation()
            self.statusBar().showMessage("Várd meg a művelet végét, majd zárd be az ablakot.")
            event.ignore()
            return
        if self.session:
            answer = QMessageBox.question(self, "Munka bezárása", "Bezárod az ablakot? A munka félbehagyva megmarad, és ugyanebben a mappában folytatható. A Vége gomb végleg lezárja a munkát.")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.session.release()
        event.accept()
