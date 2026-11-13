from __future__ import annotations

import json
import tempfile
import threading
import traceback
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QStandardPaths, Qt, QThread, QTranslator, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from . import __version__, i18n
from .i18n import tr
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


CUSTOM_PAPER = "custom"
_qt_translator = None


def default_output():
    documents = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return str(Path(documents or Path.home()) / tr("Scans"))


def apply_language(code):
    """Sets the app language, the number format and Qt's own dialog button texts."""
    global _qt_translator
    code = i18n.set_language(code)
    QLocale.setDefault(QLocale("hu_HU" if code == "hu" else "en_US"))
    app = QApplication.instance()
    if app:
        if _qt_translator:
            app.removeTranslator(_qt_translator)
            _qt_translator = None
        translator = QTranslator(app)
        # English is Qt's source language; other languages need the qtbase catalogue.
        if code != "en" and translator.load(f"qtbase_{code}", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            app.installTranslator(translator)
            _qt_translator = translator
    return code


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
    def __init__(self, demo=False, language=None):
        super().__init__()
        self.resize(1120, 820)
        self.setMinimumSize(740, 580)
        self.setStyleSheet(STYLE)
        self.session = None
        self.worker = None
        self.preview_image = QPixmap()
        self.preferences = QSettings("FedoraMultiScan", "HPScan")
        apply_language(language or self.preferences.value("language", i18n.DEFAULT_LANGUAGE))
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_views(demo)
        for key, callback in (("Ctrl+Return", self.next_scan), ("Ctrl+N", self.new_unit), ("Ctrl+Q", self.finish)):
            shortcut = QShortcut(QKeySequence(key), self, callback)
            shortcut.setAutoRepeat(False)
        self.scan_shortcuts = []
        # T/U/V are the Hungarian mnemonics (Tovább, Új egység, Vége), C/N/F the
        # English ones (Continue, New group, Finish); all work in both languages.
        for key, callback in (("Space", self.next_scan), ("T", self.next_scan), ("C", self.next_scan),
                              ("U", self.new_unit), ("N", self.new_unit),
                              ("V", self.finish), ("F", self.finish), ("Esc", self.finish)):
            shortcut = QShortcut(QKeySequence(key), self, callback)
            shortcut.setAutoRepeat(False)
            shortcut.setEnabled(False)
            self.scan_shortcuts.append(shortcut)
        self.stack.currentChanged.connect(lambda index: [s.setEnabled(index == 1) for s in self.scan_shortcuts])

    def _build_views(self, demo):
        self.setLocale(QLocale())  # new child widgets take the number format from here
        self.setWindowTitle(tr("HP Scan · document groups · {version}", version=__version__))
        self._setup_view(demo)
        self._scan_view()
        self.statusBar().showMessage(tr("Set up the scan, then start the first page."))

    def change_language(self, code):
        """Rebuilds both views in the chosen language, keeping what was entered."""
        if code == i18n.language() or self.session or self.busy():
            return
        combos = (self.devices, self.mode, self.source)
        items = [[(c.itemText(i), c.itemData(i)) for i in range(c.count())] for c in combos]
        texts = [(c.currentIndex(), c.currentText()) for c in combos]
        indexes = {name: getattr(self, name).currentIndex() for name in ("paper", "orientation", "dpi", "image_format", "naming")}
        checks = {name: getattr(self, name).isChecked() for name in ("demo", "fixed", "grouped")}
        size, count, status = (self.width.value(), self.height.value()), self.count.value(), self.device_status.text()
        output = self.output.text()
        untouched = (output == default_output(), status == tr("The device must be switched on and reachable over USB or the network."))
        apply_language(code)
        self.preferences.setValue("language", code)
        while self.stack.count():
            page = self.stack.widget(0)
            self.stack.removeWidget(page)
            page.deleteLater()
        self._build_views(checks["demo"])
        for combo, entries, (index, text) in zip((self.devices, self.mode, self.source), items, texts):
            combo.clear()
            for name, data in entries:
                combo.addItem(name, data)
            combo.setCurrentIndex(index)
            combo.setEditText(text)
        for name, index in indexes.items():
            getattr(self, name).setCurrentIndex(index)
        self.width.setValue(size[0])
        self.height.setValue(size[1])
        self.count.setValue(count)
        self.fixed.setChecked(checks["fixed"])
        self.grouped.setChecked(checks["grouped"])
        self.output.setText(default_output() if untouched[0] else output)
        if not untouched[1]:
            self.device_status.setText("")
        self.languages.setFocus()

    def _setup_view(self, demo):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        top = QHBoxLayout()
        top.addWidget(label(tr("A separate PDF for every document"), title=True), 1)
        self.languages = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.languages.addItem(name, code)
        self.languages.setCurrentIndex(self.languages.findData(i18n.language()))
        self.languages.setAccessibleName(tr("Interface language"))
        self.languages.activated.connect(lambda index: self.change_language(self.languages.itemData(index)))
        language_label = QLabel(tr("&Language:"))
        language_label.setBuddy(self.languages)
        top.addWidget(language_label)
        top.addWidget(self.languages)
        layout.addLayout(top)
        layout.addWidget(label(tr("Set up the scan; after each page change, pressing Continue is enough."), secondary=True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        device_box = QGroupBox(tr("Scanner"))
        form = QFormLayout(device_box)
        self.demo = QCheckBox(tr("Demo mode, without a scanner (simulated pages)"))
        self.demo.setChecked(demo)
        form.addRow(self.demo)
        self.devices = QComboBox()
        self.devices.setEditable(True)
        self.devices.setMinimumContentsLength(15)
        self.devices.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.devices.setToolTip(tr("Pick a device from the search, or enter a full SANE identifier such as hpaio:/net/…"))
        self.devices.setEditText(self.preferences.value("device", ""))
        row = QHBoxLayout()
        row.addWidget(self.devices, 1)
        self.detect = button(tr("Search for devices"), self.find_devices)
        row.addWidget(self.detect)
        device_label = QLabel(tr("&Device / SANE identifier:"))
        device_label.setBuddy(self.devices)
        form.addRow(device_label, row)
        self.inspect = button(tr("Load the device's options"), self.get_options)
        form.addRow(self.inspect)
        self.mode = QComboBox()
        self.mode.setEditable(True)
        self.mode.addItems(["Color", "Gray", "Lineart"])
        self.source = QComboBox()
        self.source.setEditable(True)
        self.source.addItem("")
        self.source.setToolTip(tr("Empty means the scanner's default source. The M130nw is a flatbed device."))
        form.addRow(tr("&Colour mode (device-specific):"), self.mode)
        form.addRow(tr("&Source (empty = default):"), self.source)
        self.device_status = label(tr("The device must be switched on and reachable over USB or the network."), secondary=True)
        form.addRow(self.device_status)
        self.demo.toggled.connect(self._demo_changed)
        body.addWidget(device_box)

        paper_box = QGroupBox(tr("Page and image"))
        form = QFormLayout(paper_box)
        self.paper = QComboBox()
        self.paper.addItems(PAPERS)
        self.paper.addItem(tr("Custom"), CUSTOM_PAPER)
        self.paper.currentIndexChanged.connect(self._paper_changed)
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
        self.orientation.addItems([tr("Portrait"), tr("Landscape (rotated 90° left when saved)")])
        self.dpi = QComboBox()
        self.dpi.addItems(["75", "100", "150", "200", "300", "400", "600", "1200"])
        self.dpi.setCurrentText("600")
        self.image_format = QComboBox()
        self.image_format.addItems(["JPG", "PNG"])
        form.addRow(tr("&Paper size:"), self.paper)
        form.addRow(tr("Width × height:"), dimensions)
        self.width.setAccessibleName(tr("Page width in millimetres"))
        self.height.setAccessibleName(tr("Page height in millimetres"))
        form.addRow(tr("&Orientation:"), self.orientation)
        form.addRow(tr("&Resolution (dpi):"), self.dpi)
        form.addRow(tr("&Image format (+ PDF):"), self.image_format)
        form.addRow(label(tr("Put the short edge across the width of the glass. For a landscape page, the top of the text must point to the right edge of the glass. Maximum 215.9 × 297 mm; the app rotates landscape A4."), secondary=True))
        self._paper_changed()
        body.addWidget(paper_box)

        output_box = QGroupBox(tr("Groups and output"))
        form = QFormLayout(output_box)
        self.output = QLineEdit(self.preferences.value("output", default_output()))
        row = QHBoxLayout()
        row.addWidget(self.output, 1)
        self.browse = button(tr("Choose folder…"), self.choose_folder)
        row.addWidget(self.browse)
        output_label = QLabel(tr("Output &folder:"))
        output_label.setBuddy(self.output)
        form.addRow(output_label, row)
        self.output.setAccessibleName(tr("Output folder"))
        self.naming = QComboBox()
        self.naming.addItems([tr("Automatic: aa, ab, ac, …"), tr("Custom: I name every group")])
        form.addRow(tr("Prefi&xes:"), self.naming)
        self.fixed = QCheckBox(tr("Start a new group automatically after a set number of scans"))
        self.count = QSpinBox()
        self.count.setRange(1, 9999)
        self.count.setValue(5)
        self.count.setSuffix(tr(" pages / group"))
        self.count.setEnabled(False)
        self.count.setAccessibleName(tr("Number of scans in a group"))
        self.fixed.toggled.connect(self.count.setEnabled)
        row = QHBoxLayout()
        row.addWidget(self.fixed)
        row.addWidget(self.count)
        form.addRow(row)
        self.grouped = QCheckBox(tr("Group folders: every group in its own subfolder"))
        form.addRow(self.grouped)
        self.layout_hint = label("", secondary=True)
        form.addRow(self.layout_hint)
        self.grouped.toggled.connect(self.update_hint)
        self.image_format.currentTextChanged.connect(self.update_hint)
        self.naming.currentIndexChanged.connect(self.update_hint)
        self.update_hint()
        body.addWidget(output_box)
        body.addStretch()
        self.start = button(tr("Prepare session"), self.start_session, primary=True)
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
        side.addWidget(label(tr("Saved groups")))
        self.units = QListWidget()
        self.units.setAccessibleName(tr("Saved groups and page counts"))
        self.units.currentRowChanged.connect(self.select_unit)
        side.addWidget(self.units, 1)
        self.open_output = button(tr("Open output folder"), self.open_folder)
        side.addWidget(self.open_output)
        self.preview = label(tr("No page has been scanned yet. Put the first page on the glass."))
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(220, 220)
        self.preview.setAccessibleName(tr("Preview of the most recently scanned page"))
        splitter.addWidget(left)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)
        self.status = label(tr("Put the next page on the glass."))
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        self.cancel_scan = button(tr("Cancel scan"), self.cancel_operation)
        self.cancel_scan.setVisible(False)
        layout.addWidget(self.cancel_scan)
        row = QHBoxLayout()
        self.next = button(tr("Continue"), self.next_scan, primary=True)
        self.next.setToolTip(tr("Scan the next page. Space, C or T (Ctrl+Enter also works)"))
        self.new = button(tr("New group"), self.new_unit)
        self.new.setToolTip(tr("Prepare the next group without scanning. N or U (or Ctrl+N)"))
        self.end = button(tr("Finish"), self.finish)
        self.end.setToolTip(tr("Finish the session. F, V or Esc (Ctrl+Q also works)"))
        row.addWidget(self.next, 2)
        row.addWidget(self.new, 1)
        row.addWidget(self.end, 1)
        layout.addLayout(row)
        layout.addWidget(label(tr("Space / C: scan     N: new group     F / Esc: finish. After a new group or a name entry the app waits for you to start the scan."), secondary=True))
        self.stack.addWidget(page)

    def _demo_changed(self, checked):
        for widget in (self.devices, self.detect, self.inspect, self.mode, self.source):
            widget.setEnabled(not checked)

    def _paper_changed(self, *_):
        name = self.paper.currentText()
        custom = self.paper.currentData() == CUSTOM_PAPER
        self.width.setEnabled(custom)
        self.height.setEnabled(custom)
        if not custom and name in PAPERS:
            self.width.setValue(PAPERS[name][0])
            self.height.setValue(PAPERS[name][1])

    def update_hint(self):
        prefix = "aa" if self.naming.currentIndex() == 0 else tr("Alice")
        ext = self.image_format.currentText().lower()
        if self.grouped.isChecked():
            text = tr("{prefix}/{prefix}.pdf and {prefix}/{prefix}_001.{ext}", prefix=prefix, ext=ext)
        else:
            text = tr("{prefix}.pdf and images/{prefix}_001.{ext}", prefix=prefix, ext=ext)
        self.layout_hint.setText(tr("Output pattern: {pattern}", pattern=text))

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("Output folder for the scans"), self.output.text())
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
        worker.cancelled.connect(lambda: self.status.setText(tr("Scan cancelled. The saved pages have been kept.")))
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
        self.status.setText(tr("The operation did not complete. Pages already saved have been kept."))
        self.device_status.setText(tr("The operation failed. Check the device and its driver."))
        QMessageBox.warning(self, tr("The operation failed"), message)

    def find_devices(self):
        self.device_status.setText(tr("Searching for scanners over USB and the network…"))
        def found(devices):
            self.devices.clear()
            for device, name in devices:
                self.devices.addItem(f"{name} · {device}", device)
            if devices:
                preferred = next((i for i, (d, n) in enumerate(devices) if "m130" in (d+n).lower()), 0)
                self.devices.setCurrentIndex(preferred)
            self.device_status.setText(tr("{count} device(s) found. Load the options of the selected device.", count=len(devices)) if devices else tr("No scanner found. Switch the device on, or choose demo mode."))
        self.launch(lambda w: discover(w.cancel), found)

    def get_options(self):
        device = self.device_id()
        if not device:
            QMessageBox.information(self, tr("Select a scanner"), tr("Search for a scanner or enter one first."))
            return
        self.device_status.setText(tr("Loading the scanner's options…"))
        def received(options):
            for combo, values in ((self.mode, options["modes"]), (self.source, options["sources"])):
                if values:
                    combo.clear()
                    combo.addItems(values)
            for text in ("Color", "Flatbed", "FlatBed", "Platen"):
                for combo in (self.mode, self.source):
                    if combo.findText(text) >= 0:
                        combo.setCurrentText(text)
            self.device_status.setText(tr("Colour modes and sources have been updated. Support for the resolution and size is also checked by the actual scan."))
        self.launch(lambda w: inspect_device(device, w.cancel), received)

    def read_settings(self):
        output = self.output.text().strip()
        if not output:
            raise ValueError(tr("Choose an output folder."))
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
                answer = QMessageBox.question(self, tr("Unfinished session"), tr("This folder contains an unfinished session. Resume the latest one with its original settings?\n\nYes: resume. No: start a new session and keep the existing files."), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
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
            self.statusBar().showMessage(tr("Scan: Space / C. New group: N. Finish: F / Esc."))
            self.refresh()
            if resume:
                self.status.setText(tr("Recovering the unfinished session…"))
                self.launch(lambda w: self.session.recover(), lambda _: self.status.setText(tr("Session recovered. After changing the page, press Continue.")), scanning=True)
            else:
                self.ensure_unit()
                self.refresh()
                self.status.setText(tr("Session prepared. Put the page on the glass, then press Continue, Space or C."))
                self.next.setFocus()
        except Exception as exc:
            QMessageBox.warning(self, tr("The session did not start"), str(exc))

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
                prefix, ok = QInputDialog.getText(self, tr("Prefix for the new group"), tr("Name / prefix (for example Alice):"))
                self.activateWindow()
                self.next.setFocus()
                if not ok:
                    return False
                try:
                    prefix = validate_prefix(prefix)
                    if self.session.prefix_used(prefix):
                        raise ValueError(tr("This prefix is already taken in this folder. Enter a different name."))
                    break
                except ValueError as exc:
                    QMessageBox.warning(self, tr("Invalid prefix"), str(exc))
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
                self.status.setText(tr("New group prepared. Put the page on the glass, then press Continue, Space or C."))
                return
        except Exception as exc:
            self.operation_error(str(exc))
            return
        self.refresh()
        self.status.setText(tr("Scanning. Do not move the page yet."))
        def operation(worker):
            session = self.session
            session.recover()
            if session.needs_unit:
                raise ValueError(tr("The group filled up during recovery. Press Continue again for the new group."))
            # A nyers lap is a céllemezen van, így mentési hiba után kinyerhető.
            fd, name = tempfile.mkstemp(prefix="raw-", suffix=".pnm", dir=session.meta)
            import os
            os.close(fd)
            raw = Path(name)
            try:
                warnings = scan(session.settings, raw, worker.cancel, session.total + 1)
                if worker.cancel.is_set():
                    raise ScanCancelled()
                worker.phase.emit(tr("Saving the image and the PDF. You can change the page now."))
                path = session.add_page(raw)
            except ScanCancelled:
                raw.unlink(missing_ok=True)
                raise
            except Exception as exc:
                if raw.stat().st_size == 0:
                    raw.unlink(missing_ok=True)
                else:
                    raise RuntimeError(tr("{error}\n\nThe raw scan has been kept here:\n{path}", error=exc, path=raw)) from exc
                raise
            else:
                raw.unlink(missing_ok=True)
                return path, warnings
        def saved(result):
            path, warnings = result
            self.show_preview(path)
            limit = self.session.settings.pages_per_unit
            text = tr("Saved: {image} and {prefix}.pdf.", image=path.name, prefix=self.session.current["prefix"])
            if self.session.needs_unit and limit:
                text += tr(" The group is complete ({limit} pages). Continue now starts a new group.", limit=limit)
            else:
                text += tr(" Change the page, then press Continue or New group.")
            if warnings and not self.session.settings.demo:
                text += tr(" Scanner message: {message}", message=warnings[-1000:])
            self.status.setText(text)
        self.launch(operation, saved, scanning=True)

    def new_unit(self):
        if not self.session or self.busy():
            return
        try:
            if self.ensure_unit(force=True):
                self.refresh()
                self.status.setText(tr("New group prepared. Put the page on the glass, then press Continue, Space or C."))
        except Exception as exc:
            self.operation_error(str(exc))

    def cancel_operation(self):
        if self.worker:
            self.worker.cancel.set()
            self.cancel_scan.setEnabled(False)
            self.status.setText(tr("Cancelling… A save that has already started will complete."))

    def refresh(self):
        if not self.session:
            return
        session = self.session
        unit = session.current
        title = tr("{prefix} · {count} page(s)", prefix=unit["prefix"], count=len(unit["pages"])) if unit else tr("First group")
        if session.settings.demo:
            title = tr("Demo mode · {title}", title=title)
        self.heading.setText(title)
        s = session.settings
        self.summary.setText(tr("{total} page(s) in total · {dpi} dpi · {width:g} × {height:g} mm · {orientation} · {format} + PDF\n{folder}",
                                total=session.total, dpi=s.dpi, width=s.width, height=s.height,
                                orientation=tr("landscape") if s.landscape else tr("portrait"),
                                format=s.image_format.upper(), folder=session.root))
        self.units.blockSignals(True)
        self.units.clear()
        for u in session.data["units"]:
            state = tr("done") if u["closed"] or (s.pages_per_unit and len(u["pages"]) >= s.pages_per_unit) else tr("current")
            if u["pdf_pages"] != len(u["pages"]):
                state = tr("PDF waiting for recovery")
            self.units.addItem(tr("{prefix}.pdf\n{count} page(s) · {state}", prefix=u["prefix"], count=len(u["pages"]), state=state))
        self.units.setCurrentRow(self.units.count() - 1)
        self.units.blockSignals(False)
        if unit and unit["pages"]:
            self.show_preview(session.image_path(unit, len(unit["pages"])))
        self.next.setText(tr("Continue · new group") if session.needs_unit and unit else tr("Continue"))

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
            self.preview.setText(tr("The preview cannot be opened: {error}", error=exc))

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
            QMessageBox.information(self, tr("Session finished"), tr("{total} page(s) saved. The groups' PDFs and images are in the chosen folder.", total=total))
            self.preview_image = QPixmap()
            self.preview.clear()
            self.preview.setText(tr("No page has been scanned yet."))
            self.stack.setCurrentIndex(0)
            self.statusBar().showMessage(tr("The session is finished. You can start a new one."))
        except Exception as exc:
            self.operation_error(str(exc))

    def closeEvent(self, event):
        if self.busy():
            self.cancel_operation()
            self.statusBar().showMessage(tr("Wait for the operation to end, then close the window."))
            event.ignore()
            return
        if self.session:
            answer = QMessageBox.question(self, tr("Close session"), tr("Close the window? The session stays unfinished and can be resumed in the same folder. The Finish button closes the session for good."))
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.session.release()
        event.accept()
