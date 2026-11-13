# Third-party components

The application source is MIT licensed. Bundled libraries and artwork retain
their own licenses. The portable build includes license files in `licenses/`.

| Component | License / source |
| --- | --- |
| CPython | [PSF license](https://docs.python.org/3/license.html) |
| PySide6 Essentials, Shiboken and Qt | [Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html), LGPLv3/GPLv3 and component-specific licenses |
| Pillow | [MIT-CMU](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| img2pdf | [LGPLv3](https://gitlab.mister-muffin.de/josch/img2pdf) |
| pikepdf | [MPL 2.0](https://github.com/pikepdf/pikepdf) |
| pypdf | [BSD 3-Clause](https://github.com/py-pdf/pypdf) |
| lxml | [BSD and bundled dependencies](https://lxml.de/FAQ.html#what-is-the-license) |
| packaging | [Apache 2.0 / BSD](https://github.com/pypa/packaging) |
| Scanner launcher icon | Unmodified [KDE Breeze `devices/64/scanner.svg`](https://invent.kde.org/frameworks/breeze-icons/-/blob/master/icons/devices/64/scanner.svg), LGPLv3 or later; see `packaging/BREEZE-LICENSE.txt`. |
| AppImage runtime | [AppImage type2-runtime](https://github.com/AppImage/type2-runtime), MIT and bundled component licenses |
| PyInstaller bootloader | [GPL with distribution exception](https://pyinstaller.org/en/stable/license.html) |

The Qt shared libraries remain separate in the portable tar archive and can
be replaced with compatible builds. An AppImage can be extracted with
`--appimage-extract` for the same purpose. No changes were made to the
third-party source code. The original packages and build versions are
listed in the distribution's `BUILD-DEPENDENCIES.txt`.

SANE, sane-airscan and HPLIP are system dependencies, not bundled here.
No proprietary HP plug-in is redistributed by this project.
