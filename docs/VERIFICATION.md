# Verification record

Environment: Fedora 44 KDE, x86_64, Python 3.14.10. The physical HP LaserJet
Pro MFP M130nw was unavailable during the 1.0.0 development; the real-device
results are listed separately below.

## Real device (after 1.0.0)

HP LaserJet MFP M130nw, firmware dated 2020-10-23, Fedora 45, sane-airscan
0.99.38, scanner configured by name in `/etc/sane.d/airscan.conf`.

- Through `scanimage`/sane-airscan (JPEG): A4 colour at 75 dpi works. A4 colour
  at 600 dpi fails with `sane_read: Device busy`; the device reports the job as
  `Aborted` / `JobCanceledAtDevice` after about 39 seconds.
- Straight eSCL requests with the same region: JPEG colour 300 dpi (15 s),
  JPEG grey 600 dpi (26 s) and JPEG colour 600 dpi half page (36 s) work;
  JPEG colour 600 dpi full page is aborted by the device; PDF colour 600 dpi
  full page works (51 s, 4960 × 7016 pixels). A 74-second job (grey 1200 dpi
  strip) also completes, so this is not a time limit.
- Through the app's direct eSCL path (`hpscan/escl.py`): A4 colour 600 dpi over
  the network, 4960 × 7016 pixels in 51 s; A4 grey 300 dpi over USB (ipp-usb),
  2480 × 3508 pixels.

Not yet checked on the device: the full GUI flow, landscape rotation, cancel
during a real scan, and the packaged AppImage with this change.

## Automated checks

`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`: **51 passed**.
The GUI suite has also run under Xvfb. Tests cover:

- Prefix transitions `aa`, `az`, `ba`, `zz`, `aaa`; Unicode custom names and
  rejection of unsafe path characters.
- Eleven pages split into groups of 5/5/1, for both image formats and both
  directory layouts; resulting PDF page counts and numbered image files.
- Manual student groups, case-insensitive name collisions and session locking.
- Landscape pixels, 600 dpi metadata and physical PDF page size.
- A full A4 simulated capture at 600 dpi: 4961 × 7016 pixels.
- Resume, a crash between image and journal writes, a crash between PDF and
  journal writes, initial PDF failure, and a failed PDF append preserving the
  previous complete PDF.
- Scanner subprocess errors, cancellation, and restoration of the system
  library search path when launching `scanimage` from a frozen program.
- Integration with the SANE **software test backend**, including option
  discovery and actual PNM data from `scanimage`. This is not a hardware test.
- Keyboard T/Space, U, V/Esc; actual modal name entry, initial field focus,
  Enter accepting a name without scanning, and Esc dismissing only the dialog.
- Automatic custom-name boundaries waiting for a second explicit scan action.
- Session preparation, new group preparation and recovery producing no scans.
- Pending empty-group name reservations across separate sessions, including
  custom names with case-insensitive matching.
- Missing hardlink support using the Linux `renameat2(RENAME_NOREPLACE)`
  fallback, including preservation of an existing destination file.
- Invalid folder input, cancellation and offline device errors leaving the
  application ready to retry.

## Recorded UI interactions

| Control | Observed result |
| --- | --- |
| Demo checkbox | Enables/disables scanner controls |
| Device search | Test discovery populates the selector; empty/error text exists |
| Editable device field | Manual SANE identifier is retained |
| Device options | Test response populates source and color modes |
| Paper size | Presets update dimensions; Custom enables both dimensions |
| Dimensions | Custom values are used in the session |
| Orientation | Landscape output has width greater than height |
| Resolution | Selected value appears in the session and output metadata |
| JPG/PNG | Selected format changes both filename preview and saved files |
| Folder picker | Selection updates the output field; invalid empty field rejected |
| Automatic/custom names | Correct prefix workflow; real modal accepts Enter |
| Fixed group size | Checkbox enables count; boundary starts a new numbered group |
| Group folders | Filename preview and actual paths change together |
| Prepare session | Creates a group and waits, with zero scanned pages |
| Continue / T / Space | Exactly one page is added per action |
| New group / U | Prepares the next group, adds no pages |
| Finish / V / Esc | Saves the finished journal and returns to preparation |
| Name dialog Esc | Cancels the dialog, preserves the current session |
| Cancel scan | Stops the worker; page count remains unchanged |
| Group list | Selecting a saved group loads its latest image preview |
| Open output folder | Sends the selected output URL to the desktop opener |
| Window resizing | Workspace checked at 740 × 580 and 1120 × 820 |

File chooser and desktop opener are tested with intercepted return values/URLs;
they do not launch the host file manager during the test run. Device search and
option GUI responses use test doubles. The scanner integration test separately
uses the real `scanimage` command and SANE test backend.

Screenshots in `docs/screenshots/` are captured from the running application
with actual simulated images, including a five-page group followed by two
pages in the next group at 600 dpi. Reproduce with
`QT_QPA_PLATFORM=offscreen .venv/bin/python tools/capture-screenshots.py`.

## Portable build checks

- AppImage and portable tar.gz built successfully with PyInstaller 6.22.3 and
  checksum-verified official appimagetool 1.9.1.
- AppImage extracted-run smoke test: three images, `aa.pdf` with two pages,
  `ab.pdf` with one page; PDF page counts read back by the frozen program.
- Extracted tar archive ran the same smoke test from a different directory.
- The AppImage GUI started under Xvfb, remained running until the test timeout,
  and produced no Python/Qt startup errors.
- `sha256sum -c SHA256SUMS` passed for both packages.
- Python compilation, shell syntax and desktop-file validation passed.
- The AppImage output smoke test also passed in the official Fedora 45
  x86_64 container. The Qt GUI started with the offscreen platform and stayed
  running until the startup-test timeout. This does not test a desktop session,
  Wayland interaction or a real scanner. The package uses the host fontconfig
  library to match Fedora's own font configuration format.

## UI delivery gate

- **PASS, hard gate:** functioning controls and empty/loading/error states
  covered above. Native keyboard controls, visible focus, no fictional product
  claims or user records. Desktop-only scope; no mobile website is shipped.
- **PASS, purpose:** the layout follows setup, preview, document groups and the
  three requested actions. One green accent identifies the scan action.
  Standard scanner launcher artwork is unmodified KDE Breeze artwork with
  attribution; no custom logo or decorative asset was invented.
- **PASS, liveliness:** `DESIGN.md` records ENERGY 1 / RHYTHM 1 / MOTION 1.
  Document prefixes/page counts anchor the workspace; the page preview is the
  focal content and the next scan is the primary action.
- **PASS, craftsmanship:** controls exercised as recorded above, real files and
  PDF page counts checked, window sizes captured, source and packaged app run.
  Contrast calculations: main text 12.96:1, secondary text 6.34:1, primary
  button text 8.37:1, disabled primary button text 5.37:1, disabled secondary
  button text 4.65:1. Visible input boundaries use `#758078` against white.

## Remaining checks

- The full GUI flow and the packaged AppImage with the real M130nw.
- Device-specific mode/source names, available resolutions and full-page crop.
- Real flatbed placement and 90° landscape rotation with printed text.
- Fedora 45 on the user's actual desktop and scanner connection.
- Physical unplug/replug and driver/HP plug-in installation on the target.
- Actual exFAT/FAT storage; the no-hardlink fallback was exercised using fault
  injection on a Linux filesystem, not a mounted exFAT volume.

Use a disposable document before production scanning. The application contains
no OCR, automatic page feeder control or text-orientation detection.

## Independent pre-release review

A separate review agent inspected storage/recovery, naming, explicit-scan GUI
paths, scanner cancellation and the release workflow before publication.
It found two issues:

1. An empty pending group could have its prefix reused by a different session,
   allowing recovery to adopt the second session's page. Fixed by reserving
   prefixes across all unfinished session journals, including empty groups.
2. Saving a new image required hardlink support. Fixed with an atomic Linux
   `renameat2(RENAME_NOREPLACE)` fallback when hardlinks are unavailable.

Both fixes have dedicated regression tests and were independently reproduced
and checked by the reviewer. Its complete test run also passed **51 tests**;
it reported no remaining publication blockers. Hardware and actual exFAT
testing remain outside that result.
