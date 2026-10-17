# FFmpeg (`imageio-ffmpeg`) GPL Binary Replacement Plan

**Status:** Draft — ready for implementation  
**Priority:** P0 — commercial-release Tier 0 blocker  
**TO_DO ref:** Release / Product — [Commercial Release Readiness](../../COMMERCIAL_RELEASE_READINESS.md) item #2 ("Replace `imageio-ffmpeg` — bundled FFmpeg 7.1 binary is a GPL build"); [License & library compliance](LICENSE_AND_COMPLIANCE_PLAN.md) §0b  
**Last updated:** 2026-10-17  
**Owner:** product/release

---

## 1. Background & Verified Finding

`requirements.txt` pins `imageio==2.38.0` and `imageio-ffmpeg==0.6.0` to power cine video export (**File → Export Cine As…**).

While the `imageio-ffmpeg` Python wrapper metadata (`.dist-info/METADATA`) declares **BSD-2-Clause** (and therefore passes the stdlib Python metadata gate `scripts/check_dependency_licenses.py`), a direct inspection of the vendored FFmpeg 7.1 binary inside the `imageio-ffmpeg==0.6.0` wheel on **2026-10-17** confirmed that it is compiled as a **GPLv3 build**:

- Running `<imageio_ffmpeg_exe> -version` reports:
  `configuration: --enable-gpl --enable-version3 --enable-libx264 --enable-libx265 --enable-libvidstab ...` (plus `postproc`).
- Distributing a GPLv3 FFmpeg binary inside a proprietary/closed-source PyInstaller release artifact is a **Tier 0 commercial release blocker** ([`COMMERCIAL_RELEASE_READINESS.md`](../../COMMERCIAL_RELEASE_READINESS.md) item #2, [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md) §0b, [`BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](../../info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md) row 1).

 Crucially, **DICOM Viewer V3 does not use any GPL-only encoders (`libx264`, `libx265`, `vidstab`, `postproc`)**:
- `src/gui/cine_video_export.py` explicitly avoids H.264/HEVC and encodes only with FFmpeg's built-in **LGPL-2.1+** encoders: **`mpeg4`** (MPEG-4 Part 2 for `.avi` and `.mp4`) and **`mpeg2video`** (MPEG-2 Program Stream for `.mpg`), while **`.gif`** uses Pillow via `imageio` without invoking FFmpeg at all.

Therefore, we can eliminate the GPL binary from our release artifacts without losing any export container (**GIF**, **AVI**, **MP4**, **MPG**) or regressing **Windows 11 Media Player** in-box `.mp4` playback.

---

## 2. Current Usage Inventory

### 2.1 Code & Call Graph

| Location | Symbols / Role | FFmpeg / Codec Details |
|----------|----------------|------------------------|
| [`src/gui/cine_video_export.py`](../../../src/gui/cine_video_export.py) | `ffmpeg_codec_and_params_for_cine_container(video_format)`<br>`encode_cine_video_from_png_paths(...)`<br>`gif_frame_duration_milliseconds(...)`<br>`effective_fps_for_encoder(...)`<br>`rasterize_cine_export_frame(...)` | - **GIF:** `imageio.get_writer(output_path, format="GIF", mode="I", duration=duration_ms, loop=0)` — routes through Pillow plugin; **does not invoke FFmpeg**.<br>- **AVI:** `codec="mpeg4"`, `ffmpeg_params=["-pix_fmt", "yuv420p"]`<br>- **MP4:** `codec="mpeg4"`, `ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"]` (default in UI; stock Windows 11 Media Player compatible)<br>- **MPG:** `codec="mpeg2video"`, `ffmpeg_params=["-f", "mpeg", "-pix_fmt", "yuv420p"]`<br>- Calls `imageio.get_writer(..., format="FFMPEG", mode="I", fps=eff_fps, codec=vid_codec, ffmpeg_params=vid_extra, ffmpeg_log_level="error")` |
| [`src/gui/dialogs/cine_export_encode_thread.py`](../../../src/gui/dialogs/cine_export_encode_thread.py) | `CineVideoEncodeThread(QThread)` | Runs `encode_cine_video_from_png_paths` in a worker `QThread` over temporary PNGs rendered on the Qt main thread. No `shell=True`. |
| [`src/gui/dialogs/cine_export_dialog.py`](../../../src/gui/dialogs/cine_export_dialog.py) | `CineExportDialog`, `CineExportOptions` | Format combo (`["GIF", "AVI", "MP4", "MPG"]`, default index `2` = `"MP4"`). Line 149 help label mentions: `"Video encoding uses FFmpeg via the imageio-ffmpeg package (LGPL/GPL components)."` |
| [`src/gui/actions/dialog_actions.py`](../../../src/gui/actions/dialog_actions.py) | `open_export_cine_video(app)` | Orchestrates **File → Export Cine As…**: checks `describe_focused_cine_export_blocker(app)`, opens `CineExportDialog`, renders frames to `tempfile.mkdtemp(prefix="dv3_cine_")`, runs `CineVideoEncodeThread`, cleans up partial output on cancel/error. |
| [`tests/gui/test_cine_video_export.py`](../../../tests/gui/test_cine_video_export.py) | Unit tests for `cine_video_export.py` | Mocks `imageio.get_writer` and `imageio.imread` to verify codec/parameter plumbing (`mpeg4`, `mpeg2video`, `-movflags +faststart`, `yuv420p`), cancel handling, and frame index math. |

### 2.2 FFmpeg Binary Resolution (`IMAGEIO_FFMPEG_EXE`)

- Application code under `src/` **does not currently read or set `IMAGEIO_FFMPEG_EXE`**.
- Instead, `imageio`'s `FFMPEG` plugin delegates binary discovery to `imageio_ffmpeg.get_ffmpeg_exe()`, which resolves in exact order:
  1. `os.getenv("IMAGEIO_FFMPEG_EXE")` — if set and non-empty, returned immediately.
  2. Wheel-bundled binary inside `imageio_ffmpeg.binaries` (`ffmpeg-<platform>-v7.1*`) — **this is the GPLv3 binary that must not ship**.
  3. Conda environment binary (`$CONDA_PREFIX/bin/ffmpeg` or `Library/bin/ffmpeg.exe`).
  4. System `ffmpeg` on `PATH` (`shutil.which("ffmpeg")`).

### 2.3 Dependencies & PyInstaller Spec Collection

- [`requirements.txt`](../../../requirements.txt) lines 31–33:
  ```text
  imageio==2.38.0
  imageio-ffmpeg==0.6.0
  ```
- [`requirements-dev.txt`](../../../requirements-dev.txt): includes `-r requirements.txt`; `scripts/check_dependency_licenses.py` inspects Python dist-info metadata (`BSD-2-Clause` for `imageio-ffmpeg`), which is why the native GPL binary inside `imageio_ffmpeg/binaries/` is invisible to metadata-only checks.
- [`DICOMViewerV3.spec`](../../../DICOMViewerV3.spec): does not explicitly list `imageio_ffmpeg` in `binaries`, `datas`, or `hiddenimports` (only `'imageio.tests'` in `excludes`). However, `_pyinstaller_hooks_contrib`'s standard hook **`hook-imageio_ffmpeg.py`** automatically executes:
  ```python
  datas = collect_data_files('imageio_ffmpeg', subdir="binaries")
  hiddenimports = ['imageio_ffmpeg.binaries']
  ```
  Consequently, any PyInstaller build executed in a venv where the binary `imageio-ffmpeg` wheel is installed **silently bundles the ~70–80 MB GPLv3 `ffmpeg` executable** into `dist/` unless explicitly excluded/replaced.

---

## 3. Options Assessment

| Option | Effective License | Platforms | Effort | Regression Risk | Pros | Cons |
|--------|-------------------|-----------|--------|-----------------|------|------|
| **A. Bundle LGPL-only FFmpeg binary** (e.g. BtbN `ffmpeg-n7.1-latest-*-lgpl-7.1` or custom `--disable-gpl` build) via `IMAGEIO_FFMPEG_EXE` + PyInstaller `datas`/`binaries`, and strip `imageio_ffmpeg/binaries/*` | **LGPL-2.1-or-later** (binary) + **BSD-2-Clause** (`imageio` / `imageio-ffmpeg` wrapper) | Windows x64, macOS (arm64/x64), Linux x64 | **Medium** | **Low** — `mpeg4` and `mpeg2video` are native LGPL encoders in FFmpeg 7.1; zero change to containers or CLI flags | - Preserves out-of-the-box **GIF, AVI, MP4, MPG** export with zero user setup.<br>- Preserves stock **Windows 11 Media Player** `.mp4` playback.<br>- Keeps `imageio-ffmpeg`'s battle-tested subprocess management (`no shell=True`). | - Must fetch/verify LGPL FFmpeg binaries per OS in CI/build scripts (especially macOS universal/arm64 where BtbN only publishes Windows/Linux).<br>- Must comply with LGPL-2.1+ attribution, license text, and source/build-script offer in release artifacts.<br>- Must sign the bundled `ffmpeg` binary on Windows (Authenticode) and macOS (codesign + Hardened Runtime / notarization). |
| **B. User-supplied system `ffmpeg` (`PATH` / `IMAGEIO_FFMPEG_EXE`) — no bundled FFmpeg binary** (keep `imageio` + `imageio-ffmpeg` sdist/wrapper only, strip wheel binary) | **BSD-2-Clause** (app ships zero FFmpeg code; user supplies binary) | Windows, macOS, Linux | **Easy** | **Medium** (UX) — AVI/MP4/MPG require user to install FFmpeg or configure path; GIF still works out-of-the-box | - **Zero FFmpeg copyleft or binary-signing obligations** in the shipped installer.<br>- Shrinks frozen bundle size by ~70–85 MB.<br>- Power users / clinical workstations can point `IMAGEIO_FFMPEG_EXE` or Settings to an IT-approved `ffmpeg`. | - Out-of-the-box AVI/MP4/MPG export is unavailable until the user installs FFmpeg (friction for non-technical Windows/macOS users).<br>- Requires clear UI detection and actionable guidance in `CineExportDialog`. |
| **C. Zero-FFmpeg native export:** Pillow animated **GIF** + **Multi-frame Secondary Capture DICOM** export (drop AVI/MP4/MPG, or gate them behind optional system `ffmpeg` as in B) | **MIT-CMU / MIT** (`Pillow` + `pydicom`) | Windows, macOS, Linux | **Medium** | **Medium–High** if MP4/AVI are dropped completely; **Low** if combined with Option B | - 100% pure Python/permissive stack (`Pillow` + `pydicom`) in the default bundle.<br>- Multi-frame SC DICOM is lossless/clinical-grade and plays natively in any DICOM viewer (including DICOM Viewer V3). | - Dropping MP4/AVI breaks stock Windows 11 Media Player slide-deck/presentation workflows unless paired with Option B.<br>- GIF is 256-color palette quantized. |
| **D. `PyAV` (`av` wheel)** replacing `imageio-ffmpeg` | **BSD-3-Clause** wrapper, **but wheel-bundled `libavcodec` license varies by OS/release** (often GPLv3 on PyPI when built with `libx264`/`libx265`) | Windows, macOS, Linux | **Hard** | **High** | - In-process CFFI/Cython bindings to FFmpeg libraries; no child subprocess spawn. | - **High licensing trap:** upstream PyPI binary wheels for `av` frequently bundle `libx264`/`libx265` (GPL), and link `libavcodec` **in-process** (dynamic/static library linking rather than separate-process CLI execution).<br>- Rewrites working `encode_cine_video_from_png_paths` pipeline. |
| **E. *(Rejected)* OpenCV (`opencv-python` / `cv2.VideoWriter`)** | **GPLv3** in PyPI wheels (wrapper is Apache-2.0, but bundled FFmpeg is GPLv3) | Windows, macOS, Linux | **Hard** | **High** | *(None for this project)* | - **Explicitly rejected** ([`COMMERCIAL_RELEASE_READINESS.md`](../../COMMERCIAL_RELEASE_READINESS.md) #2, [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md) §0b): `opencv-python` wheels bundle GPLv3 FFmpeg (`libavcodec`/`libx264`/`libx265`) linked **in-process**, which is legally and architecturally worse than `imageio-ffmpeg`.<br>- Not a project dependency (~90 MB bloat).<br>- Known Windows MSMF/FourCC fallback bugs ([`MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md`](MPR_DICOM_SAVE_CINE_VIDEO_EXPORT_ANGLE_MEASUREMENT_PLAN.md) §2.1). |

---

## 4. Recommended Approach

Adopt a **two-layer hybrid of Option A (Primary for Release Builds) + Option B (Runtime Resolver & Dev/Fallback Path)**:

1. **Runtime FFmpeg Resolver (`src/gui/cine_video_export.py`):**
   - Add a dedicated helper `resolve_ffmpeg_exe() -> Path | None` that resolves an approved FFmpeg binary in deterministic priority order:
     1. Explicit `IMAGEIO_FFMPEG_EXE` environment variable (if pointing to an existing executable file).
     2. Bundled LGPL FFmpeg inside the frozen PyInstaller distribution (`Path(sys._MEIPASS) / "resources" / "ffmpeg" / <exe_name>` or platform equivalent) — sets `os.environ["IMAGEIO_FFMPEG_EXE"]` so `imageio-ffmpeg` uses it.
     3. System `ffmpeg` on `PATH` (`shutil.which("ffmpeg")`).
   - **Never** fall back to `imageio_ffmpeg`'s wheel-bundled `imageio_ffmpeg/binaries/ffmpeg-*` unless explicitly running in an unstripped dev test environment, and strip `imageio_ffmpeg/binaries` from all PyInstaller builds.
2. **Bundle a Verified LGPL-2.1+ FFmpeg Binary in Frozen Releases (Option A):**
   - Package an audited **LGPL-only** FFmpeg 7.1 binary (`--disable-gpl`, no `libx264`/`libx265`/`postproc`/`vidstab`, with `mpeg4` and `mpeg2video` encoders enabled) into the PyInstaller bundle and point `IMAGEIO_FFMPEG_EXE` to it at startup/export time.
   - Strip the `imageio_ffmpeg/binaries` directory in `DICOMViewerV3.spec` so the GPL binary from the PyPI wheel can never enter `dist/`.
3. **Graceful UI Degradation When No FFmpeg Binary Is Present (Option B safety net):**
   - If a developer or source-checkout user removes the wheel binary and has no system `ffmpeg` installed, **GIF export continues to work unconditionally**, while **AVI / MP4 / MPG** remain listed (or clearly badged) with a clear, actionable message explaining how to install `ffmpeg` or set `IMAGEIO_FFMPEG_EXE`.

---

## 5. Phased Implementation Steps

### Phase 1 — Runtime FFmpeg Resolution, License Guard & Graceful Fallback
- [ ] **Add `resolve_ffmpeg_exe()` and `probe_ffmpeg_build_config()` in `src/gui/cine_video_export.py`:**
  - Inspect: `1) os.environ.get("IMAGEIO_FFMPEG_EXE")`, `2) bundled path under sys._MEIPASS / repo resources`, `3) shutil.which("ffmpeg")`.
  - Provide a helper `probe_ffmpeg_build_config(exe_path: Path) -> dict[str, Any]` that runs `[str(exe_path), "-version"]` (`shell=False`, timeout 5 s) and checks whether `--enable-gpl`, `--enable-libx264`, `--enable-libx265`, or `--enable-nonfree` appear in the `configuration:` line.
  - Before invoking `imageio.get_writer(..., format="FFMPEG", ...)`, pin `os.environ["IMAGEIO_FFMPEG_EXE"] = str(resolved_exe)` so `imageio_ffmpeg.get_ffmpeg_exe()` uses the resolved binary.
- [ ] **Update `CineExportDialog` (`src/gui/dialogs/cine_export_dialog.py`):**
  - Update the line 149 description text from `"Video encoding uses FFmpeg via the imageio-ffmpeg package (LGPL/GPL components)."` to accurately reflect the LGPL-2.1+ bundled/system FFmpeg posture.
  - If `resolve_ffmpeg_exe()` returns `None` at dialog open, keep `"GIF"` enabled and either disable `"AVI"`, `"MP4"`, `"MPG"` with a tooltip/banner explaining how to set `IMAGEIO_FFMPEG_EXE` / install `ffmpeg`, or surface a clear message on accept.

### Phase 2 — Acquire & Pin Audited LGPL-Only FFmpeg Binaries per Platform
- [ ] **Provision LGPL-only FFmpeg 7.1 binaries for all three target OSes:**
  - **Windows (`win64`):** BtbN `ffmpeg-n7.1-latest-win64-lgpl-7.1.zip` (extract `ffmpeg.exe` + required LGPL shared DLLs if shared build, or static LGPL `ffmpeg.exe`, plus `LICENSE.txt`).
  - **Linux (`linux64`):** BtbN `ffmpeg-n7.1-latest-linux64-lgpl-7.1.tar.xz` (extract `ffmpeg` + `LICENSE.txt`).
  - **macOS (`macos-arm64` / `x86_64`):** Build or fetch a reproducible static/relocatable FFmpeg 7.1 binary configured with:
    `./configure --prefix=... --disable-gpl --disable-nonfree --disable-ffplay --disable-ffprobe --enable-ffmpeg --enable-avcodec --enable-avformat --enable-avfilter --enable-swscale --enable-swresample --enable-encoder=mpeg4,mpeg2video --enable-muxer=avi,mp4,mov,mpeg2video,mpeg1system`
    (since BtbN only publishes Windows and Linux builds, and Homebrew's default `ffmpeg` formula enables GPL dependencies).
- [ ] **Record SHA-256 checksums and provenance:**
  - Create a manifest script `scripts/fetch_lgpl_ffmpeg.py` (or CI step) that downloads the pinned release archive, verifies its **SHA-256 digest**, runs `ffmpeg -version` to assert **zero `--enable-gpl` / `--enable-nonfree` flags** and presence of `mpeg4` + `mpeg2video` encoders, and stages the binary + `LICENSE.txt` + build-config metadata into a gitignored staging directory (e.g. `build/ffmpeg-lgpl/`).

### Phase 3 — PyInstaller Spec & Build Pipeline Integration
- [ ] **Update `DICOMViewerV3.spec`:**
  - Filter out any `imageio_ffmpeg/binaries/*` entries from `a.datas` and `a.binaries` so `hook-imageio_ffmpeg.py` cannot slip the wheel's GPL binary into `dist/`.
  - Collect the staged LGPL `ffmpeg` executable and its `LICENSE.txt` / build configuration notice into the bundle under a deterministic relative path (e.g. `ffmpeg/`).
- [ ] **Update `.github/workflows/build.yml`:**
  - Add a step before `pyinstaller DICOMViewerV3.spec --clean --noconfirm` that provisions the platform's LGPL FFmpeg binary via `scripts/fetch_lgpl_ffmpeg.py` and verifies its SHA-256 and `--disable-gpl` configuration.
  - Add a post-freeze verification step that:
    1. Fails if any file matching `imageio_ffmpeg/binaries/ffmpeg*` exists inside `dist/`.
    2. Runs the bundled `ffmpeg -version` inside `dist/` and asserts `"--enable-gpl"` and `"--enable-nonfree"` are **absent** from output.

### Phase 4 — Compliance Artifacts & Documentation Alignment
- [ ] **Include LGPL-2.1+ compliance notices in the distribution:**
  - Bundle FFmpeg's `COPYING.LGPLv2.1` (or `LICENSE.txt`), copyright notices, exact `ffmpeg -buildconf` output, and the written source/relinking pointer alongside `THIRD_PARTY_LICENSES.md`.
- [ ] **Update project documentation:**
  - [`requirements.txt`](../../../requirements.txt): update the comment above `imageio` / `imageio-ffmpeg` (or install `imageio-ffmpeg` with `--no-binary imageio-ffmpeg` if feasible).
  - [`AGENTS.md`](../../../AGENTS.md), [`dev-docs/CONTRIBUTING.md`](../../CONTRIBUTING.md), [`dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](../../info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md), [`dev-docs/info/BUILDING_EXECUTABLES.md`](../../info/BUILDING_EXECUTABLES.md), [`CHANGELOG.md`](../../../CHANGELOG.md).
  - Mark item #2 complete in [`dev-docs/COMMERCIAL_RELEASE_READINESS.md`](../../COMMERCIAL_RELEASE_READINESS.md) and update [`LICENSE_AND_COMPLIANCE_PLAN.md`](LICENSE_AND_COMPLIANCE_PLAN.md) §0b once frozen verification passes on all three platforms.

### Phase 5 — Testing & Verification Gates
- [ ] **Unit & integration tests (`tests/gui/test_cine_video_export.py`):**
  - Test `resolve_ffmpeg_exe()` priority order (`IMAGEIO_FFMPEG_EXE` override → bundled path → system `PATH` → `None`).
  - Test `probe_ffmpeg_build_config()` correctly rejects `--enable-gpl` / `--enable-nonfree` outputs and accepts clean LGPL-only outputs.
  - Test end-to-end synthetic 4-frame encode to `tmp_path` for **GIF**, **AVI**, **MP4**, and **MPG** (< 512 KiB per file), verifying magic bytes and readable frame count.
- [ ] **Frozen bundle license & binary gate (all 3 OSes):**
  - Confirm zero `imageio_ffmpeg/binaries/*` files in `dist/`.
  - Confirm bundled `ffmpeg -version` has no `--enable-gpl` or `libx264`/`libx265`.
  - Run `python scripts/check_dependency_licenses.py` and Syft/ScanCode on `dist/`.
- [ ] **Manual export QA gate:**
  - Export a multi-frame cine loop (with and without overlays/ROIs, and with MONOCHROME1/MONOCHROME2) to **GIF**, **AVI**, **MP4**, and **MPG**.
  - Verify `.mp4` and `.avi` play out-of-the-box in stock **Windows 11 Media Player**, macOS QuickTime / VLC, and Linux players.
  - Verify mid-encode **Cancel** terminates the subprocess cleanly and removes the partial output file.

---

## 6. Cross-Platform Notes, Build Changes & `IMAGEIO_FFMPEG_EXE` Handling

### 6.1 Platform-Specific Packaging Details
- **Windows (`windows-latest` / x64):**
  - BtbN's `ffmpeg-n7.1-latest-win64-lgpl-7.1.zip` ships `bin/ffmpeg.exe` and `bin/*.dll` (`avcodec-61.dll`, `avformat-61.dll`, `avutil-59.dll`, `swresample-5.dll`, `swscale-8.dll`). Keeping the shared LGPL DLLs next to `ffmpeg.exe` inside the one-folder `dist/DICOMViewerV3/ffmpeg/` directory also satisfies LGPL-2.1 dynamic relinking/replacement friendliness on Windows.
  - When Windows Authenticode signing is enabled ([`BUILDING_EXECUTABLES.md`](../../info/BUILDING_EXECUTABLES.md) Step 4), include `dist/DICOMViewerV3/ffmpeg/*.exe` and `*.dll` in the `signtool` pass.
  - Ensure `subprocess` calls inside `imageio_ffmpeg` continue to use `CREATE_NO_WINDOW` on Windows so no console window flashes during cine export.
- **macOS (`macos-latest` / arm64 & x86_64):**
  - Place the LGPL `ffmpeg` Mach-O binary under `DICOMViewerV3.app/Contents/Resources/ffmpeg/ffmpeg` (or `Contents/MacOS/ffmpeg` as appropriate for notarization).
  - **Code signing & notarization:** Apple notarization requires all bundled Mach-O executables inside `.app` to be signed with **Developer ID Application** and **Hardened Runtime** (`--options runtime`) and a valid timestamp before `create-dmg` / `notarytool submit` ([`CODE_SIGNING_AND_NOTARIZATION.md`](../../info/CODE_SIGNING_AND_NOTARIZATION.md)). Do not use UPX on macOS (`USE_UPX = False` is already enforced in `DICOMViewerV3.spec`).
- **Linux (`ubuntu-latest` / x86_64 AppImage):**
  - Bundle BtbN's `ffmpeg-n7.1-latest-linux64-lgpl-7.1` `bin/ffmpeg` and `lib/*.so*` into `dist/DICOMViewerV3/ffmpeg/` before `AppDir` assembly in `.github/workflows/build.yml`, with `chmod +x`.

### 6.2 `IMAGEIO_FFMPEG_EXE` Contract
- **User / Admin Override First:** If the user or system administrator sets `IMAGEIO_FFMPEG_EXE=/path/to/ffmpeg` in the environment before launching DICOM Viewer V3, the application **must** honor that path and never overwrite it.
- **Frozen App Default:** If `IMAGEIO_FFMPEG_EXE` is unset (or points to a non-existent path) and the bundled LGPL `ffmpeg` binary exists at the expected bundle path, the app sets `os.environ["IMAGEIO_FFMPEG_EXE"] = str(bundled_ffmpeg_path)` before calling `imageio.get_writer(..., format="FFMPEG")`.
- **Subprocess Safety:** `IMAGEIO_FFMPEG_EXE` is passed as `argv[0]` to `subprocess.Popen` by `imageio-ffmpeg` with **`shell=False`**. Validate that the resolved path is an existing regular file (`os.path.isfile` and `os.access(..., os.X_OK)`) before invoking.

---

## 7. Rollback & Fallback Strategy

- **Immediate compliance fallback (zero-binary ship):** If any platform's LGPL FFmpeg build or code-signing/notarization step blocks a release cut, build with `DICOMViewerV3.spec` stripping `imageio_ffmpeg/binaries/*` and **without** bundling a replacement binary (Option B). In that fallback build:
  - **GIF** export works 100% out-of-the-box via Pillow.
  - **AVI / MP4 / MPG** automatically activate when the user installs `ffmpeg` on `PATH` or sets `IMAGEIO_FFMPEG_EXE`.
  - Zero GPL binary is distributed in the release artifact.
- **Dev environment rollback:** Developers can always set `IMAGEIO_FFMPEG_EXE` to any local `ffmpeg` binary to test encoding without modifying the spec or virtual environment.

---

## 8. Files Likely Touched (During Implementation)

| File | Planned Change |
|------|----------------|
| `src/gui/cine_video_export.py` | Add `resolve_ffmpeg_exe()`, `probe_ffmpeg_build_config()`, and set `IMAGEIO_FFMPEG_EXE` to the resolved LGPL/system binary before `imageio.get_writer(..., format="FFMPEG")`. |
| `src/gui/dialogs/cine_export_dialog.py` | Update FFmpeg license/notice wording on line 149; add graceful UI feedback if no FFmpeg executable is found for AVI/MP4/MPG. |
| `DICOMViewerV3.spec` | Strip `imageio_ffmpeg/binaries/*` from `a.datas` / `a.binaries`; include staged LGPL `ffmpeg` binary + `LICENSE.txt` in bundle. |
| `scripts/fetch_lgpl_ffmpeg.py` | **New** — download, SHA-256 verify, and audit (`--disable-gpl` check) the pinned LGPL FFmpeg 7.1 build per OS. |
| `.github/workflows/build.yml` | Run `scripts/fetch_lgpl_ffmpeg.py` before PyInstaller freeze; assert frozen bundle contains LGPL `ffmpeg` and zero `imageio_ffmpeg/binaries/*` files. |
| `requirements.txt` | Update cine export comment (and optionally document `--no-binary imageio-ffmpeg` or wrapper-only usage). |
| `tests/gui/test_cine_video_export.py` | Add unit tests for `resolve_ffmpeg_exe()`, `probe_ffmpeg_build_config()`, missing-FFmpeg graceful error, and LGPL flag verification. |
| `dev-docs/info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md` | Update FFmpeg row from GPL blocker to verified LGPL-2.1+ bundled binary once landed. |
| `dev-docs/info/BUILDING_EXECUTABLES.md` | Document the LGPL FFmpeg staging step and post-build verification check. |
| `dev-docs/COMMERCIAL_RELEASE_READINESS.md` | Check off Tier 0 item #2 once verified across Windows, macOS, and Linux frozen builds. |
| `dev-docs/plans/supporting/LICENSE_AND_COMPLIANCE_PLAN.md` | Update §0b and Decision Summary table once complete. |
| `AGENTS.md` / `CHANGELOG.md` | Update cine export FFmpeg notes and `[Unreleased]` changelog entry. |

---

## 9. Open Questions

1. **macOS LGPL FFmpeg binary source:** Since BtbN publishes prebuilt LGPL 7.1 archives only for Windows (`win64`) and Linux (`linux64`/`linuxarm64`), should our macOS CI job compile a minimal LGPL FFmpeg 7.1 binary from the official FFmpeg 7.1 source tarball (cached in GitHub Actions by source SHA-256 + configure flags), or pull from a dedicated internal release asset repo?
2. **Static vs. shared LGPL FFmpeg executable:** FFmpeg is an external CLI helper invoked in a **separate process** via `subprocess.Popen` (not linked into the Python interpreter or app process). Does counsel prefer shipping the **shared** LGPL FFmpeg build (`ffmpeg` + `libav*.dll`/`.so`/`.dylib` in `dist/DICOMViewerV3/ffmpeg/`) so end users can trivially swap the FFmpeg shared libraries too, or is a single **static** LGPL `ffmpeg` executable plus source/build-script offer sufficient since it is an independent executable?
3. **Should we also add Multi-frame Secondary Capture DICOM cine export (Option C) as a P2 feature enhancement?** While not needed to unblock Windows 11 Media Player `.mp4` export, exporting a rendered cine loop (with burned-in overlays/LUT) as a multi-frame Secondary Capture DICOM series is a natural medical-imaging complement.
4. **Runtime GPL guard policy for user-supplied `IMAGEIO_FFMPEG_EXE`:** When a user explicitly sets `IMAGEIO_FFMPEG_EXE` to their own system `ffmpeg` (which may be a Homebrew/apt GPL build), our app is not distributing that binary. Confirm that the `--disable-gpl` assertion runs **strictly on our bundled/packaged binary in CI and release builds**, while allowing user-supplied system `ffmpeg` at runtime without blocking the user.
