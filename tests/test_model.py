import json
from dataclasses import replace

import pytest
from PIL import Image
from pypdf import PdfReader

from hpscan.model import Session, Settings, auto_prefix, validate_prefix


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "source.png"
    with Image.new("RGB", (150, 210), "white") as image:
        image.save(path)
    return path


@pytest.fixture
def settings(tmp_path):
    return Settings(output=str(tmp_path / "out"), demo=True, dpi=150)


@pytest.mark.parametrize("index,expected", [(0, "aa"), (1, "ab"), (25, "az"), (26, "ba"), (675, "zz"), (676, "aaa"), (677, "aab")])
def test_prefix_sequence(index, expected):
    assert auto_prefix(index) == expected


@pytest.mark.parametrize("name", ["", "../Pisti", "a/b", "a\\b", ".rejtett", "images", "CON", "a:b", "a\n", "x" * 101])
def test_invalid_names(name):
    # A beviteli mező végén a whitespace levágása szándékos.
    if name == "a\n":
        name = "a\nb"
    with pytest.raises(ValueError):
        validate_prefix(name)


def test_hungarian_name():
    assert validate_prefix("  Ágnes dolgozata  ") == "Ágnes dolgozata"


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("fmt", ["jpg", "png"])
def test_five_page_units(settings, source, grouped, fmt):
    session = Session(replace(settings, group_folders=grouped, image_format=fmt, pages_per_unit=5))
    try:
        for _ in range(11):
            if session.needs_unit:
                session.start_unit()
            session.add_page(source)
        session.finish()
        assert [len(u["pages"]) for u in session.data["units"]] == [5, 5, 1]
        for prefix, pages in (("aa", 5), ("ab", 5), ("ac", 1)):
            folder = session.root / prefix if grouped else session.root
            images = folder if grouped else session.root / "images"
            assert len(PdfReader(folder / f"{prefix}.pdf").pages) == pages
            for number in range(1, pages + 1):
                with Image.open(images / f"{prefix}_{number:03d}.{fmt}") as image:
                    assert image.size == (150, 210)
            assert not (images / f"{prefix}_{pages+1:03d}.{fmt}").exists()
    finally:
        session.release()


def test_custom_names_manual_units(settings, source):
    session = Session(replace(settings, automatic=False, group_folders=True))
    try:
        session.start_unit("Pistike")
        session.add_page(source)
        session.add_page(source)
        session.start_unit("Petike")
        session.add_page(source)
        assert (session.root / "Pistike/Pistike.pdf").is_file()
        assert (session.root / "Petike/Petike_001.jpg").is_file()
        with pytest.raises(ValueError, match="already taken"):
            session.start_unit("pistike")
        assert session.current["prefix"] == "Petike"
        session.finish()
    finally:
        session.release()


def test_landscape_dpi_and_pdf_size(settings, source):
    session = Session(replace(settings, landscape=True, dpi=600, image_format="png"))
    try:
        session.start_unit()
        path = session.add_page(source)
        with Image.open(path) as image:
            assert image.size == (210, 150)
            assert image.info["dpi"][0] == pytest.approx(600, abs=0.02)
        page = PdfReader(session.pdf_path(session.current)).pages[0]
        assert float(page.mediabox.width) == pytest.approx(210 / 600 * 72, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(150 / 600 * 72, abs=0.01)
    finally:
        session.release()


def test_existing_files_are_never_overwritten(settings, source):
    root = __import__("pathlib").Path(settings.output)
    root.mkdir()
    (root / "AA.PDF").write_bytes(b"keep")
    (root / "images").mkdir()
    (root / "images/ab_001.png").write_bytes(b"keep2")
    session = Session(settings)
    try:
        assert session.start_unit() == "ac"
        session.add_page(source)
        assert (root / "AA.PDF").read_bytes() == b"keep"
        assert (root / "images/ab_001.png").read_bytes() == b"keep2"
    finally:
        session.release()


def test_session_lock(settings):
    session = Session(settings)
    try:
        with pytest.raises(ValueError, match="another window"):
            Session(settings)
    finally:
        session.release()
    other = Session(settings)
    other.release()


def test_recover_and_continue(settings, source):
    session = Session(settings)
    session.start_unit()
    session.add_page(source)
    path = session.path
    session.release()
    assert Session.unfinished(settings.output) == [path]
    session = Session(settings, path)
    try:
        session.recover()
        session.add_page(source)
        assert len(PdfReader(session.pdf_path(session.current)).pages) == 2
        session.finish()
        assert Session.unfinished(settings.output) == []
    finally:
        session.release()


def test_pdf_failure_preserves_image_and_recovers(settings, source, monkeypatch):
    import hpscan.model as model
    session = Session(settings)
    try:
        session.start_unit()
        original = model.img2pdf.convert
        def fail(*args, **kwargs):
            raise OSError("disk error")
        monkeypatch.setattr(model.img2pdf, "convert", fail)
        with pytest.raises(OSError):
            session.add_page(source)
        assert session.image_path(session.current, 1).is_file()
        assert session.current["pdf_pages"] == 0
        monkeypatch.setattr(model.img2pdf, "convert", original)
        session.recover()
        assert len(PdfReader(session.pdf_path(session.current)).pages) == 1
        session.add_page(source)
        assert len(PdfReader(session.pdf_path(session.current)).pages) == 2
    finally:
        session.release()


@pytest.mark.parametrize("after_pdf", [False, True])
def test_crash_between_file_and_journal(settings, source, after_pdf):
    session = Session(settings)
    session.start_unit()
    if after_pdf:
        session.add_page(source)
        session.current["pdf_pages"] = 0
        session.save()
    else:
        # A kép már megvan, a napló még 0 oldalt mutat.
        source.replace(session.image_path(session.current, 1))
    path = session.path
    session.release()
    session = Session(settings, path)
    try:
        session.recover()
        assert session.total == 1
        assert session.current["pdf_pages"] == 1
        assert len(PdfReader(session.pdf_path(session.current)).pages) == 1
    finally:
        session.release()


def test_image_collision_is_not_overwritten(settings, source):
    session = Session(settings)
    try:
        session.start_unit()
        session.add_page(source)
        target = session.image_path(session.current, 2)
        target.write_bytes(b"foreign file")
        with pytest.raises(Exception):
            session.add_page(source)
        assert target.read_bytes() == b"foreign file"
    finally:
        session.release()


def test_failed_pdf_append_keeps_previous_pdf(settings, source, monkeypatch):
    import hpscan.model as model
    session = Session(settings)
    try:
        session.start_unit()
        session.add_page(source)
        target = session.pdf_path(session.current)
        original_pdf = target.read_bytes()
        original_converter = model.img2pdf.convert
        def fail(*args, **kwargs):
            kwargs["outputstream"].write(b"incomplete PDF")
            raise OSError("disk full")
        monkeypatch.setattr(model.img2pdf, "convert", fail)
        with pytest.raises(OSError):
            session.add_page(source)
        assert target.read_bytes() == original_pdf
        assert session.total == 2
        assert session.current["pdf_pages"] == 1
        monkeypatch.setattr(model.img2pdf, "convert", original_converter)
        session.recover()
        assert len(PdfReader(target).pages) == 2
    finally:
        session.release()


def test_empty_pending_unit_reserves_prefix_across_sessions(settings, source):
    old = Session(settings)
    old.start_unit()
    old_path = old.path
    old.release()
    newer = Session(settings)
    try:
        assert newer.start_unit() == "ab"
        newer.add_page(source)
        newer.finish()
    finally:
        newer.release()
    resumed = Session(settings, old_path)
    try:
        resumed.recover()
        assert resumed.total == 0
        assert resumed.current["prefix"] == "aa"
        resumed.add_page(source)
        assert resumed.total == 1
        assert (resumed.root / "aa.pdf").is_file()
        assert (resumed.root / "ab.pdf").is_file()
    finally:
        resumed.release()


def test_custom_empty_prefix_reservation(settings):
    custom = replace(settings, automatic=False)
    old = Session(custom)
    old.start_unit("Pistike")
    old.release()
    newer = Session(custom)
    try:
        with pytest.raises(ValueError, match="already taken"):
            newer.start_unit("pistike")
        newer.start_unit("Petike")
    finally:
        newer.release()


def test_no_hardlink_filesystem_fallback(settings, source, monkeypatch):
    import errno
    import hpscan.model as model
    def unsupported(*args, **kwargs):
        raise OSError(errno.EOPNOTSUPP, "hardlinks unsupported")
    monkeypatch.setattr(model.os, "link", unsupported)
    session = Session(settings)
    try:
        session.start_unit()
        session.add_page(source)
        assert session.total == 1
        assert len(PdfReader(session.pdf_path(session.current)).pages) == 1
        assert session.image_path(session.current, 1).is_file()
    finally:
        session.release()


def test_no_hardlink_fallback_still_preserves_existing_file(tmp_path, monkeypatch):
    import errno
    import hpscan.model as model
    path = tmp_path / "existing.txt"
    path.write_bytes(b"keep")
    def unsupported(*args, **kwargs):
        raise OSError(errno.EPERM, "no hardlinks")
    monkeypatch.setattr(model.os, "link", unsupported)
    with pytest.raises(FileExistsError):
        model.atomic_write(path, lambda f: f.write(b"replacement"), replace=False)
    assert path.read_bytes() == b"keep"
