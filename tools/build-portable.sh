#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
PYTHON=${PYTHON:-.venv/bin/python}
VERSION=$("$PYTHON" -c 'from hpscan import __version__; print(__version__)')
ARCH=$(uname -m)
if [[ "$ARCH" != x86_64 ]]; then
  echo 'This build script currently targets Fedora x86_64.' >&2
  exit 1
fi

"$PYTHON" -m PyInstaller --noconfirm --clean --name hpscan \
  --distpath build/frozen --workpath build/pyinstaller \
  --specpath build --collect-submodules pypdf \
  --copy-metadata img2pdf --copy-metadata pikepdf \
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets \
  --exclude-module PySide6.QtPdf --exclude-module tkinter run.py

APPDIR="build/FedoraMultiScan-$VERSION.AppDir"
if [[ -d "$APPDIR" ]]; then
  # Ez kizárólag a build/ alatt előállított alkalmazáskönyvtár.
  rm -rf -- "$APPDIR"
fi
mkdir -p "$APPDIR/usr/bin" "$APPDIR/licenses" dist build/tools
cp -a build/frozen/hpscan/. "$APPDIR/usr/bin/"
# A fontconfig a gazdagép saját konfigurációját olvassa, ezért annak a
# könyvtárát használjuk az újabb Fedora konfigurációformátumával is.
rm -f "$APPDIR/usr/bin/_internal/libfontconfig.so.1"
cp packaging/AppRun "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp packaging/hpscan.desktop "$APPDIR/hpscan.desktop"
cp packaging/scanner.svg "$APPDIR/scanner.svg"
cp LICENSE THIRD_PARTY.md "$APPDIR/licenses/"
cp packaging/BREEZE-LICENSE.txt "$APPDIR/licenses/"
cp README.md LICENSE THIRD_PARTY.md CHANGELOG.md docs/HASZNALAT.md "$APPDIR/"
cp -a docs "$APPDIR/docs"
cp -a packaging/licenses/. "$APPDIR/licenses/"
"$PYTHON" tools/collect-licenses.py "$APPDIR/licenses"
"$PYTHON" -m pip freeze --exclude-editable > "$APPDIR/BUILD-DEPENDENCIES.txt"
cp /etc/os-release "$APPDIR/BUILD-OS.txt"

TOOL=build/tools/appimagetool.AppImage
if [[ ! -f "$TOOL" ]]; then
  curl --fail --location --silent --show-error \
    https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage \
    -o "$TOOL"
fi
echo 'ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0  build/tools/appimagetool.AppImage' | sha256sum -c -
chmod +x "$TOOL"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" "dist/FedoraMultiScan-$VERSION-x86_64.AppImage"
tar -czf "dist/FedoraMultiScan-$VERSION-x86_64.tar.gz" -C build "FedoraMultiScan-$VERSION.AppDir"
cp docs/HASZNALAT.md dist/HASZNALAT.md
(
  cd dist
  sha256sum "FedoraMultiScan-$VERSION-x86_64.AppImage" "FedoraMultiScan-$VERSION-x86_64.tar.gz" > SHA256SUMS
)
echo "Built AppImage and portable tar.gz in dist/"
