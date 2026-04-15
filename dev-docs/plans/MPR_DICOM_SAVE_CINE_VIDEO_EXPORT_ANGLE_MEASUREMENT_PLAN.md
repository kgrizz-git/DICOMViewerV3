# MPR DICOM Save, Cine Video Export, and Angle Measurement – Implementation Plan

This document implements three related items from `dev-docs/TO_DO.md` (**Features (Near-Term)**):

1. **Save MPRs as DICOM** (P1)
2. **Export cine as MPG/GIF/AVI** (P1)
3. **Angle measurement** — two connected line segments with on-screen angle (P2; reuse measurement styling)

**Related context**

- Existing MPR pipeline: `src/core/mpr_builder.py` (`MprResult`), `src/core/mpr_volume.py`, `src/core/mpr_controller.py`, `src/core/mpr_cache.py` (NPZ cache is **not** a substitute for standards-based DICOM export).
- Broader MPR/oblique plan: [SLICE_SYNC_AND_MPR_PLAN.md](SLICE_SYNC_AND_MPR_PLAN.md) (ROIs/measurements on MPR are still deferred there; **this plan** assumes angle and linear measurements remain **disabled on MPR subwindows** unless product direction changes).
- Cine: `src/gui/cine_player.py`, `src/gui/cine_controls_widget.py`, wiring in `src/core/app_signal_wiring.py` and handlers in `src/main.py` (`_on_cine_frame_advance`, etc.).
- Linear measurements: `src/tools/measurement_tool.py`, config under measurement settings in `src/utils/config/` (`measurement_config.py`), integration in `src/core/slice_display_manager.py` and per-subwindow managers in `src/core/subwindow_lifecycle_controller.py`.

---

## 1. Save MPRs as DICOM

### Goal

Allow the user to **write the computed MPR stack** (the same slices shown in an MPR subwindow) to one or more **DICOM CT/MR-style** instances (or a secondary capture SOP Class if you choose to minimize modality claims — see decisions below) so other tools can ingest them.

### Prerequisites

- [ ] Confirm legal/clinical disclaimer: exported MPR series are **derived**; UIDs must be new; patient/study identifiers policy (copy vs anonymize) must match existing export/privacy rules.
- [ ] Inventory what metadata is already available on `MprResult` and the **source** series datasets (first slice or representative instance).

### Design decisions (resolve before coding)

| Topic | Options | Recommendation |
|-------|---------|----------------|
| **SOP Class** | Standard MR/CT Image Storage vs Secondary Capture | Prefer **same general image storage class as source** when modality and attributes are coherent; otherwise **Secondary Capture** (0028,0008) to avoid invalid MR/CT IOD claims. |
| **Frame of reference** | Copy source Frame of Reference UID vs new | **Copy** when geometry is traceable to source; ensures registration tools still relate stacks. |
| **Pixel data** | Raw (BitsAllocated/BitsStored) vs float pipeline | Write **consistent with source** where possible (e.g. apply rescale for display HU only if you also set slope/intercept consistently). Map `MprResult` float slices to output dtype using a documented window (min/max or percentile) or **store slope/intercept** from known rescale. |
| **Series description** | User suffix vs fixed prefix | Default description like `MPR <orientation> from <SeriesDescription>`; optional user suffix in save dialog. |
| **Multi-file API** | One file per slice vs multi-frame | **One file per slice** matches most stacks today and simplifies per-instance UIDs; multi-frame is a later optimization. |

### Implementation outline

1. **Entry point**  
   - Add **“Save MPR as DICOM…”** (or under **Export**) when the **focused subwindow is MPR mode** and a completed `MprResult` (or equivalent in-memory slices + `SliceStack`) is available.  
   - Mirror UX patterns from existing export dialogs (`src/gui/dialogs/export_dialog.py`, `src/core/export_manager.py`) for folder picker, progress, and errors.

2. **Writer module**  
   - New module e.g. `src/core/mpr_dicom_export.py` (or under `src/utils/`) with a pure-ish function:  
     `write_mpr_series(output_dir, mpr_result, template_dataset, options) -> list[Path]`  
   - **UIDs**: new `StudyInstanceUID` only if policy requires; always new `SeriesInstanceUID`, new `SOPInstanceUID` per slice; consistent `SeriesNumber` / `InstanceNumber`.

3. **Metadata**  
   - **Copy** from template: patient/study level tags, referenced source series UID in private tag or `SourceImageSequence` (0018,2107), `ImageType` including `DERIVED\SECONDARY` as appropriate.  
   - **Set** per slice: `ImagePositionPatient`, `ImageOrientationPatient`, `PixelSpacing`, `SliceThickness`, `SpacingBetweenSlices` (if applicable) from `MprResult.slice_stack` and `output_spacing_mm` / `output_thickness_mm`.  
   - **Window/level**: optional preset tags from current viewer W/L or from min/max of slice.

4. **Verification**  
   - Round-trip: load written series in this app and in an external validator (dciodverify / dcmdump).  
   - Unit tests with a **minimal synthetic** `MprResult` or fixture slices (no PHI).

5. **Changelog / version**  
   - Document new behavior and any new optional dependency (none expected if using `pydicom` + NumPy only).

### Out of scope (initial pass)

- Sending to PACS / DIMSE  
- Lossless float32 MPR storage as DICOM float pixels (rare; most tools expect integer pixels + rescale)

---

## 2. Cine video export (MPG, GIF, AVI) — **Task ID: CINE1**

### Goal

From a **cine-capable** subwindow, export the **full loop** (respecting loop bounds and direction if applicable) to **MPG (MPEG)**, **GIF**, or **AVI**, at a user-chosen frame rate (default: effective cine FPS from `CinePlayer` / DICOM).

**Single-branch phasing (orchestrator default):** **M1** implements **CINE1** before **RDSR1** / **ROI_RGB1** / **HIST_PROJ1** unless a second worktree is approved.

### Task graph and gates

| Ordering | Notes |
|----------|--------|
| After dependency row locked in plan + optional **`researcher`** brief → **UI/dialog** → **frame iterator** → **encoders** → **progress/cancel** → **tests** + **CHANGELOG** | Do not edit `requirements.txt` until the dependency gate is explicit in state/plan. |
| **Verification gates** | (1) **`reviewer`** — export path, cancel semantics, no `shell=True`. (2) **`tester`** — full pytest + ledger when slice ends. (3) **`secops`** — if new native binaries / subprocess invocations land. |

**Multi-window / sync cine (deferral):** `dev-docs/TO_DO.md` **L105** (*cine playback across multiple windows: sync vs independent*) is **out of scope** for **CINE1** MVP export. **MVP:** export **only the focused subwindow’s** cine loop and bounds. Document follow-up in L105 or a future plan slice when product chooses sync semantics.

### Prerequisites

- [ ] Decide dependency strategy using **§2.1 Dependency decision matrix** (record chosen row in plan + `CHANGELOG` / `AGENTS.md` if install steps change).
- [ ] Privacy: same rules as screenshot export (optional burn-in vs clean pixels; respect **Privacy Mode**).
- [ ] **UX (defer to `ux`):** whether export uses **LUT-applied “as displayed”** pixels vs **raw/rescaled array** first (matrix size vs fidelity).

### Design decisions

| Topic | Recommendation |
|-------|----------------|
| **Resolution** | Native pixel matrix of the displayed image after standard LUT **or** explicit “as displayed” (if W/L and zoom must match UI, add a second mode later). |
| **Scope** | **Focused subwindow** first; multi-window batch **deferred** (see L105). |
| **Palette GIF** | Quantize to 256 colors; document quality tradeoff for medical grayscale. |
| **MPG vs MP4** | User asked for **MPG**; implement **MPEG-1/2** or **transport** as supported by chosen backend; if only MP4 is trivial, document mapping (e.g. “MPG via ffmpeg `-f mpeg`”). |

### §2.1 Dependency decision matrix (encoding backend)

| Approach | Distribution | Pros | Cons / pitfalls |
|----------|--------------|------|------------------|
| **`imageio` + `imageio-ffmpeg`** | PyPI; may vendor **ffmpeg** binary via `imageio-ffmpeg` | Single pip story on Windows; API for GIF/MP4/MPEG depending on backend build | Wheel **size**; **license** stack (ffmpeg LGPL/GPL components — confirm ship posture for frozen **PyInstaller** bundle); version **pin** discipline |
| **ffmpeg / ffprobe subprocess** | User-installed or app installer | Maximum **codec** flexibility; no Python-native encoder maintenance | **PATH** / “not installed” UX; **quoting** and **no `shell=True`**; **cancel** = terminate child process + cleanup partial file; Windows ** Defender** / execution policy friction |
| **`opencv-python` + `cv2.VideoWriter`** | PyPI wheel | Familiar to CV devs | On Windows, **fourcc** / backend often falls back to **MSMF** with **limited** MPEG-1; many deployments still need **ffmpeg** DLL for reliability |
| **Qt Multimedia** (`PySide6` already present) | Qt runtime | Theoretically native | **Codec availability** varies by OS install; **GIF** support is awkward; higher **integration** cost for batch frames |
| **Pillow / imageio GIF-only path** | Mostly Python + numpy | **GIF** without native video stack | **No MPG/AVI**; slow on large matrices; **256-color** quantization |

**Windows codec pitfalls (all backends):** missing **H.264/MPEG** encoders on stock Windows; **MSMF** rejecting fourcc; **32-bit vs 64-bit** ffmpeg mismatch in PATH; long paths and **antivirus** locks on temp files during encode.

**Recommendation for planner (non-binding):** short **`researcher`** spike comparing **`imageio`+`imageio-ffmpeg`** vs **documented optional system ffmpeg** for **MPG**; use **GIF** path that works with minimal deps first if product wants incremental ship.

### UI entrypoints (MVP)

- [ ] **File → Export** (or **Tools**) submenu: **“Export cine as…”** — gated on **cine-capable** series in **focused** subwindow (mirror **MPR save** eligibility patterns: clear message if disabled).  
  `parallel-safe: no`, `stream: N`, `after: none` — touches `main_window_menu_builder.py`, `app_signal_wiring.py`, `main.py` / facade hooks.
- [ ] **Cine toolbar** affordance (optional second entry): icon or overflow **“Export…”** — **`ux`** decides clutter vs discoverability.  
  `parallel-safe: no`, `stream: N`, `after: none`
- [ ] **Dialog fields:** output path, **format** (GIF / AVI / MPG), **FPS**, **loop range** (reuse `CineControlsWidget` / `CinePlayer` loop bounds if present), **include overlays** (checkbox; default off or match PNG export — **`ux`**).
- [ ] Dialog **WindowStaysOnTopHint** only at open; defocus behavior per app rule (match `mpr_dicom_save_dialog` / export dialogs).

### Frame source

- [ ] **Loop bounds:** export frames in **`[loop_start, loop_end]`** inclusive (or full `0 … N-1` if loop disabled); respect **direction** if cine supports reverse.
- [ ] **Deterministic stepping:** advance with same logic as `_on_cine_frame_advance` / slice navigator **without** relying on `QTimer` tick timing (no dropped frames).  
  `parallel-safe: no`, `stream: N`, `after: dependency-gate`
- [ ] **Pixel source:** single code path chosen in design table (viewport grab vs `SliceDisplayManager` / export pixmap pipeline); document **fusion** and **Privacy Mode** behavior explicitly.
- [ ] **Multi-window:** **not** in **CINE1** MVP — see **L105** deferral above.

### Encoding options (MPG vs AVI vs GIF)

- [ ] **GIF:** per-frame delay from FPS; **quantize** if RGB intermediate; document medical grayscale limitation.
- [ ] **AVI:** pick **fourcc** compatible with chosen backend; document **Windows** fallback behavior.
- [ ] **MPG:** target **MPEG-1 System** or documented **ffmpeg** `-f mpeg` mux; if backend only yields **MP4**, ship **MP4** behind same dialog with **user-visible** format list update + **`CHANGELOG`** **Changed** entry (requires **product** sign-off — **`needs_user`** if MPG is strict).

### Progress / cancel

- [ ] **`QThread`** worker + **`QProgressDialog`** (reuse patterns from `LoadingProgressManager` / `export_manager.py`).
- [ ] **Cancel:** cooperative flag between frames; on hard cancel, delete **partial** output file where safe; document **leftover** behavior in dialog help text (align **MPR2** reviewer note on partial files).
- [ ] **Memory:** prefer **streaming** frames into encoder when API allows; otherwise cap concurrent buffered frames or document RAM risk for large matrices.

### Test strategy

| Layer | Content |
|-------|---------|
| **Unit** | Pure helpers: frame index list from loop settings; rescale/FPS timing math. |
| **Integration** | Small synthetic **multi-frame** fixture (4–8 frames, low res) → export to **`tmp_path`** → assert **file exists**, **size > 0**, optional **magic bytes** / `imageio.imread` frame count **≤ cap** (avoid golden blobs in git). |
| **Golden / binary** | **Avoid** committing large video artifacts; cap artifact size in CI (e.g. `< 512 KiB` per test file). |
| **Manual smoke** | Full-screen / overlay on/off; cancel mid-run; re-open file in external player. |

### `CHANGELOG` / version expectations

- [ ] **`CHANGELOG.md` [Unreleased] Added** — user-visible **Export cine** + formats + dependency/install note if applicable.
- [ ] **`src/version.py`** — bump per **`dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`** only at release boundary; feature accumulation may stay **[Unreleased]** until release chore.
- [ ] **`README.md` / `AGENTS.md`** — if users must install **ffmpeg** or accept **imageio-ffmpeg** binary, document explicitly.

### Implementation outline (concise)

1. **UI** — Dialog + menu/toolbar wiring; eligibility checks.  
2. **Frame capture** — Deterministic index loop + pixel grab path.  
3. **Encode** — Pluggable backend per matrix row §2.1.  
4. **Worker** — Thread + progress + cancel.  
5. **Tests + docs** — As above.

### Risks

- **Performance**: large matrices × many frames → memory; stream frames to encoder when possible.  
- **IP/licensing**: confirm codec libraries are OK for distribution in packaged executables.  
- **Windows variability**: codec / PATH / AV locks — mitigate with clear errors and **docs**.

---

## 3. Angle measurement tool

### Goal

**Three-click** interaction:

1. First click: vertex / hinge point (start of both arms, per product choice — see below).  
2. Second click: first arm endpoint.  
3. Third click: second arm endpoint.  
Display **two line segments** and the **interior angle** (and optionally the **supplementary** angle) with **same color / line thickness / font** as linear measurements.

### Interaction semantics (pick one and document in UI strings)

**Option A (typical “angle at point A”)**  

- Click 1 = **vertex**, click 2 = one ray point, click 3 = other ray point.  
- Angle = angle between vectors **(2−1)** and **(3−1)**.

**Option B (elbow from TO_DO wording)**  

- Click 1 → 2 = first segment; click 3 extends from **vertex at 2** — actually matches “line extends, second click drops point, third segment from there” = polyline **P1–P2–P3**, measure angle at **P2** between segments **P1–P2** and **P2–P3**.

The TO_DO text matches **Option B** (vertices P1–P2–P3 with angle at **P2**). Implement **Option B** unless UX review prefers vertex-first.

### Implementation outline

1. **Data model**  
   - Extend `MeasurementItem` or add `AngleMeasurementItem` in `measurement_tool.py` storing three scene coordinates + computed angle in degrees.  
   - Persistence: extend serialization used for copy/paste and session restore (`annotation_paste_handler.py`, any JSON/session code) with a **versioned** type discriminator.

2. **Painting**  
   - Two `QGraphicsLineItem` (or path) + text item for `θ = xx.x°`; reuse measurement font and pen from config via existing helpers.

3. **State machine**  
   - Idle → after tool activate: `waiting_p1` → `waiting_p2` → `waiting_p3` → commit → idle.  
   - Esc cancels; right-click behavior matches linear measurement tool.

4. **Wiring**  
   - Toolbar / menu: “Angle” next to distance measurement.  
   - Disable on MPR subwindows if linear measurements remain disabled (consistent with [SLICE_SYNC_AND_MPR_PLAN.md](SLICE_SYNC_AND_MPR_PLAN.md)).

5. **Export / screenshots**  
   - Include angle graphics in PNG/JPG export paths where linear measurements are drawn (`export_manager.py`).

6. **Tests**  
   - Pure geometry: known points → expected angle (0°, 90°, 180°).  
   - Optional: Qt graphics test for hit regions if you add dragging handles later (out of scope unless requested).

### Out of scope (initial pass)

- Oblique 3-D angle in patient space (use **in-plane** image coordinates unless pixel spacing is applied consistently for “true” angle — document as **in-plane angle** using **row/column** directions).

---

## Suggested implementation order

1. **Angle measurement** — localized to `measurement_tool` + export + config; lowest integration risk.  
2. **MPR DICOM save** — new writer + dialog; depends on stable `MprResult` access from `MprController`.  
3. **Cine video export** — dependency and packaging decisions; heaviest QA.

---

## Checklist (high level)

### MPR DICOM save

- [x] Dialog + eligibility (MPR focused subwindow only) — **2026-04-14:** File → **Save MPR as DICOM…** + ``MprController.prompt_save_mpr_as_dicom``; message if not MPR / no stack.
- [x] `mpr_dicom_export` writer with UIDs and geometry tags — **`src/core/mpr_dicom_export.py`**; optional **ReferencedSeriesSequence** to source series.
- [x] Privacy / anonymization alignment — reuses **`DICOMAnonymizer`**; export folder names follow anonymized template when enabled.
- [x] Tests + manual round-trip validation — **`tests/test_mpr_dicom_export.py`** (pydicom read-back); manual external validator still optional.
- [x] `CHANGELOG.md` + version bump per release rules — **CHANGELOG** [Unreleased] **Added**; **`src/version.py`** unchanged (pre-release accumulation per repo pattern).

### Cine export (**CINE1** — see §2 phased checklist)

- [x] **(CINE1-S0)** Dependency row chosen + optional **`researcher`** brief logged (`parallel-safe: yes`, `stream: N`, `after: none`) — **2026-04-14:** **`imageio` + `imageio-ffmpeg`** pinned in **`requirements.txt`**; orchestration **`dependency_row_locked`**.
- [x] **(CINE1-P1)** UI entrypoints + export dialog + eligibility (focused subwindow; **L105** out of scope) — **2026-04-14:** **File → Export cine as…**, **`CineExportDialog`**, **`describe_focused_cine_export_blocker`** (MPR + non-cine gating).
- [x] **(CINE1-P2)** Off-timer frame iteration + pixel capture path (overlays / privacy behavior documented) — **2026-04-14:** deterministic index list + **`rasterize_cine_export_frame`** (same PIL path as PNG export; overlays optional; **Privacy** follows overlay/export rules when overlays on).
- [x] **(CINE1-P3)** GIF / AVI / MPG encode paths per §2.1 matrix — **2026-04-14:** **`encode_cine_video_from_png_paths`** (GIF-PIL writer, FFMPEG **png** in AVI, **mpeg2video** + **`-f mpeg`** for MPG).
- [x] **(CINE1-P4)** `QThread` + progress + cancel + partial-file policy — **2026-04-14:** **`CineVideoEncodeThread`** for encode; main-thread render + **`QProgressDialog`** cancel; partial output removed on failure/cancel.
- [x] **(CINE1-P5)** Tests (size-capped) + `CHANGELOG.md` + docs if deps change — **2026-04-14:** **`tests/test_cine_video_export.py`**, **`CHANGELOG`** [Unreleased], **`README`** / **`AGENTS.md`** FFmpeg note.

### Angle measurement

- [x] Three-click tool + visuals + config reuse — **2026-04-14:** toolbar **Angle** / **Shift+M**, `measure_angle` mode, `AngleMeasurementItem` + previews
- [x] Export + paste/copy compatibility — **`export_rendering`**, clipboard `measurement_kind` `angle` / `distance`
- [x] Tests for geometry math — **`tests/test_angle_measurement_geometry.py`**
- [x] `CHANGELOG.md` — **[Unreleased] Added**
