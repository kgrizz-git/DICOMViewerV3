# Executable Size Reduction Plan

**Status:** Not started  
**Priority:** P0  
**TO_DO ref:** Performance / Packaging — "See if executables can be made smaller (especially on macOS)"

---

## Goal

Reduce the PyInstaller-built executable/bundle size on **all three platforms** (Windows, macOS, Linux) through systematic measurement, dependency auditing, and targeted exclusions — without breaking runtime functionality.

### Prior work

- **Completed plan:** `plans/completed/pyinstaller-bundle-size-macos-2026-04-09.md` — established macOS slim build via `PYINSTALLER_MACOS_SLIM` and `MACOS_PYSIDE6_MODULE_EXCLUDES`.
- **Existing excludes:** `scripts/pyinstaller_exclude_lists.py` — PIL/Tk, matplotlib backends, macOS PySide6 modules.
- **Baseline doc:** `dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md` — measurement instructions, rough Qt module size estimates.
- **Audit test:** `tests/test_pyinstaller_exclude_audit.py` — verifies excludes don't conflict with actual imports.

This plan extends that work cross-platform and goes deeper.

---

## Phase 1 — Baseline measurement (all platforms)

- [ ] Build on Windows, macOS (normal + slim), and Linux from the **same commit**.
- [ ] Record total bundle size and top-20 largest files/directories in each bundle.
- [ ] Record in a new markdown table in `dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md` with commit hash and date.
- [ ] Identify the **top 5 size contributors** on each platform (likely: PySide6/Qt, VTK, SimpleITK, numpy, matplotlib, pylinac).

## Phase 2 — Dependency audit

### 2a. Import graph analysis

- [ ] Run `pyinstaller --collect-all` dry-run or use `modulegraph` / `PyInstaller.utils.hooks` to dump the full import graph.
- [ ] Identify modules pulled in by transitive imports that are **never reached** at runtime:
  - VTK: which VTK modules are imported? Only `vtkRenderingCore`, `vtkRenderingVolume`, `vtkCommonDataModel`, `vtkIOImage`, `vtkInteractionStyle`, `vtkFiltersCore` are needed. Exclude the rest.
  - SimpleITK: only image resampling functions used; check if heavyweight sub-packages (registration, segmentation) get pulled in.
  - pylinac: pulls in scikit-image, scipy, etc. — these are needed, but check for test data or example files bundled.
  - matplotlib: only `FigureCanvasQTAgg` used; verify no data files (sample images, fonts beyond what's needed) are bundled.

### 2b. Data file audit

- [ ] List all `datas` entries in `DICOMViewerV3.spec` and their sizes.
- [ ] Check for bundled test data, sample DICOMs, documentation, or dev-only files.
- [ ] Check for duplicate font files (app bundles its own fonts via `bundled_fonts.py`; Qt may also include fonts).
- [ ] Check if pylinac bundles reference images or calibration data that can be loaded on-demand instead.

### 2c. Platform-specific Qt trims

- [ ] **Windows:** Apply the same PySide6 module exclusion strategy as macOS slim. Qt WebEngine alone can add 150+ MB. Verify app doesn't use WebEngine, then exclude on all platforms.
- [ ] **Linux:** Same as Windows. Also check for bundled `libicu` (often 30+ MB) and whether system ICU can be used.
- [ ] **All platforms:** Audit Qt plugins (`imageformats`, `platforms`, `styles`, `sqldrivers`) — keep only what's needed:
  - `imageformats`: keep `qjpeg`, `qico`, `qsvg`; likely remove `qtiff`, `qwebp`, `qpdf` etc.
  - `sqldrivers`: keep `qsqlite` only (if needed for anything besides sqlcipher which bundles its own).
  - `platforms`: Windows needs `qwindows`; macOS needs `qcocoa`; Linux needs `qxcb` or `qwayland`.

## Phase 3 — Targeted exclusions

- [ ] Extend `scripts/pyinstaller_exclude_lists.py` with new exclusion lists:
  - `VTK_UNUSED_MODULE_EXCLUDES` — VTK modules not imported by `volume_renderer.py` or `volume_viewer_widget.py`.
  - `PYSIDE6_CROSS_PLATFORM_EXCLUDES` — WebEngine, 3D, Multimedia, etc. (superset of current macOS-only list, applied everywhere).
  - `QT_PLUGIN_EXCLUDES` — unused image format and SQL driver plugins.
- [ ] Update `DICOMViewerV3.spec` to apply cross-platform excludes unconditionally (not just macOS slim).
- [ ] Extend `tests/test_pyinstaller_exclude_audit.py` to cover new excludes — verify no `src/` or `tests/` file imports excluded modules.

## Phase 4 — Advanced optimizations (if needed)

- [ ] **UPX compression:** PyInstaller supports UPX for compressing binaries. Test on Windows and Linux (macOS code-signing may conflict). Measure size reduction vs startup time impact.
- [ ] **`--onefile` vs `--onedir`:** Current build is `--onedir`. `--onefile` compresses into a single executable (smaller download, slower startup due to extraction). Evaluate tradeoff; may offer as an alternative artifact.
- [ ] **Lazy VTK import:** If VTK is a major contributor and the user hasn't opened a 3D view, defer VTK import entirely. This doesn't reduce bundle size but could enable a "lite" build profile that excludes VTK entirely for users who don't need 3D.
- [ ] **Strip debug symbols:** Verify that `strip` is applied to `.so`/`.dylib`/`.pyd` files in the bundle (PyInstaller may already do this).

## Phase 5 — CI integration & regression tracking

- [ ] Add a **size reporting step** to `.github/workflows/build.yml` that logs total bundle size to the job summary on every build.
- [ ] Set a **size budget** (e.g. Windows < 400 MB, macOS < 350 MB) with a warning annotation if exceeded.
- [ ] Update `PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md` with post-optimization baselines.

---

## Verification gates

- [ ] All three platform builds succeed with new excludes.
- [ ] `test_pyinstaller_exclude_audit.py` passes (no excluded module is actually imported).
- [ ] Manual smoke test on each platform: app starts, loads DICOM folder, fusion works, 3D render opens, pylinac analysis runs, export works.
- [ ] Bundle size reduced by measurable amount (target: **≥ 20% reduction** on at least one platform, or documented explanation why not achievable).

---

## Open questions

1. **VTK as optional:** Should we offer a build **without** VTK for users who don't need 3D rendering? That could save 50–100+ MB.  Would require the 3D menu items to show "VTK not available" gracefully.
2. **SimpleITK alternatives:** SimpleITK is large. For the limited resampling we do, could `scipy.ndimage` suffice? This is a bigger refactor and may belong in a separate plan.
3. **pylinac modularity:** Can pylinac be imported lazily so its heavy deps (scikit-image, scipy) aren't loaded at startup? This helps startup time more than bundle size.

---

## Files likely touched

| File | Change |
|------|--------|
| `scripts/pyinstaller_exclude_lists.py` | New cross-platform exclude lists |
| `DICOMViewerV3.spec` | Apply cross-platform excludes |
| `tests/test_pyinstaller_exclude_audit.py` | Cover new excludes |
| `.github/workflows/build.yml` | Size reporting step |
| `dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md` | Updated baselines |
