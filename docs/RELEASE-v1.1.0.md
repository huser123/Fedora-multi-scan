Fedora Multi Scan 1.1.0 adds an English interface next to the Hungarian one.

- English is now the default. Choose **Magyar** in the **Language** box at the
  top right of the settings screen to switch to Hungarian; the choice is
  remembered. `--lang en` / `--lang hu` selects the language for one run.
- The letter keys **C** (Continue), **N** (New group) and **F** (Finish) work
  alongside **T**, **U** and **V** in both languages.
- The default output folder is `Scans` (Hungarian: `Scannelés`) inside the
  desktop's Documents folder.

This release includes the 1.0.1 fix for full-page 600 dpi colour scanning on
the HP LaserJet MFP M130nw; see the README for the `airscan.conf` entry it needs.

Download `FedoraMultiScan-1.1.0-x86_64.AppImage`, make it executable, and run it.
If FUSE is unavailable, use `APPIMAGE_EXTRACT_AND_RUN=1` or the portable tar.gz.
`SHA256SUMS` contains checksums for both packages. `HASZNALAT.md` is the Hungarian
user guide.

The language switch is covered by automated GUI tests. The packaged build and
the full GUI flow have not been re-tested on the physical scanner.
