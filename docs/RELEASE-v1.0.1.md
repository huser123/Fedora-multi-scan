Fedora Multi Scan 1.0.1 fixes full-page 600 dpi colour scanning on the
HP LaserJet MFP M130nw.

The device aborts such a job after about 40 seconds when asked for JPEG, which
is the only format sane-airscan requests, so 1.0.0 failed with
`sane_read: Device busy`. Scanners listed by name in the `[devices]` section of
`/etc/sane.d/airscan.conf` that offer PDF are now read directly over eSCL as
PDF. Other devices and settings still go through `scanimage`.

```ini
[devices]
"HP LaserJet M130nw (eSCL)" = http://PRINTER-NAME.local/eSCL/, escl
```

Download `FedoraMultiScan-1.0.1-x86_64.AppImage`, make it executable, and run it.
If FUSE is unavailable, use `APPIMAGE_EXTRACT_AND_RUN=1` or the portable tar.gz.
`SHA256SUMS` contains checksums for both packages. `HASZNALAT.md` is the Hungarian
user guide.

Checked on a real M130nw on Fedora 45 from source: A4 colour at 600 dpi over the
network and A4 grey at 300 dpi over USB. The full GUI flow and this packaged
build have not been re-tested on the device.
