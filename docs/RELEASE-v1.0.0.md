Fedora Multi Scan groups manually scanned pages into separate PDFs and matching
numbered JPG/PNG images. The interface is Hungarian.

Download `FedoraMultiScan-1.0.0-x86_64.AppImage`, make it executable, and run it.
If FUSE is unavailable, use `APPIMAGE_EXTRACT_AND_RUN=1` or the portable tar.gz.
`SHA256SUMS` contains checksums for both packages. `HASZNALAT.md` is the Hungarian
user guide.

The application bundles Python, Qt and its image/PDF libraries. The target
machine needs SANE/HP drivers:

```bash
sudo dnf install sane-backends sane-airscan hplip hplip-libs
```

Try `--demo` without a scanner. Every scan requires T, Space or the Continue
button. New group and name confirmation never start scanning.

Verified on Fedora 44 x86_64, including SANE's software test backend. Portable
output tests and headless GUI startup also run in a Fedora 45 container.
Testing on the physical HP M130nw and a Fedora 45 desktop is still pending.

See the repository README for screenshots, controls and output layouts.
