# Changelog

## Unreleased

- Fix full-page 600 dpi colour scans on the HP LaserJet MFP M130nw. The device
  aborts such a job after about 40 seconds when asked for JPEG, which is the
  only format sane-airscan requests (`sane_read: Device busy`). Devices listed
  in the `[devices]` section of `airscan.conf` that offer PDF are now scanned
  directly over eSCL as PDF, and the embedded image is saved. Other devices
  and settings still go through `scanimage`.
- Verified on a real M130nw on Fedora 45: A4 colour at 600 dpi over the
  network (51 s) and A4 grey at 300 dpi over USB through ipp-usb.

## 1.0.0

Initial release:

- Hungarian desktop UI for scanning document groups on Fedora x86_64.
- JPG/PNG pages and a separate PDF per group, automatic or custom prefixes.
- Optional fixed page counts and per-group output folders.
- Explicit keyboard-driven scanning with no automatic scan after name entry.
- Session recovery, collision checks and scanner-free simulation.
- AppImage, portable tar archive and GitHub release build workflow.

Real HP M130nw hardware validation and a full Fedora 45 desktop test are
pending. Automated tests and portable smoke tests are documented in
`docs/VERIFICATION.md`.
