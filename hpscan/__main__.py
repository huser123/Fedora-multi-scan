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
        print(f"OK: 3 kép, aa.pdf (2 oldal), ab.pdf (1 oldal): {session.root}")
    finally:
        session.release()


def main():
    parser = argparse.ArgumentParser(description="HP Scan: dokumentumegységek scannelése")
    parser.add_argument("--demo", action="store_true", help="Próbaüzem scanner nélkül")
    parser.add_argument("--smoke-test", metavar="MAPPA", help="Fej nélküli mentési próba egy üres mappába")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test(args.smoke_test)
        return
    from PySide6.QtCore import QLocale
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication
    from .ui import MainWindow
    QLocale.setDefault(QLocale("hu_HU"))
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setFont(QFont("Sans Serif", 10))
    app.setApplicationName("HP Scan")
    window = MainWindow(demo=args.demo)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
