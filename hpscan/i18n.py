"""Interface languages: English (default) and Hungarian.

English strings are written in the code; `tr()` looks them up in `HU` when the
Hungarian interface is selected. tests/test_i18n.py checks that every string
passed to `tr()` has a Hungarian entry and that no entry is left unused.
"""
from __future__ import annotations

LANGUAGES = {"en": "English", "hu": "Magyar"}
DEFAULT_LANGUAGE = "en"
_language = DEFAULT_LANGUAGE


def language():
    return _language


def set_language(code):
    global _language
    _language = code if code in LANGUAGES else DEFAULT_LANGUAGE
    return _language


def tr(text, **values):
    if _language == "hu":
        text = HU[text]
    return text.format(**values) if values else text


HU = {
    # Command line
    "Fedora Multi Scan: scan document groups into separate PDFs": "Fedora Multi Scan: dokumentumegységek scannelése külön PDF-ekbe",
    "Demo mode without a scanner": "Próbaüzem scanner nélkül",
    "Headless output test into an empty folder": "Fej nélküli mentési próba egy üres mappába",
    "FOLDER": "MAPPA",
    "Interface language (default: the last one used, initially English)": "A felület nyelve (alapérték: a legutóbb használt, kezdetben angol)",
    "OK: 3 images, aa.pdf (2 pages), ab.pdf (1 page): {folder}": "OK: 3 kép, aa.pdf (2 oldal), ab.pdf (1 oldal): {folder}",

    # Window and setup view
    "HP Scan · document groups · {version}": "HP Scan · dokumentumegységek · {version}",
    "Set up the scan, then start the first page.": "Beállítás után indítsd az első lap beolvasását.",
    "A separate PDF for every document": "Dolgozatonként külön PDF",
    "Set up the scan; after each page change, pressing Continue is enough.": "Állítsd be a beolvasást, majd lapcsere után elég a Tovább gombot megnyomni.",
    "&Language:": "&Nyelv:",
    "Interface language": "A felület nyelve",
    "Scanner": "Scanner",
    "Demo mode, without a scanner (simulated pages)": "Próbaüzem, scanner nélkül (szimulált lapok)",
    "Pick a device from the search, or enter a full SANE identifier such as hpaio:/net/…": "A keresésből válassz eszközt, vagy add meg a teljes SANE-azonosítót, például hpaio:/net/…",
    "Search for devices": "Eszközök keresése",
    "&Device / SANE identifier:": "&Eszköz / SANE-azonosító:",
    "Load the device's options": "Eszköz beállításainak lekérése",
    "Empty means the scanner's default source. The M130nw is a flatbed device.": "Üresen a scanner alapértelmezett forrása. Az M130nw síkágyas eszköz.",
    "&Colour mode (device-specific):": "&Színmód (eszközfüggő):",
    "&Source (empty = default):": "&Forrás (üres = alapérték):",
    "The device must be switched on and reachable over USB or the network.": "A készüléknek bekapcsolva és USB-n vagy hálózaton elérhetőnek kell lennie.",
    "Page and image": "Lap és kép",
    "Custom": "Egyedi",
    "Portrait": "Álló",
    "Landscape (rotated 90° left when saved)": "Fekvő (90° balra forgatás mentéskor)",
    "&Paper size:": "&Papírméret:",
    "Width × height:": "Szélesség × magasság:",
    "Page width in millimetres": "Lap szélessége milliméterben",
    "Page height in millimetres": "Lap magassága milliméterben",
    "&Orientation:": "&Tájolás:",
    "&Resolution (dpi):": "&Felbontás (dpi):",
    "&Image format (+ PDF):": "&Képformátum (+ PDF):",
    "Put the short edge across the width of the glass. For a landscape page, the top of the text must point to the right edge of the glass. Maximum 215.9 × 297 mm; the app rotates landscape A4.": "A rövid oldal legyen az üveg szélességén. Fekvő lapnál a szöveg teteje az üveg jobb széle felé nézzen. Maximum 215,9 × 297 mm; a fekvő A4-et a program forgatja el.",
    "Groups and output": "Egységek és mentés",
    "Scans": "Scannelés",
    "Choose folder…": "Mappa választása…",
    "Output &folder:": "Mentési &mappa:",
    "Output folder": "Mentési mappa",
    "Automatic: aa, ab, ac, …": "Automatikus: aa, ab, ac, …",
    "Custom: I name every group": "Egyedi: minden egység előtt megadom",
    "Prefi&xes:": "&Előtagok:",
    "Start a new group automatically after a set number of scans": "Adott számú scan után automatikusan új egység",
    " pages / group": " oldal / egység",
    "Number of scans in a group": "Scanek száma egy egységben",
    "Group folders: every group in its own subfolder": "Csoportosítás: minden egység külön almappába",
    "Prepare session": "Munka előkészítése",
    "Alice": "Pistike",
    "{prefix}/{prefix}.pdf and {prefix}/{prefix}_001.{ext}": "{prefix}/{prefix}.pdf és {prefix}/{prefix}_001.{ext}",
    "{prefix}.pdf and images/{prefix}_001.{ext}": "{prefix}.pdf és images/{prefix}_001.{ext}",
    "Output pattern: {pattern}": "Mentési minta: {pattern}",
    "Output folder for the scans": "Scannelés mentési mappája",

    # Scan view
    "Saved groups": "Mentett egységek",
    "Saved groups and page counts": "Mentett egységek és oldalszámok",
    "Open output folder": "Mentési mappa megnyitása",
    "No page has been scanned yet. Put the first page on the glass.": "Még nincs beolvasott lap. Helyezd az első lapot az üvegre.",
    "Preview of the most recently scanned page": "A legutóbb beolvasott lap előnézete",
    "Put the next page on the glass.": "Helyezd a következő lapot az üvegre.",
    "Cancel scan": "Beolvasás megszakítása",
    "Continue": "Tovább",
    "Continue · new group": "Tovább · új egység",
    "Scan the next page. Space, C or T (Ctrl+Enter also works)": "Következő lap beolvasása. T vagy Space (Ctrl+Enter is használható)",
    "New group": "Új egység",
    "Prepare the next group without scanning. N or U (or Ctrl+N)": "Következő egység előkészítése beolvasás nélkül. U (vagy Ctrl+N)",
    "Finish": "Vége",
    "Finish the session. F, V or Esc (Ctrl+Q also works)": "A munka lezárása. V vagy Esc (Ctrl+Q is használható)",
    "Space / C: scan     N: new group     F / Esc: finish. After a new group or a name entry the app waits for you to start the scan.": "T / Space: beolvasás     U: új egység     V / Esc: vége. Új egység és névmegadás után a program vár a beolvasásra.",
    "Scan: Space / C. New group: N. Finish: F / Esc.": "Beolvasás: T / Space. Új egység: U. Befejezés: V / Esc.",

    # Status and dialogs
    "Scan cancelled. The saved pages have been kept.": "A beolvasás megszakítva. A mentett lapok megmaradtak.",
    "The operation did not complete. Pages already saved have been kept.": "A művelet nem fejeződött be. A már mentett lapok megmaradtak.",
    "The operation failed. Check the device and its driver.": "A művelet nem sikerült. Ellenőrizd a készüléket és az illesztőprogramot.",
    "The operation failed": "A művelet nem sikerült",
    "Searching for scanners over USB and the network…": "Scannerek keresése USB-n és a hálózaton…",
    "{count} device(s) found. Load the options of the selected device.": "{count} eszköz található. Kérd le a kiválasztott eszköz beállításait.",
    "No scanner found. Switch the device on, or choose demo mode.": "Nem található scanner. Kapcsold be a készüléket, vagy válaszd a próbaüzemet.",
    "Select a scanner": "Scanner kiválasztása",
    "Search for a scanner or enter one first.": "Előbb keress vagy adj meg egy scannert.",
    "Loading the scanner's options…": "Scanner beállításainak lekérése…",
    "Colour modes and sources have been updated. Support for the resolution and size is also checked by the actual scan.": "A színmódok és a források frissültek. A felbontás és a méret támogatását a tényleges beolvasás is ellenőrzi.",
    "Choose an output folder.": "Válassz mentési mappát.",
    "Unfinished session": "Félbehagyott munka",
    "This folder contains an unfinished session. Resume the latest one with its original settings?\n\nYes: resume. No: start a new session and keep the existing files.": "Ebben a mappában félbehagyott munka van. Folytatod a legutóbbit az eredeti beállításaival?\n\nIgen: folytatás. Nem: új munka, a meglévő fájlok megtartásával.",
    "Recovering the unfinished session…": "A félbehagyott munka helyreállítása…",
    "Session recovered. After changing the page, press Continue.": "Munka helyreállítva. Lapcsere után nyomd meg a Tovább gombot.",
    "Session prepared. Put the page on the glass, then press Continue, Space or C.": "A munka előkészítve. Helyezd a lapot az üvegre, majd Tovább, T vagy Space.",
    "The session did not start": "A munka nem indult el",
    "Prefix for the new group": "Új egység előtagja",
    "Name / prefix (for example Alice):": "Név / előtag (például Pistike):",
    "This prefix is already taken in this folder. Enter a different name.": "Ez az előtag már foglalt ebben a mappában. Adj másik nevet.",
    "Invalid prefix": "Érvénytelen előtag",
    "New group prepared. Put the page on the glass, then press Continue, Space or C.": "Az új egység előkészítve. Helyezd a lapot az üvegre, majd Tovább, T vagy Space.",
    "Scanning. Do not move the page yet.": "Beolvasás folyamatban. A lapot még ne mozdítsd el.",
    "The group filled up during recovery. Press Continue again for the new group.": "A helyreállítás során az egység megtelt. Nyomd meg újra a Tovább gombot az új egységhez.",
    "Saving the image and the PDF. You can change the page now.": "Kép és PDF mentése. A lapot már kicserélheted.",
    "{error}\n\nThe raw scan has been kept here:\n{path}": "{error}\n\nA nyers beolvasás megmaradt itt:\n{path}",
    "Saved: {image} and {prefix}.pdf.": "Mentve: {image} és {prefix}.pdf.",
    " The group is complete ({limit} pages). Continue now starts a new group.": " Az egység kész ({limit} oldal). A Tovább már új egységet indít.",
    " Change the page, then press Continue or New group.": " Cseréld ki a lapot, majd Tovább vagy Új egység.",
    " Scanner message: {message}": " Scanner üzenete: {message}",
    "Cancelling… A save that has already started will complete.": "Megszakítás kérése… A már megkezdett mentés befejeződik.",
    "{prefix} · {count} page(s)": "{prefix} · {count} oldal",
    "First group": "Első egység",
    "Demo mode · {title}": "Próbaüzem · {title}",
    "landscape": "fekvő",
    "portrait": "álló",
    "{total} page(s) in total · {dpi} dpi · {width:g} × {height:g} mm · {orientation} · {format} + PDF\n{folder}": "Összesen {total} oldal · {dpi} dpi · {width:g} × {height:g} mm · {orientation} · {format} + PDF\n{folder}",
    "done": "kész",
    "current": "aktuális",
    "PDF waiting for recovery": "PDF helyreállításra vár",
    "{prefix}.pdf\n{count} page(s) · {state}": "{prefix}.pdf\n{count} oldal · {state}",
    "The preview cannot be opened: {error}": "Az előnézet nem nyitható meg: {error}",
    "Session finished": "A munka befejeződött",
    "{total} page(s) saved. The groups' PDFs and images are in the chosen folder.": "{total} oldal mentve. Az egységek PDF-jei és képei a választott mappában vannak.",
    "No page has been scanned yet.": "Még nincs beolvasott lap.",
    "The session is finished. You can start a new one.": "A munka befejeződött. Új munkát indíthatsz.",
    "Wait for the operation to end, then close the window.": "Várd meg a művelet végét, majd zárd be az ablakot.",
    "Close session": "Munka bezárása",
    "Close the window? The session stays unfinished and can be resumed in the same folder. The Finish button closes the session for good.": "Bezárod az ablakot? A munka félbehagyva megmarad, és ugyanebben a mappában folytatható. A Vége gomb végleg lezárja a munkát.",

    # Settings and session rules
    "The scan area must be 10–215.9 mm wide and 10–297 mm high.": "A beolvasási terület 10–215,9 mm széles és 10–297 mm magas lehet.",
    "Enter the shorter side as the width; choose landscape orientation separately.": "A rövidebb oldalt add meg szélességként; a fekvő tájolást külön válaszd ki.",
    "Unsupported resolution.": "Nem támogatott felbontás.",
    "The image format must be JPG or PNG.": "A képformátum JPG vagy PNG lehet.",
    "The group size must be between 1 and 9999 pages.": "Az egységméret 1 és 9999 közötti oldalszám lehet.",
    "Choose a scanner, or switch on demo mode.": "Válassz scannert, vagy kapcsold be a próbaüzemet.",
    "Negative index.": "Negatív index.",
    "Enter a valid prefix of at most 100 bytes. Accented letters and spaces are allowed; / \\ : * ? and a leading dot are not.": "Adj meg érvényes, legfeljebb 100 bájtos előtagot. Ékezet és szóköz használható; / \\ : * ? és kezdő pont nem.",
    "The .hpscan folder must not be a symbolic link.": "A .hpscan mappa nem lehet szimbolikus hivatkozás.",
    "A scanning session is already running in this folder in another window.": "Ebben a mappában már folyik scannelés egy másik ablakban.",
    "Invalid session journal.": "Érvénytelen munkanapló.",
    "This session has already been finished.": "Ezt a munkát már lezártad.",
    "The session is already finished.": "A munka már befejeződött.",
    "The prefix {prefix} is already taken. Enter a different name; existing files are never overwritten.": "A(z) {prefix} előtag már foglalt. Adj másik nevet; meglévő fájlt nem írunk felül.",
    "The output subfolder must not be a symbolic link.": "A mentési almappa nem lehet szimbolikus hivatkozás.",
    "Start a new group first.": "Előbb indíts új egységet.",
    "Unexpected existing PDF; it will not be overwritten: {path}": "Váratlan meglévő PDF; nem írjuk felül: {path}",

    # Scanner access
    "scanimage is missing. Install it on this machine: sudo dnf install sane-backends sane-airscan hplip hplip-libs": "Hiányzik a scanimage. A használati gépen telepítsd: sudo dnf install sane-backends sane-airscan hplip hplip-libs",
    "The scanner did not respond in time. Check the connection, then try again.": "A scanner nem válaszolt a megadott időn belül. Ellenőrizd a kapcsolatot, majd próbáld újra.",
    "The scanner reported an error ({code}):\n{error}\n\nFor an HP device, check HPLIP and, if needed, that hp-plugin is installed.": "A scanner hibát jelzett ({code}):\n{error}\n\nHP eszköznél ellenőrizd a HPLIP-et és szükség esetén a hp-plugin telepítését.",
    "HP Scan\nDEMO MODE\n\nScan {number}\n{width:g} x {height:g} mm\n{dpi} dpi\n\nThis is a simulated test page.": "HP Scan\nPROBAUZEM\n\n{number}. beolvasas\n{width:g} x {height:g} mm\n{dpi} dpi\n\nEz szimulalt tesztlap.",
    "Simulated page created.": "Szimulált lap elkészült.",
    "The scanner rounded to a different resolution. Choose a supported dpi value.\n{warnings}": "A scanner más felbontásra kerekített. Válassz támogatott dpi értéket.\n{warnings}",
    "The size or resolution returned by the scanner differs from the request. Received: {width} × {height} pixels; expected: {expected_width} × {expected_height}. Check the device settings.": "A scanner mérete vagy felbontása eltér a kért értéktől. Kapott: {width} × {height} képpont; várt: {expected_width} × {expected_height}. Ellenőrizd az eszköz beállításait.",
    "The scanner did not return a job identifier.": "A scanner nem adott vissza feladatazonosítót.",
    "The scanner did not accept the scan request (HTTP {code}).": "A scanner nem fogadta el a beolvasási kérést (HTTP {code}).",
    "The scanner aborted the scan before the page was ready. Try again; if it keeps happening, choose a lower resolution.": "A scanner megszakította a beolvasást, mielőtt a lap elkészült volna. Próbáld újra; ha ismétlődik, válassz kisebb felbontást.",
    "The scanner reported an error while the page was being downloaded (HTTP {code}).": "A scanner hibát jelzett a lap letöltésekor (HTTP {code}).",
    "The scanner did not finish the page in time.": "A scanner nem készült el a lappal a megadott időn belül.",
    "{count} images on the page": "{count} kép az oldalon",
    "The PDF sent by the scanner cannot be read: {error}": "A scanner által küldött PDF nem értelmezhető: {error}",
    "The scanner cannot be reached: {error}": "A scanner nem érhető el: {error}",
    "The connection to the scanner was lost: {error}": "A kapcsolat megszakadt a scannerrel: {error}",
}
