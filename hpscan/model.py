from __future__ import annotations

import fcntl
import ctypes
import errno
import json
import os
import re
import tempfile
import unicodedata
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import img2pdf
from PIL import Image


PAPERS = {"A4": (210.0, 297.0), "A5": (148.0, 210.0), "A6": (105.0, 148.0),
          "B5 (ISO)": (176.0, 250.0), "B5 (JIS)": (182.0, 257.0),
          "Letter": (215.9, 279.4)}
MAX_WIDTH, MAX_HEIGHT = 215.9, 297.0


@dataclass
class Settings:
    output: str
    device: str = ""
    demo: bool = False
    width: float = 210.0
    height: float = 297.0
    landscape: bool = False
    dpi: int = 600
    image_format: str = "jpg"
    automatic: bool = True
    group_folders: bool = False
    pages_per_unit: int = 0
    mode: str = "Color"
    source: str = ""

    def validate(self):
        if not (10 <= self.width <= MAX_WIDTH and 10 <= self.height <= MAX_HEIGHT):
            raise ValueError("A beolvasási terület 10–215,9 mm széles és 10–297 mm magas lehet.")
        if self.width > self.height:
            raise ValueError("A rövidebb oldalt add meg szélességként; a fekvő tájolást külön válaszd ki.")
        if self.dpi not in (75, 100, 150, 200, 300, 400, 600, 1200):
            raise ValueError("Nem támogatott felbontás.")
        if self.image_format not in ("jpg", "png"):
            raise ValueError("A képformátum JPG vagy PNG lehet.")
        if not 0 <= self.pages_per_unit <= 9999:
            raise ValueError("Az egységméret 1 és 9999 közötti oldalszám lehet.")
        if not self.demo and not self.device.strip():
            raise ValueError("Válassz scannert, vagy kapcsold be a próbaüzemet.")


def auto_prefix(index: int) -> str:
    if index < 0:
        raise ValueError("Negatív index.")
    n, result = index + 27, ""
    while n:
        n, r = divmod(n - 1, 26)
        result = chr(97 + r) + result
    return result


def validate_prefix(value: str) -> str:
    value = unicodedata.normalize("NFC", value.strip())
    if (not value or value.startswith(".") or value.endswith((".", " "))
            or len(value.encode("utf-8")) > 100
            or any(c in '<>:"/\\|?*' or unicodedata.category(c).startswith("C") for c in value)
            or value.casefold() in {"images", ".hpscan"}
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", value)):
        raise ValueError("Adj meg érvényes, legfeljebb 100 bájtos előtagot. Ékezet és szóköz használható; / \\ : * ? és kezdő pont nem.")
    return value


def atomic_write(path: Path, writer, *, replace=True):
    fd, temporary = tempfile.mkstemp(prefix=".hpscan-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            try:
                os.link(temporary, path)
            except OSError as exc:
                if exc.errno not in (errno.EPERM, errno.EOPNOTSUPP, errno.ENOSYS):
                    raise
                # FAT/exFAT nem tud hardlinket. A Fedora glibc/kernel ugyanitt
                # atomi, felülírás nélküli átnevezést is biztosít.
                rename = ctypes.CDLL(None, use_errno=True).renameat2
                rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
                rename.restype = ctypes.c_int
                if rename(-100, os.fsencode(temporary), -100, os.fsencode(path), 1) != 0:
                    error = ctypes.get_errno()
                    raise OSError(error, os.strerror(error), str(path))
        dirfd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Session:
    """A képek a PDF előtt kerülnek lemezre, így a PDF újraépíthető."""

    def __init__(self, settings: Settings, resume: Path | None = None):
        settings.validate()
        self.settings = settings
        self.root = Path(settings.output).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta = self.root / ".hpscan"
        if self.meta.is_symlink():
            raise ValueError("A .hpscan mappa nem lehet szimbolikus hivatkozás.")
        self.meta.mkdir(exist_ok=True)
        self.lock = (self.meta / "active.lock").open("a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise ValueError("Ebben a mappában már folyik scannelés egy másik ablakban.") from None
        try:
            if resume:
                if resume.resolve().parent != self.meta:
                    raise ValueError("Érvénytelen munkanapló.")
                self.path = resume
                self.data = json.loads(resume.read_text())
                if self.data["finished"]:
                    raise ValueError("Ezt a munkát már lezártad.")
                self.settings = Settings(**self.data["settings"])
                self.settings.output = str(self.root)
                self.settings.validate()
            else:
                self.path = self.meta / f"session-{uuid.uuid4().hex}.json"
                self.data = {"version": 1, "settings": asdict(settings), "units": [],
                             "auto_index": 0, "finished": False,
                             "created": datetime.now(timezone.utc).isoformat()}
                self.save()
        except Exception:
            self.release()
            raise

    @staticmethod
    def unfinished(root: str) -> list[Path]:
        result = []
        for p in (Path(root).expanduser() / ".hpscan").glob("session-*.json"):
            try:
                if not json.loads(p.read_text())["finished"]:
                    result.append(p)
            except (ValueError, KeyError, OSError):
                continue
        return sorted(result, key=lambda p: p.stat().st_mtime, reverse=True)

    @property
    def current(self):
        return self.data["units"][-1] if self.data["units"] else None

    @property
    def total(self):
        return sum(len(u["pages"]) for u in self.data["units"])

    @property
    def needs_unit(self):
        u = self.current
        return not u or u["closed"] or bool(self.settings.pages_per_unit and
                                            len(u["pages"]) >= self.settings.pages_per_unit)

    def save(self):
        atomic_write(self.path, lambda f: f.write(json.dumps(self.data, ensure_ascii=False, indent=2).encode()))

    def release(self):
        if not self.lock.closed:
            self.lock.close()

    def _paths(self, prefix):
        folder = self.root / prefix if self.settings.group_folders else self.root
        images = folder if self.settings.group_folders else self.root / "images"
        return folder, images

    def prefix_used(self, prefix):
        folded = prefix.casefold()
        if any(u["prefix"].casefold() == folded for u in self.data["units"]):
            return True
        # Az üres, félbehagyott egységnek még nincs képe, de a neve foglalt.
        # Enélkül egy másik munka képeit a helyreállítás saját lapnak vélhetné.
        for journal in self.meta.glob("session-*.json"):
            if journal == self.path:
                continue
            try:
                other = json.loads(journal.read_text())
                if not other["finished"] and any(u["prefix"].casefold() == folded for u in other["units"]):
                    return True
            except (OSError, ValueError, KeyError, TypeError):
                continue
        for folder in (self.root, self.root / "images"):
            if folder.is_dir():
                for path in folder.iterdir():
                    name = path.name.casefold()
                    if name == folded or name == folded + ".pdf" or re.fullmatch(re.escape(folded) + r"_\d+\.(jpg|jpeg|png)", name):
                        return True
        return False

    def start_unit(self, prefix: str | None = None):
        if self.data["finished"]:
            raise ValueError("A munka már befejeződött.")
        if self.current and not self.current["pages"]:
            return self.current["prefix"]
        if self.settings.automatic:
            index = self.data["auto_index"]
            prefix = auto_prefix(index)
            while self.prefix_used(prefix):
                index += 1
                prefix = auto_prefix(index)
            self.data["auto_index"] = index + 1
        else:
            prefix = validate_prefix(prefix or "")
            if self.prefix_used(prefix):
                raise ValueError(f"A(z) {prefix} előtag már foglalt. Adj másik nevet; meglévő fájlt nem írunk felül.")
        if self.current:
            self.repair_pdf()
        folder, images = self._paths(prefix)
        for directory in (folder, images):
            if directory.is_symlink():
                raise ValueError("A mentési almappa nem lehet szimbolikus hivatkozás.")
            directory.mkdir(exist_ok=True)
        if self.current:
            self.current["closed"] = True
        self.data["units"].append({"prefix": prefix, "pages": [], "pdf_pages": 0, "closed": False})
        self.save()
        return prefix

    def image_path(self, unit, number):
        _, images = self._paths(unit["prefix"])
        return images / f"{unit['prefix']}_{number:03d}.{self.settings.image_format}"

    def pdf_path(self, unit):
        folder, _ = self._paths(unit["prefix"])
        return folder / f"{unit['prefix']}.pdf"

    def add_page(self, source: Path):
        if self.data["finished"] or self.needs_unit:
            raise ValueError("Előbb indíts új egységet.")
        unit = self.current
        self.repair_pdf()
        number = len(unit["pages"]) + 1
        target = self.image_path(unit, number)
        with Image.open(source) as opened:
            image = opened.convert("RGB")
        try:
            if self.settings.landscape:
                rotated = image.transpose(Image.Transpose.ROTATE_90)
                image.close()
                image = rotated
            fmt = "JPEG" if self.settings.image_format == "jpg" else "PNG"
            options = {"quality": 95, "subsampling": 0} if fmt == "JPEG" else {"compress_level": 3}
            atomic_write(target, lambda f: image.save(f, format=fmt, dpi=(self.settings.dpi,) * 2, **options), replace=False)
        finally:
            image.close()
        unit["pages"].append(target.name)
        # A PDF-hiba után a kép és a napló megmarad, a következő művelet újraépít.
        self.save()
        self.repair_pdf()
        return target

    def repair_pdf(self):
        unit = self.current
        if not unit or not unit["pages"]:
            return
        # A kép átnevezése és a napló írása közötti megszakítást is helyreállítjuk.
        next_image = self.image_path(unit, len(unit["pages"]) + 1)
        while next_image.is_file():
            with Image.open(next_image) as im:
                im.verify()
            unit["pages"].append(next_image.name)
            next_image = self.image_path(unit, len(unit["pages"]) + 1)
        target = self.pdf_path(unit)
        if unit["pdf_pages"] == len(unit["pages"]) and target.is_file():
            return
        if target.exists() and not unit["pdf_pages"]:
            # Megszakadhatott a legelső PDF átnevezése utáni naplóírás.
            from pypdf import PdfReader
            if len(PdfReader(target).pages) == len(unit["pages"]):
                unit["pdf_pages"] = len(unit["pages"])
                self.save()
                return
            raise ValueError(f"Váratlan meglévő PDF; nem írjuk felül: {target}")
        _, images = self._paths(unit["prefix"])
        paths = [str(images / name) for name in unit["pages"]]
        layout = img2pdf.get_fixed_dpi_layout_fun((self.settings.dpi, self.settings.dpi))
        atomic_write(target, lambda f: img2pdf.convert(*paths, outputstream=f, layout_fun=layout),
                     replace=bool(unit["pdf_pages"]))
        unit["pdf_pages"] = len(unit["pages"])
        self.save()

    def recover(self):
        if self.current:
            unit = self.current
            next_image = self.image_path(unit, len(unit["pages"]) + 1)
            while next_image.is_file():
                with Image.open(next_image) as im:
                    im.verify()
                unit["pages"].append(next_image.name)
                next_image = self.image_path(unit, len(unit["pages"]) + 1)
            # Megszakadhatott a PDF átnevezése utáni naplóírás is.
            target = self.pdf_path(unit)
            if target.exists() and unit["pdf_pages"] != len(unit["pages"]):
                from pypdf import PdfReader
                if len(PdfReader(target).pages) == len(unit["pages"]):
                    unit["pdf_pages"] = len(unit["pages"])
            self.repair_pdf()
            self.save()

    def finish(self):
        self.recover()
        if self.current:
            self.current["closed"] = True
        self.data["finished"] = True
        self.save()
        self.release()
