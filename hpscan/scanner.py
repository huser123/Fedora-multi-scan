from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import Settings


class ScanCancelled(Exception):
    pass


def host_environment():
    env = os.environ.copy()
    # A csomagolt Qt/Python könyvtárai nem kerülhetnek a rendszer scanimage folyamatába.
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    else:
        env.pop("LD_LIBRARY_PATH", None)
    env["LC_ALL"] = "C"
    return env


def scanimage_path():
    path = shutil.which("scanimage")
    if not path:
        raise RuntimeError("Hiányzik a scanimage. A használati gépen telepítsd: sudo dnf install sane-backends sane-airscan hplip hplip-libs")
    return path


def run_command(args, *, cancel=None, output=None, timeout=45):
    with subprocess.Popen(args, stdout=output if output else subprocess.PIPE,
                          stderr=subprocess.PIPE, env=host_environment()) as process:
        deadline = time.monotonic() + timeout
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.15)
                break
            except subprocess.TimeoutExpired:
                if (cancel and cancel.is_set()) or time.monotonic() > deadline:
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                    if cancel and cancel.is_set():
                        raise ScanCancelled()
                    raise RuntimeError("A scanner nem válaszolt a megadott időn belül. Ellenőrizd a kapcsolatot, majd próbáld újra.")
        if cancel and cancel.is_set():
            raise ScanCancelled()
        error = stderr.decode("utf-8", errors="replace")
        if process.returncode:
            raise RuntimeError(f"A scanner hibát jelzett ({process.returncode}):\n{error[-6000:]}\n\nHP eszköznél ellenőrizd a HPLIP-et és szükség esetén a hp-plugin telepítését.")
        return (stdout or b"").decode("utf-8", errors="replace"), error


def discover(cancel=None):
    text, _ = run_command([scanimage_path(), "--formatted-device-list=%d\t%v %m\n"], cancel=cancel)
    devices = []
    for line in text.splitlines():
        if "\t" in line:
            device, title = line.split("\t", 1)
            devices.append((device, title))
    return devices


def inspect_device(device, cancel=None):
    text, _ = run_command([scanimage_path(), "--device-name", device, "--all-options"], cancel=cancel)
    def choices(name):
        match = re.search(r"^\s*--" + name + r"\s+(.+)$", text, re.M)
        if not match:
            return []
        value = re.sub(r"\s+\[.*$", "", match[1]).strip()
        return [v.strip() for v in value.split("|") if v.strip()]
    return {"modes": choices("mode"), "sources": choices("source"), "text": text}


def scan(settings: Settings, target: Path, cancel: threading.Event, page_number=1):
    if settings.demo:
        for _ in range(6):
            if cancel.wait(0.06):
                raise ScanCancelled()
        width = round(settings.width / 25.4 * settings.dpi)
        height = round(settings.height / 25.4 * settings.dpi)
        with Image.new("RGB", (width, height), "white") as image:
            draw = ImageDraw.Draw(image)
            scale = settings.dpi / 150
            font_path = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
            if not Path(font_path).exists():
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            try:
                font = ImageFont.truetype(font_path, round(28 * scale))
            except OSError:
                font = ImageFont.load_default(size=round(28 * scale))
            margin = round(60 * scale)
            draw.rectangle((margin, margin, width-margin, height-margin), outline="#53645b", width=max(1, round(2*scale)))
            draw.multiline_text((margin*1.4, margin*1.5),
                                f"HP Scan\nPROBAUZEM\n\n{page_number}. beolvasas\n{settings.width:g} x {settings.height:g} mm\n{settings.dpi} dpi\n\nEz szimulalt tesztlap.",
                                fill="#182e25", font=font, spacing=round(14*scale))
            image.save(target, format="PNG", dpi=(settings.dpi,) * 2)
        return "Szimulált lap elkészült."
    args = [scanimage_path(), "--device-name", settings.device, "--format=pnm"]
    if settings.source:
        args += ["--source", settings.source]
    if settings.mode:
        args += ["--mode", settings.mode]
    args += ["--resolution", str(settings.dpi), "-l", "0", "-t", "0",
             "-x", f"{settings.width:g}", "-y", f"{settings.height:g}"]
    with target.open("wb") as stream:
        _, warnings = run_command(args, cancel=cancel, output=stream, timeout=600)
    # Ne címkézzünk fel 300 dpi-s képet 600 dpi-ként, ha a backend kerekített.
    if re.search(r"rounded.*(?:resolution|dpi)|(?:resolution).*rounded", warnings, re.I):
        raise RuntimeError("A scanner más felbontásra kerekített. Válassz támogatott dpi értéket.\n" + warnings)
    with Image.open(target) as image:
        expected = (round(settings.width / 25.4 * settings.dpi), round(settings.height / 25.4 * settings.dpi))
        if any(abs(actual - wanted) > max(8, wanted * 0.02) for actual, wanted in zip(image.size, expected)):
            raise RuntimeError(f"A scanner mérete vagy felbontása eltér a kért értéktől. Kapott: {image.width} × {image.height} képpont; várt: {expected[0]} × {expected[1]}. Ellenőrizd az eszköz beállításait.")
        image.verify()
    return warnings.strip()
