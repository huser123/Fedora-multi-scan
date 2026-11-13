import io
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import img2pdf
import pytest
from PIL import Image

from hpscan import escl
from hpscan.model import Settings
from hpscan.scanner import ScanCancelled, scan

DEVICE = "airscan:e0:Teszt scanner"
CAPS = """<scan:ScannerCapabilities><scan:Platen><scan:PlatenInputCaps>
<scan:MaxWidth>2550</scan:MaxWidth><scan:MaxHeight>3508</scan:MaxHeight>
<scan:ColorMode>RGB24</scan:ColorMode><scan:ColorMode>Grayscale8</scan:ColorMode>
<pwg:DocumentFormat>image/jpeg</pwg:DocumentFormat><pwg:DocumentFormat>{pdf}</pwg:DocumentFormat>
<scan:XResolution>75</scan:XResolution><scan:XResolution>600</scan:XResolution>
</scan:PlatenInputCaps></scan:Platen></scan:ScannerCapabilities>"""


def page_pdf(size=(310, 437)):
    jpeg = io.BytesIO()
    Image.new("RGB", size, "white").save(jpeg, format="JPEG", dpi=(75, 75))
    return img2pdf.convert(jpeg.getvalue())


class FakeScanner:
    """Minimális eSCL készülék: a lap előtt `busy` alkalommal 503-at ad."""

    def __init__(self, tmp_path, monkeypatch, *, busy=2, document=200, pdf="application/pdf", hang=False):
        self.requests, self.bodies = [], []
        self.busy, self.document, self.hang = busy, document, hang
        self.release = threading.Event()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, body=b"", headers=()):
                self.send_response(code)
                for name, value in headers:
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                owner.requests.append(("GET", self.path))
                if self.path == "/eSCL/ScannerCapabilities":
                    self.reply(200, CAPS.format(pdf=pdf).encode())
                elif self.path == "/eSCL/ScanJobs/7/NextDocument":
                    if owner.hang:
                        owner.release.wait(10)
                        self.reply(410)
                    elif owner.busy > 0:
                        owner.busy -= 1
                        self.reply(503)
                    elif owner.document == 200:
                        self.reply(200, page_pdf())
                    else:
                        self.reply(owner.document)
                else:
                    self.reply(404)

            def do_POST(self):
                owner.requests.append(("POST", self.path))
                owner.bodies.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
                # A valódi készülék a saját címével válaszol, nem azzal, amin megszólították.
                self.reply(201, headers=[("Location", "http://192.0.2.1:80/eSCL/ScanJobs/7")])

            def do_DELETE(self):
                owner.requests.append(("DELETE", self.path))
                owner.release.set()
                self.reply(200)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        config = tmp_path / "sane"
        config.mkdir()
        (config / "airscan.conf").write_text(
            f'[devices]\n"Teszt scanner" = http://127.0.0.1:{self.server.server_port}/eSCL, escl\n'
            '"WSD eszköz" = http://127.0.0.1:1/wsd, wsd\n[options]\ndiscovery = disable\n')
        monkeypatch.setenv("SANE_CONFIG_DIR", str(config))
        monkeypatch.setattr(escl, "fetch_document", self.fast(escl.fetch_document))

    @staticmethod
    def fast(original):
        def fetch(job, stop, timeout):
            wait = stop.wait
            stop.wait = lambda seconds: wait(0.01)
            return original(job, stop, timeout)
        return fetch

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def scanner(tmp_path, monkeypatch, request):
    fake = FakeScanner(tmp_path, monkeypatch, **getattr(request, "param", {}))
    yield fake
    fake.close()


def settings(tmp_path, **changes):
    return Settings(**{"output": str(tmp_path), "device": DEVICE, "width": 105, "height": 148, "dpi": 75, **changes})


def test_configured_devices(scanner):
    devices = escl.configured_devices()
    assert list(devices) == ["Teszt scanner"]
    assert devices["Teszt scanner"].endswith("/eSCL/")
    assert escl.device_url("airscan:w0:Teszt scanner") is None
    assert escl.device_url("hpaio:/usb/x") is None


def test_scan_requests_pdf_and_saves_image(scanner, tmp_path):
    target = tmp_path / "raw.pnm"
    scan(settings(tmp_path), target, threading.Event())
    with Image.open(target) as image:
        assert image.size == (310, 437)
    body = scanner.bodies[0]
    assert "application/pdf" in body and "RGB24" in body
    assert "<pwg:Width>1240</pwg:Width>" in body and "<pwg:Height>1748</pwg:Height>" in body
    assert scanner.requests.count(("GET", "/eSCL/ScanJobs/7/NextDocument")) == 3
    assert ("DELETE", "/eSCL/ScanJobs/7") not in scanner.requests


def test_region_is_limited_to_the_glass(scanner):
    body = escl.job_xml(Settings(output="x", device=DEVICE, width=300, height=400, dpi=75), CAPS).decode()
    assert "<pwg:Width>2550</pwg:Width>" in body and "<pwg:Height>3508</pwg:Height>" in body


@pytest.mark.parametrize("changes", [{"dpi": 150}, {"mode": "Lineart"}, {"source": "ADF"}, {"device": "airscan:e0:Ismeretlen"}])
def test_not_applicable_leaves_the_device_alone(scanner, tmp_path, changes):
    assert escl.scan(settings(tmp_path, **changes), tmp_path / "raw", threading.Event()) is False
    assert not any(method == "POST" for method, _ in scanner.requests)


@pytest.mark.parametrize("scanner", [{"pdf": "image/png"}], indirect=True)
def test_device_without_pdf_is_not_applicable(scanner, tmp_path):
    assert escl.scan(settings(tmp_path), tmp_path / "raw", threading.Event()) is False


@pytest.mark.parametrize("scanner", [{"document": 410}], indirect=True)
def test_job_aborted_by_device(scanner, tmp_path):
    with pytest.raises(escl.EsclError, match="megszakította"):
        scan(settings(tmp_path), tmp_path / "raw", threading.Event())
    assert ("DELETE", "/eSCL/ScanJobs/7") in scanner.requests


@pytest.mark.parametrize("scanner", [{"hang": True}], indirect=True)
def test_cancel_deletes_the_job(scanner, tmp_path):
    cancel = threading.Event()
    timer = threading.Timer(0.3, cancel.set)
    timer.start()
    try:
        with pytest.raises(ScanCancelled):
            scan(settings(tmp_path), tmp_path / "raw", cancel)
    finally:
        timer.cancel()
    assert ("DELETE", "/eSCL/ScanJobs/7") in scanner.requests
