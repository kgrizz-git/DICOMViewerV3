# FFmpeg (`imageio-ffmpeg`) GPL Binary Replacement Plan

**Status:** Ready for implementation (review blockers incorporated 2026-10-17)
**Priority:** P0 — commercial-release Tier 0 blocker
**TO_DO ref:** Release / Product — [Commercial Release Readiness](../../COMMERCIAL_RELEASE_READINESS.md) item #2 ("Replace `imageio-ffmpeg` — bundled FFmpeg 7.1 binary is a GPL build"); [License & library compliance](LICENSE_AND_COMPLIANCE_PLAN.md) §0b
**Last updated:** 2026-10-17
**Owner:** product/release

This plan is an engineering recommendation, not a legal opinion. Counsel still reviews the final notice text and source offer before a paid release.

---

## 1. Background & Verified Finding

`requirements.txt` pins `imageio==2.38.0` and `imageio-ffmpeg==0.6.0` for cine video export (**File → Export Cine As…**).

The `imageio-ffmpeg` Python wrapper metadata (`.dist-info/METADATA`) declares **BSD-2-Clause**, so `scripts/check_dependency_licenses.py` does not see the native binary. Direct inspection of the vendored FFmpeg 7.1 binary inside the `imageio-ffmpeg==0.6.0` wheel on **2026-10-17** confirmed a **GPLv3-applicable build**. On macOS arm64 the binary is `imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1`, and `ffmpeg -version` reports:

```text
configuration: --prefix=/Volumes/tempdisk/sw ... --enable-gpl --enable-libx264 --enable-libx265 ... --enable-libvidstab ... --enable-postproc ...
```

That configuration line does **not** include `--enable-version3`. `--enable-gpl` plus GPL libraries (`libx264`, `libx265`, `postproc`, `libvidstab`) is enough: the binary is GPL, not LGPL. Distributing it inside a proprietary PyInstaller artifact is a Tier 0 blocker ([`COMMERCIAL_RELEASE_READINESS.md`](../../COMMERCIAL_RELEASE_READINESS.md) item #2, [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md) §0b, [`BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](../../info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md)).

DICOM Viewer V3 does not use those GPL encoders:

- **GIF** uses Pillow through `imageio` and does not start FFmpeg.
- **AVI and MP4** use the built-in `mpeg4` encoder (MPEG-4 Part 2).
- **MPG** uses the built-in `mpeg2video` encoder and the `mpeg` muxer (`-f mpeg`).

Those encoders and that muxer are available in an LGPL FFmpeg build. The export containers and the Windows 11 Media Player `.mp4` path can stay.

**What must be replaced:** the GPL executable that the wheel and the PyInstaller hook would ship. **What stays:** the `imageio` / `imageio-ffmpeg` Python wrapper, the existing codec flags, and GIF-via-Pillow.

---

## 2. Current Usage Inventory

### 2.1 Code & Call Graph

| Location | Symbols / Role | FFmpeg / Codec Details |
|----------|----------------|------------------------|
| [`src/gui/cine_video_export.py`](../../../src/gui/cine_video_export.py) | `ffmpeg_codec_and_params_for_cine_container(video_format)`<br>`encode_cine_video_from_png_paths(...)` | - **GIF:** `imageio.get_writer(..., format="GIF")` — Pillow; no FFmpeg.<br>- **AVI:** `codec="mpeg4"`, `ffmpeg_params=["-pix_fmt", "yuv420p"]`<br>- **MP4:** `codec="mpeg4"`, `ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]`<br>- **MPG:** `codec="mpeg2video"`, `ffmpeg_params=["-f", "mpeg", "-pix_fmt", "yuv420p"]`<br>- Writer: `imageio.get_writer(..., format="FFMPEG", mode="I", fps=..., codec=..., ffmpeg_params=..., ffmpeg_log_level="error")` |
| [`src/gui/dialogs/cine_export_encode_thread.py`](../../../src/gui/dialogs/cine_export_encode_thread.py) | `CineVideoEncodeThread` | Runs encode on a `QThread`. No `shell=True`. |
| [`src/gui/dialogs/cine_export_dialog.py`](../../../src/gui/dialogs/cine_export_dialog.py) | `CineExportDialog` | Formats `GIF`, `AVI`, `MP4`, `MPG` (default MP4). Help text says `"Video encoding uses FFmpeg via the imageio-ffmpeg package (LGPL/GPL components)."` |
| [`src/gui/actions/dialog_actions.py`](../../../src/gui/actions/dialog_actions.py) | `open_export_cine_video(app)` | Renders frames to `tempfile.mkdtemp(prefix="dv3_cine_")`, then encodes. |
| [`tests/gui/test_cine_video_export.py`](../../../tests/gui/test_cine_video_export.py) | Unit tests | Mocks `imageio.get_writer`. Does not run a real FFmpeg binary. |

`imageio_ffmpeg.write_frames` invokes FFmpeg as a separate process. The input side is stdin raw video, not a PNG demux:

```text
ffmpeg -y -f rawvideo -vcodec rawvideo -s WxH -pix_fmt rgb24 -r FPS -i - -an -vcodec mpeg4 -pix_fmt yuv420p ...
```

Odd frame sizes can add `-vf scale=...` (default macro-block size 16). A replacement build must keep the `rawvideo` demuxer/decoder, the `scale` filter, the `pipe` protocol, encoders `mpeg4` and `mpeg2video`, and muxers `avi`, `mp4`, and `mpeg`.

### 2.2 How `imageio-ffmpeg` 0.6.0 finds the binary

`get_ffmpeg_exe()` in `imageio_ffmpeg._utils` (verified in the project venv):

1. `os.getenv("IMAGEIO_FFMPEG_EXE")` — returned immediately when non-empty. **Not cached. Not checked for existence.**
2. `_get_ffmpeg_exe()` — `@lru_cache`. Wheel file under `imageio_ffmpeg/binaries/` (`ffmpeg-<platform>-v7.1*`). This is the GPL binary.
3. `sys.prefix/bin/ffmpeg`, or on Windows `sys.prefix/Library/bin/ffmpeg.exe`. This is the interpreter prefix, not `$CONDA_PREFIX`.
4. The command name `ffmpeg` on `PATH` (the string `"ffmpeg"`, after a `-version` probe). Not `shutil.which`.

Application code does not set `IMAGEIO_FFMPEG_EXE` today. On Windows, `imageio_ffmpeg` hides the console with `STARTF_USESHOWWINDOW`, not `CREATE_NO_WINDOW`.

### 2.3 Freeze behavior

[`DICOMViewerV3.spec`](../../../DICOMViewerV3.spec) does not name `imageio_ffmpeg`. `_pyinstaller_hooks_contrib`'s `hook-imageio_ffmpeg.py` does:

```python
datas = collect_data_files('imageio_ffmpeg', subdir="binaries")
hiddenimports = ['imageio_ffmpeg.binaries']  # imageio-ffmpeg >= 0.5
```

Those files land in `a.datas`. A freeze from a venv that has the wheel installed copies the GPL executable into `dist/` unless the spec removes those entries before `COLLECT`.

`pip install --no-binary imageio-ffmpeg` is **not** a compliance fix. The sdist downloads the same GPL binary at install time. Keep the wrapper pin. Strip the binary at freeze time.

---

## 3. Options Assessment

| Option | License of what we ship | Effort | Fit |
|--------|-------------------------|--------|-----|
| **A. Bundle our own static LGPL `ffmpeg` CLI** and strip the wheel binary | LGPL for that executable (2.1 or 3, matching the build) + BSD-2-Clause wrapper | Medium | **Chosen for release builds.** Same containers and flags. Separate process, not linked into the app. |
| **B. No bundled FFmpeg; user supplies `PATH` or `IMAGEIO_FFMPEG_EXE`** | No FFmpeg code in the installer | Low | **Required fallback** for dev machines and for a release cut whose LGPL build or notarization is blocked. GIF still works. |
| **C. Drop AVI/MP4/MPG; GIF + multi-frame Secondary Capture DICOM only** | Permissive (`Pillow`, `pydicom`) | Medium | Out of scope. Does not preserve Windows Media Player export. SC DICOM can be a later feature. |
| **D. PyAV (`av`)** | PyPI wheels often bundle GPL `libx264` / `libx265` and link them in-process | Hard | Rejected. |
| **E. OpenCV `VideoWriter`** | PyPI wheels bundle GPLv3 FFmpeg linked in-process | Hard | Rejected. Not a dependency. |

BtbN GitHub builds are not the supply chain. The rolling `latest` tag is rewritten, so a SHA-256 of that URL does not stay valid. The non-`shared` archives are one static executable; `*-lgpl-shared-*` is the DLL/.so set. BtbN also does not publish macOS binaries. One pinned official source tarball and one configure line for every OS avoids that split.

---

## 4. Decisions

1. **Replace the bundled binary. Keep the wrapper.** Frozen builds must not contain `imageio_ffmpeg/binaries/ffmpeg*`. `imageio` and `imageio-ffmpeg` stay pinned. Codec flags stay `mpeg4` / `mpeg2video` / `-f mpeg`.
2. **Ship a static LGPL CLI, built from a pinned official FFmpeg 7.1.x source tarball**, the same configure line on Windows, macOS, and Linux. "Static" means libavcodec/libavformat/libavutil/libswscale are linked into the `ffmpeg` executable. The executable may still depend on system libc (and on macOS, libSystem). Do not ship `lgpl-shared` DLLs or `.so` files. The app does not link those libraries; it only spawns the CLI. Users replace the whole executable.
3. **Configure line (do not component-whitelist):**

   ```text
   ./configure --disable-gpl --disable-nonfree --disable-ffplay --disable-ffprobe --disable-doc --disable-debug
   ```

   A whitelist such as `--enable-encoder=mpeg4,mpeg2video --enable-muxer=avi,mp4,mov,mpeg2video,mpeg1system` is wrong for this app. `mpeg1system` is not an FFmpeg 7.1 muxer name. The MPG path needs the muxer named `mpeg`. The writer also needs `rawvideo` and `scale`. Default LGPL configure already includes those. Record the exact tarball version, SHA-256, and configure line in the manifest at implementation time. Do not invent the digest in this plan.
4. **GPL checks run when we build or fetch our binary, and again on `dist/`.** They do **not** run against a user-supplied `ffmpeg`. Homebrew and apt builds are typically GPL. The user is not asking us to distribute those binaries. Refusing them disables the fallback on the machines that need it.
5. **Resolver order.** `resolve_ffmpeg_exe()` is pure: it does not write `os.environ`. It returns a small frozen result, not a bare `Path`, so the caller can tell a user override from a discovered binary:

   ```text
   FfmpegResolution(path: Path | None, source: "user_env" | "bundled" | "path" | "dev_wheel" | "missing")
   ```

   1. `source="user_env"` when `IMAGEIO_FFMPEG_EXE` names an existing regular file. Honor it. Never overwrite it.
   2. `source="bundled"` when `sys.frozen` and `Path(sys._MEIPASS) / "ffmpeg" / exe_name` is an existing file. `exe_name` is `ffmpeg.exe` on Windows and `ffmpeg` elsewhere. The staged tree and the spec destination use that same filename under `ffmpeg/`.
   3. `source="path"` from `shutil.which("ffmpeg")` when that path is an existing file.
   4. `source="dev_wheel"` only when **not** frozen. Read the wheel file from `importlib.resources.files("imageio_ffmpeg.binaries")` using the platform filename in `imageio_ffmpeg._definitions.FNAME_PER_PLATFORM`. Do **not** call `imageio_ffmpeg._get_ffmpeg_exe()` or `get_ffmpeg_exe()` for this step. `_get_ffmpeg_exe()` is `@lru_cache` and checks the wheel, then `sys.prefix`, then `PATH`, which would undo the PATH-before-wheel order above.
   5. `source="missing"` and `path=None` otherwise. An empty or non-file `IMAGEIO_FFMPEG_EXE` is not `user_env`; resolution continues.
6. **Encode path.** `encode_cine_video_from_png_paths` calls the resolver before any FFmpeg `get_writer`:
   - GIF does not need a binary.
   - For AVI, MP4, and MPG, `source="missing"` raises `RuntimeError` with text that tells the user to install `ffmpeg` or set `IMAGEIO_FFMPEG_EXE`. `CineVideoEncodeThread.run` already emits `failed` with `str(exc)`; do not add a second error channel.
   - When `source` is not `user_env` and `path` is set, assign `os.environ["IMAGEIO_FFMPEG_EXE"] = str(path)` immediately before `imageio.get_writer(..., format="FFMPEG")`. The env read inside `get_ffmpeg_exe()` is uncached, so this beats the cached wheel lookup.
   - When `source` is `user_env`, leave the environment alone.
7. **UI:** GIF stays available with no FFmpeg. If `source` is `missing`, disable AVI/MP4/MPG and explain `IMAGEIO_FFMPEG_EXE` or a system `ffmpeg`. In a normal dev venv the wheel binary counts as resolved, so those formats stay enabled. Frozen builds never use `dev_wheel`. The dialog check is read-only and must not set `IMAGEIO_FFMPEG_EXE`.
8. **macOS arch:** current [`.github/workflows/build.yml`](../../../.github/workflows/build.yml) builds `macos-latest` only (Apple silicon). Do not block this work on an Intel or universal binary.
9. **Multi-frame Secondary Capture DICOM** is not part of this change.
10. **Size:** a default LGPL static `ffmpeg` is tens of megabytes. This change does not claim a bundle-size reduction. The size win exists only in the zero-binary fallback.

---

## 5. Implementation Steps

### Phase 1 — Resolver and dialog

- [ ] Add `FfmpegResolution` and `resolve_ffmpeg_exe() -> FfmpegResolution` in `src/gui/cine_video_export.py` with the order and wheel lookup in Decision 5. Validate with `Path.is_file()` before use. On Windows, `os.access(..., os.X_OK)` is a weak check; require a regular file. The dev-wheel helper reads package resources directly and does not call `_get_ffmpeg_exe()`.
- [ ] Do not add a runtime function that rejects `--enable-gpl` on the resolved binary.
- [ ] Wire `encode_cine_video_from_png_paths` as in Decision 6: resolve, raise `RuntimeError` for AVI/MP4/MPG when `source` is `missing`, and set `IMAGEIO_FFMPEG_EXE` only when `source` is not `user_env`. Rely on `CineVideoEncodeThread.run`'s existing `failed.emit(str(exc))`.
- [ ] Update the cine dialog help text so it no longer says the app ships LGPL/GPL components together. When `source` is `missing`, keep GIF and disable AVI/MP4/MPG with a short explanation. Do not write the environment from the dialog.

### Phase 2 — Pinned LGPL build

- [ ] Add `scripts/build_lgpl_ffmpeg.py` (or a small script plus a shell/MSYS2 recipe) that:
  - Downloads one official FFmpeg 7.1.x tarball.
  - Verifies the recorded SHA-256 before configure.
  - Configures with Decision 3. No `--enable-gpl`, `--enable-nonfree`, `--enable-libx264`, `--enable-libx265`, or `--enable-postproc`.
  - Stages `ffmpeg` (or `ffmpeg.exe`) plus `COPYING.LGPLv2.1` and a text file with the tarball version, digest, and configure line into gitignored `build/ffmpeg-lgpl/`.
  - Runs `ffmpeg -version` and fails if the configuration line contains any of these whole flags: `--enable-gpl`, `--enable-nonfree`, `--enable-libx264`, `--enable-libx265`, `--enable-postproc`. A bare substring such as `postproc` or `libx264` is the wrong check: it also matches `--disable-postproc` and `--disable-libx264`.
  - Runs `ffmpeg -hide_banner -encoders` and `-muxers` and requires `mpeg4`, `mpeg2video`, and muxer `mpeg`.
- [ ] If the build was configured with `--enable-version3`, ship `COPYING.LGPLv3` and say LGPL-3. If not, say LGPL-2.1-or-later. Do not guess; use the configuration line.
- [ ] Windows: build on `windows-latest` with MSYS2 mingw64 (or an equivalent documented toolchain). Cache by tarball digest plus configure line. If that toolchain blocks a release cut, use the zero-binary fallback in section 7. Do not substitute an unpinned third-party binary.
- [ ] macOS and Linux: build with the runner's clang/gcc. The Linux binary may require the runner's glibc; that matches `ubuntu-latest`.

### Phase 3 — PyInstaller

- [ ] In `DICOMViewerV3.spec`, after `Analysis` and before `COLLECT`, drop every `a.datas` entry collected by `hook-imageio_ffmpeg.py` (`collect_data_files('imageio_ffmpeg', subdir="binaries")` puts the GPL executable in `a.datas`, not `a.binaries`). Also drop any `a.binaries` entry whose path contains `imageio_ffmpeg` and `binaries`, in case a later hook change collects it as a binary.
- [ ] Add the staged executable as a datas entry with destination `ffmpeg/`. The frozen file is `Path(sys._MEIPASS) / "ffmpeg" / "ffmpeg.exe"` on Windows and `Path(sys._MEIPASS) / "ffmpeg" / "ffmpeg"` on macOS and Linux. Use `_MEIPASS`. Do not hard-code `Contents/Resources` or `resources/ffmpeg`. Confirm that relative path once on a real Windows, macOS, and Linux freeze.
- [ ] Keep `ffmpeg` out of UPX (`upx_exclude` if it is collected as a binary). `USE_UPX` is still true on Windows and Linux.
- [ ] In `.github/workflows/build.yml`, run the LGPL build before `pyinstaller`, then after the freeze:
  1. Fail if `dist/` contains `imageio_ffmpeg/binaries/ffmpeg*`.
  2. Run the bundled `ffmpeg -version` and fail on the same whole flags as Phase 2: `--enable-gpl`, `--enable-nonfree`, `--enable-libx264`, `--enable-libx265`, `--enable-postproc`. Do not fail on `--disable-libx264`, `--disable-libx265`, or `--disable-postproc`.
- [ ] Sign the bundled executable with the app: Windows Authenticode when signing is enabled, macOS Developer ID + Hardened Runtime before notarization. `USE_UPX = False` on macOS stays.

### Phase 4 — Notices and docs

- [ ] Ship `COPYING.LGPLv2.1` (and `COPYING.LGPLv3` only if `--enable-version3` is present), the configure line, and a pointer to the corresponding FFmpeg source tarball next to `THIRD_PARTY_LICENSES`.
- [ ] Update the `imageio` / `imageio-ffmpeg` comment in `requirements.txt`, plus `AGENTS.md`, `dev-docs/CONTRIBUTING.md`, `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`, `dev-docs/info/BUILDING_EXECUTABLES.md`, and `CHANGELOG.md`.
- [ ] Mark Commercial Release Readiness item #2 done only after the frozen gate passes on Windows, macOS, and Linux. Update `LICENSE_AND_COMPLIANCE_PLAN.md` §0b in that same change.

### Phase 5 — Tests

- [ ] Unit-test resolver priority with temporary files and `monkeypatch`: user env, bundled path, PATH, then dev wheel, then `missing`. Assert `source` as well as `path`. Mock the package-resource lookup so the test does not depend on `_get_ffmpeg_exe()`'s cached order. Do not require a real encode to decide license compliance.
- [ ] License-string checks belong to `scripts/build_lgpl_ffmpeg.py` and the build workflow, using fixtures or the staged binary. Do not fail `tests/gui/test_cine_video_export.py` because the dev wheel is GPL.
- [ ] Add an optional integration encode of a few synthetic frames to GIF, AVI, MP4, and MPG when `source` is not `missing`. Skip otherwise. Assert container magic bytes, not GPL flags.
- [ ] Manual QA: export with and without overlays, including MONOCHROME1 and MONOCHROME2; play `.mp4` in stock Windows 11 Media Player; confirm Cancel still deletes a partial file.

---

## 6. `IMAGEIO_FFMPEG_EXE` Contract

- `source="user_env"` means the variable already names an existing file. `encode_cine_video_from_png_paths` must not replace that value with the bundled, PATH, or dev-wheel binary.
- An empty value, or a value that is not an existing file, is not `user_env`. Resolution continues at the bundled path.
- Only `encode_cine_video_from_png_paths` may set the variable, and only when `source` is `bundled`, `path`, or `dev_wheel`. The dialog's enablement check is read-only.
- `imageio-ffmpeg` passes the value as `argv[0]` with `shell=False`.

---

## 7. Rollback

If the LGPL build or code signing blocks a release:

- Strip `imageio_ffmpeg/binaries/*` from the spec.
- Do not bundle a replacement binary.
- GIF works. AVI/MP4/MPG work when the user has `ffmpeg` on `PATH` or sets `IMAGEIO_FFMPEG_EXE`.
- The installer contains no GPL FFmpeg.

Developers can keep using the wheel binary in an unfrozen checkout. That binary must never appear under `dist/`.

---

## 8. Files Likely Touched

| File | Change |
|------|--------|
| `src/gui/cine_video_export.py` | `FfmpegResolution` and `resolve_ffmpeg_exe()`; dev-wheel lookup via `importlib.resources`; `encode_cine_video_from_png_paths` sets `IMAGEIO_FFMPEG_EXE` only when `source` is not `user_env`, and raises `RuntimeError` for AVI/MP4/MPG when `source` is `missing`. |
| `src/gui/dialogs/cine_export_encode_thread.py` | No new signal. `run` already emits `failed` with the exception text. |
| `src/gui/dialogs/cine_export_dialog.py` | Help text; disable AVI/MP4/MPG when `source` is `missing`. Do not set the environment. |
| `scripts/build_lgpl_ffmpeg.py` | New. Download, digest-check, configure, and audit the LGPL CLI. |
| `DICOMViewerV3.spec` | Drop wheel binaries from `a.datas` / `a.binaries`; add `ffmpeg/` from `build/ffmpeg-lgpl/`. |
| `.github/workflows/build.yml` | Build LGPL FFmpeg before freeze; fail the job if `dist/` still contains the wheel binary or any `--enable-gpl` / `--enable-nonfree` / `--enable-libx264` / `--enable-libx265` / `--enable-postproc` flag. |
| `requirements.txt` | Comment only. Do not drop the wrapper pins. Do not rely on `--no-binary`. |
| `tests/gui/test_cine_video_export.py` | Resolver tests. Integration encodes skip when no binary resolves. |
| `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` | Replace the GPL-blocker row after the frozen gate passes. |
| `dev-docs/info/BUILDING_EXECUTABLES.md` | Document the staging step, `_MEIPASS/ffmpeg`, and the post-freeze check. |
| `dev-docs/COMMERCIAL_RELEASE_READINESS.md` | Close item #2 only after all three frozen builds pass. |
| `dev-docs/plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md` | Update §0b with this plan. |
| `AGENTS.md`, `CHANGELOG.md` | Cine-export note and `[Unreleased]` entry when the code lands. |

---

## 9. Closed Questions

1. **macOS binary source.** Build macOS from the same official tarball as Windows and Linux. Do not use BtbN.
2. **Static vs shared.** Static CLI. Shared LGPL libraries are for in-process linking, which this app does not do, and they add DLL search hazards.
3. **Secondary Capture DICOM cine.** Not this change.
4. **User-supplied GPL `ffmpeg`.** Allowed at runtime. The `--enable-gpl` assertion applies only to the binary we build and to the frozen `dist/` tree.
