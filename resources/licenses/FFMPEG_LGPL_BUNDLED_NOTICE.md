# Bundled FFmpeg (LGPL) — packager notice

Frozen DICOM Viewer V3 builds may ship a static **FFmpeg 7.1.5** CLI built from the official source release:

- **Tarball:** https://ffmpeg.org/releases/ffmpeg-7.1.5.tar.xz
- **SHA-256:** `de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f`

**Configure line** (same as `scripts/build_lgpl_ffmpeg.py`):

```text
./configure --disable-gpl --disable-nonfree --disable-autodetect --disable-ffplay --disable-ffprobe --disable-doc --disable-debug
```

The **GNU LGPL** license text for this executable is **`COPYING.LGPLv2.1`** (and **`COPYING.LGPLv3`** only when the built binary’s `ffmpeg -version` configuration includes `--enable-version3`). Those files are taken from the verified tarball at build time, staged under `build/ffmpeg-lgpl/`, and bundled next to `ffmpeg` / `ffmpeg.exe` under `ffmpeg/` in PyInstaller output when the LGPL build step has been run.

For the rolling third-party attribution table and Python dependency licenses, regenerate and bundle **`THIRD_PARTY_LICENSES.md`** at release time (`python scripts/generate_third_party_licenses.py --release`). That file is generated and gitignored; do not commit it to this repository.

**Unfrozen development** may still use the **GPL** FFmpeg binary from the pinned `imageio-ffmpeg` wheel; frozen `dist/` trees must not contain `imageio_ffmpeg/binaries/ffmpeg*`.
