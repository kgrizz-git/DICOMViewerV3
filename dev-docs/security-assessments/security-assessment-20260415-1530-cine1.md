# Security assessment — CINE1 slice (targeted)

**Date:** 2026-04-15  
**Scope:** `requirements.txt` (imageio / imageio-ffmpeg pins), `src/core/cine_video_export.py`, `src/gui/dialogs/cine_export_encode_thread.py`, `src/gui/dialogs/cine_export_dialog.py`, `src/main.py` (`_on_export_cine_video`), `src/core/app_signal_wiring.py`, `src/gui/main_window_menu_builder.py` (menu only).

## Tools

| Tool | Result |
|------|--------|
| **Semgrep** `p/python` + `p/security-audit` | **0** findings on the 5 small files + **`src/main.py`** (rules run: 200 each scan). |
| **gitleaks** | **Not installed** in local PATH; repo CI uses **TruffleHog** (range scan) in `.github/workflows/security-checks.yml` — not re-run here. |

## Executive summary

No Semgrep-flagged dangerous patterns in scoped paths. Cine export uses **imageio / imageio-ffmpeg** (FFmpeg subprocess inside the library; app code documents **no `shell=True`**). User-controlled **output path** comes from the native save dialog and is not passed through a shell. **Video format** is constrained to **GIF / AVI / MPG** in `encode_cine_video_from_png_paths`. Temp frames use **`tempfile.mkdtemp`** with a fixed **`f{step:05d}.png`** naming scheme.

## Dependency and supply-chain

- **`imageio==2.37.3`** and **`imageio-ffmpeg==0.6.0`** are **exact pins** — good for reproducible builds and predictable FFmpeg bundling.
- **`imageio-ffmpeg`** ships a **prebuilt FFmpeg** in the wheel: treat as **trusted third-party binary** (verify hashes on bump, monitor advisories). **License / redistribution:** LGPL/GPL components are noted in-repo (`README.md`, `AGENTS.md`, `CHANGELOG`); PyInstaller/frozen builds need compliance with FFmpeg obligations.
- **`IMAGEIO_FFMPEG_EXE`** (if used later) would shift trust to the **host-provided** binary — document integrity expectations for enterprise deployments.

## Application controls (subprocess, paths, temp, cancel)

- **Command injection:** No app-owned `subprocess` with user strings; FFmpeg invocation is via imageio. **`ffmpeg_params`** in MPG path are **static** (`-f`, `mpeg`).
- **Path safety:** Default filename stem is derived from **SeriesDescription** with removal of **`<>:"/\|?*`** and length cap — reduces odd / reserved names on Windows.
- **Temp data:** **`tempfile.mkdtemp(prefix="dv3_cine_")`**; **`cleanup_temp_frame_dir`** in **`finally`** — good hygiene (PHI in frames is expected for DICOM export; user responsibility aligns with other exports).
- **Cancel:** **`threading.Event`** checked during encode loops; render loop uses **`QProgressDialog.wasCanceled()`**. Encoding dialog **`canceled`** connects to **`cancel_event.set()`**. Residual risk: FFmpeg may not exit instantly on cancel (library-dependent) — **availability / UX**, not a typical integrity break.
- **Thread join:** **`enc_thread.wait(60_000)`** after event loop quit — if the worker ever **hung past 60s**, **`finally`** could remove temp PNGs while the thread still runs (**race / crash** risk) — **reliability**; consider documenting or tightening join policy if seen in the field.

## Low / informational

- **`CineVideoEncodeThread.run`:** broad **`except Exception`** emits **`str(exc)`** to the UI — could surface **paths** from low-level errors; acceptable for desktop diagnostic, avoid logging raw errors to shared telemetry without redaction.

## Remediation order

1. **None required** for blocking security defects from this pass.  
2. **Ongoing:** keep **pins** and **`pip audit` / OSV** hygiene on **imageio** family when bumping.  
3. **Optional hardening:** align **`wait()`** / cleanup ordering if timeout scenarios become a support issue.
