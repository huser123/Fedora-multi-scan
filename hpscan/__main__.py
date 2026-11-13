from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def smoke_test(output):
    import threading
    from .model import Session, Settings
    from .scanner import scan
    settings = Settings(output=str(Path(output).resolve()), demo=True, dpi=150,
                        width=105, height=148, pages_per_unit=2)
    session = Session(settings)
    try:
        for number in range(3):
            if session.needs_unit:
                session.start_unit()
            raw = session.meta / "smoke.png"
            scan(settings, raw, threading.Event(), number + 1)
            session.add_page(raw)
            raw.unlink()
        session.finish()
        from pypdf import PdfReader
        assert len(PdfReader(session.root / "aa.pdf").pages) == 2
        assert len(PdfReader(session.root / "ab.pdf").pages) == 1
        from .i18n import tr
        print(tr("OK: 3 images, aa.pdf (2 pages), ab.pdf (1 page): {folder}", folder=session.root))
    finally:
        session.release()


def main():
    from .i18n import LANGUAGES, set_language, tr
    # The --lang option also selects the language of --help, so look for it first.
    early = argparse.ArgumentParser(add_help=False)
    early.add_argument("--lang", choices=LANGUAGES)
    chosen = early.parse_known_args()[0].lang
    if chosen:
        set_language(chosen)
    parser = argparse.ArgumentParser(description=tr("Fedora Multi Scan: scan document groups into separate PDFs"))
    parser.add_argument("--demo", action="store_true", help=tr("Demo mode without a scanner"))
    parser.add_argument("--lang", choices=LANGUAGES, help=tr("Interface language (default: the last one used, initially English)"))
    parser.add_argument("--smoke-test", metavar=tr("FOLDER"), help=tr("Headless output test into an empty folder"))
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test(args.smoke_test)
        return
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    from .ui import MainWindow
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Sans Serif", 10))
    app.setApplicationName("HP Scan")
    window = MainWindow(demo=args.demo, language=args.lang)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
