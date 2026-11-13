"""Közvetlen eSCL (AirScan) beolvasás PDF-ként.

A sane-airscan csak JPEG-et kér a készüléktől. A HP LaserJet M130nw a teljes
A4-es, 600 dpi-s színes lapot JPEG-ként kérve kb. 40 másodperc után maga
szakítja meg (JobCanceledAtDevice), PDF-ként kérve viszont hibátlanul leadja.
Ezért ha a kiválasztott airscan eszköz URL-je kiolvasható az airscan.conf-ból
és a készülék tud PDF-et, a lapot közvetlenül kérjük le, és a PDF-be ágyazott
képet mentjük ki. Minden más esetben a hívó a scanimage-re esik vissza.
"""
from __future__ import annotations

import io
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from .i18n import tr
from .model import Settings

MODES = {"Color": "RGB24", "Gray": "Grayscale8"}
PLATEN_SOURCES = {"", "Flatbed", "Platen"}
UNITS_PER_MM = 300 / 25.4  # az eSCL 1/300 hüvelykben számol
POLL_SECONDS = 0.15

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class EsclError(RuntimeError):
    pass


def config_files():
    folders = [p for p in os.environ.get("SANE_CONFIG_DIR", "").split(":") if p] or ["/etc/sane.d"]
    for folder in map(Path, folders):
        yield folder / "airscan.conf"
        extra = folder / "airscan.d"
        if extra.is_dir():
            yield from sorted(extra.glob("*.conf"))


def configured_devices():
    """Az airscan.conf [devices] szakaszában rögzített eSCL eszközök: név -> URL."""
    devices = {}
    for path in config_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        section = ""
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] in "#;":
                continue
            if line.startswith("["):
                section = line.strip("[] \t").lower()
                continue
            if section != "devices" or "=" not in line:
                continue
            name, value = (part.strip() for part in line.split("=", 1))
            name = name.strip('"')
            parts = [part.strip() for part in value.split(",")]
            protocol = parts[1].lower() if len(parts) > 1 else "escl"
            if protocol == "escl" and parts[0].lower().startswith(("http://", "https://")):
                devices[name] = parts[0] if parts[0].endswith("/") else parts[0] + "/"
    return devices


def device_url(device: str):
    match = re.fullmatch(r"airscan:e\d+:(.+)", device or "")
    return configured_devices().get(match[1]) if match else None


def request(url, *, method="GET", data=None, timeout=30):
    headers = {"Content-Type": "text/xml"} if data is not None else {}
    return _opener.open(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=timeout)


def capabilities(base):
    with request(urljoin(base, "ScannerCapabilities"), timeout=10) as response:
        return response.read().decode("utf-8", errors="replace")


def job_xml(settings: Settings, caps: str):
    def limit(tag, wanted):
        match = re.search(rf"<scan:Platen>.*?<scan:{tag}>(\d+)<", caps, re.S)
        return min(wanted, int(match[1])) if match else wanted
    width = limit("MaxWidth", round(settings.width * UNITS_PER_MM))
    height = limit("MaxHeight", round(settings.height * UNITS_PER_MM))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm" xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03">
<pwg:Version>2.0</pwg:Version>
<pwg:ScanRegions><pwg:ScanRegion><pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>
<pwg:XOffset>0</pwg:XOffset><pwg:YOffset>0</pwg:YOffset><pwg:Width>{width}</pwg:Width><pwg:Height>{height}</pwg:Height></pwg:ScanRegion></pwg:ScanRegions>
<pwg:InputSource>Platen</pwg:InputSource>
<scan:ColorMode>{MODES[settings.mode]}</scan:ColorMode>
<pwg:DocumentFormat>application/pdf</pwg:DocumentFormat>
<scan:XResolution>{settings.dpi}</scan:XResolution><scan:YResolution>{settings.dpi}</scan:YResolution>
</scan:ScanSettings>""".encode()


def supported(settings: Settings, caps: str):
    resolutions = set(re.findall(r"<scan:XResolution>(\d+)<", caps))
    return (settings.mode in MODES and settings.source in PLATEN_SOURCES
            and "<scan:Platen>" in caps and "application/pdf" in caps
            and MODES[settings.mode] in caps and str(settings.dpi) in resolutions)


def create_job(base, body, cancel, busy_timeout=30):
    deadline = time.monotonic() + busy_timeout
    while True:
        try:
            with request(urljoin(base, "ScanJobs"), method="POST", data=body) as response:
                location = response.headers.get("Location")
            if not location:
                raise EsclError(tr("The scanner did not return a job identifier."))
            # A készülék a saját IP-címével válaszol; a beállított címen maradunk
            # (az ipp-usb localhost-os átjárója miatt ez nem mindegy).
            return urljoin(base, "ScanJobs/" + urlsplit(location).path.rstrip("/").rsplit("/", 1)[-1])
        except urllib.error.HTTPError as exc:
            if exc.code != 503 or time.monotonic() > deadline:
                raise EsclError(tr("The scanner did not accept the scan request (HTTP {code}).", code=exc.code)) from exc
        if cancel.wait(1):
            from .scanner import ScanCancelled
            raise ScanCancelled()


def fetch_document(job, stop, timeout):
    """Megvárja és letölti a lapot. A 503 azt jelenti, hogy a készülék még dolgozik."""
    deadline = time.monotonic() + timeout
    while not stop.is_set():
        try:
            with request(job + "/NextDocument", timeout=120) as response:
                chunks = []
                while chunk := response.read(1 << 16):
                    if stop.is_set():
                        return None
                    chunks.append(chunk)
                return b"".join(chunks)
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 410):
                raise EsclError(tr("The scanner aborted the scan before the page was ready. Try again; if it keeps happening, choose a lower resolution.")) from exc
            if exc.code != 503:
                raise EsclError(tr("The scanner reported an error while the page was being downloaded (HTTP {code}).", code=exc.code)) from exc
            if time.monotonic() > deadline:
                raise EsclError(tr("The scanner did not finish the page in time.")) from exc
        stop.wait(1)
    return None


def delete_job(job):
    try:
        request(job, method="DELETE", timeout=5).close()
    except OSError:
        pass


def extract_image(pdf: bytes):
    from pypdf import PdfReader
    try:
        images = PdfReader(io.BytesIO(pdf)).pages[0].images
        if len(images) != 1:
            raise ValueError(tr("{count} images on the page", count=len(images)))
        return images[0].data
    except Exception as exc:
        raise EsclError(tr("The PDF sent by the scanner cannot be read: {error}", error=exc)) from exc


def scan(settings: Settings, target: Path, cancel: threading.Event, timeout=600):
    """Közvetlen eSCL beolvasás a target fájlba.

    False, ha ez az út erre az eszközre vagy beállításra nem alkalmazható
    (ilyenkor semmi nem történt a készüléken, a hívó használhatja a scanimage-et).
    """
    from .scanner import ScanCancelled
    base = device_url(settings.device)
    if not base:
        return False
    try:
        caps = capabilities(base)
    except OSError:
        return False
    if not supported(settings, caps):
        return False
    try:
        job = create_job(base, job_xml(settings, caps), cancel)
    except OSError as exc:
        raise EsclError(tr("The scanner cannot be reached: {error}", error=exc)) from exc
    result = {}
    stop = threading.Event()

    def download():
        try:
            result["data"] = fetch_document(job, stop, timeout)
        except Exception as exc:  # a hívó szálon dobjuk tovább
            result["error"] = exc

    thread = threading.Thread(target=download, daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            if cancel.wait(POLL_SECONDS):
                raise ScanCancelled()
        if cancel.is_set():
            raise ScanCancelled()
        if "error" in result:
            error = result["error"]
            raise error if isinstance(error, EsclError) else EsclError(tr("The connection to the scanner was lost: {error}", error=error)) from error
        target.write_bytes(extract_image(result["data"]))
    except BaseException:
        stop.set()
        delete_job(job)
        raise
    return True
