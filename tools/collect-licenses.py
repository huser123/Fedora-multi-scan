"""Copy installed dependency license files into the portable distribution."""
import ast
import importlib.metadata
import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

target = Path(sys.argv[1])
for name in ("PySide6-Essentials", "shiboken6", "Pillow", "img2pdf", "pikepdf", "pypdf", "lxml", "packaging"):
    distribution = importlib.metadata.distribution(name)
    folder = target / name
    folder.mkdir(exist_ok=True)
    (folder / "METADATA.txt").write_text(distribution.read_text("METADATA") or "")
    for relative in distribution.files or []:
        parts = str(relative).lower()
        if any(term in parts for term in ("license", "copying", "copyright", "notice")):
            original = Path(distribution.locate_file(relative))
            if original.is_file():
                destination = folder / str(relative).replace("..", "_")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
if python_license.is_file():
    shutil.copy2(python_license, target / "PYTHON-LICENSE.txt")

# A PyInstaller által a Fedora rendszerből átvett megosztott könyvtárak.
toc = Path("build/pyinstaller/hpscan/COLLECT-00.toc")
if toc.exists() and shutil.which("rpm"):
    entries = ast.literal_eval(toc.read_text())[0]
    sources = sorted({source for _, source, kind in entries
                      if kind in ("BINARY", "EXTENSION") and source.startswith(("/usr/", "/lib"))})
    query = subprocess.run(["rpm", "-qf", "--qf", "%{NAME}\n", *sources], text=True, capture_output=True)
    packages = sorted({line for line in query.stdout.splitlines() if line and " " not in line})
    for package in packages:
        listing = subprocess.run(["rpm", "-ql", package], text=True, capture_output=True, check=True)
        for line in listing.stdout.splitlines():
            original = Path(line)
            if line.startswith("/usr/share/licenses/") and original.is_file():
                destination = target / "fedora" / original.relative_to("/usr/share/licenses")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
    (target / "FEDORA-RUNTIME-PACKAGES.json").write_text(json.dumps(packages, indent=2))
