# Performance / Memory / Responsiveness Deep Dive — Implementation Plan

**Created:** 2026-05-24
**Covers TO_DO items:**
- [P1] Performance / memory / responsiveness deep dive (line 49)
- [P1] Try to make code faster (line 50)

---

## Context

The app has no profiling infrastructure and several known performance bottlenecks discovered via static code review. The most critical: **file loading runs entirely on the UI thread**, **3D fusion re-extracts a ~300 MB volume on every scroll**, and **multiple redundant array copies** occur per displayed frame. This plan establishes measurement first (Phase 0), then attacks high-impact fixes (Phase 1), moderate refactors (Phase 2), and architectural changes (Phase 3).

---

## Phase 0 — Profiling Infrastructure (measure before optimizing)

No behavior changes. Add instrumentation behind `DICOM_PERF_LOG=1` env var.

- [x] **P0.1 Startup timing:** Add `time.perf_counter()` checkpoints in `src/main.py` at: end of imports (line ~161), end of `__init__`, after `main_window.show()`. Write `scripts/benchmark_startup.py` that runs the app 5x and records median to `dev-docs/perf-baselines/startup.csv`.
- [x] **P0.2 Per-operation timer:** Create `src/utils/perf_timer.py` — a context manager emitting `[PERF] label: Xms` at DEBUG level when env var is set; no-op otherwise. Instrument: `image_resampler.get_resampled_slice`, `fusion_processor.create_fusion_image`, `dicom_loader.load_files` (total), `mpr_controller._display_mpr_slice`, `image_viewer_view.set_image`, `apply_window_level`, `index_service.search`, `index_service.search_grouped_studies`.
- [x] **P0.3 Memory snapshot:** Create `scripts/memory_profile_load.py` using `tracemalloc` to capture before/after snapshots of a 100-file folder load. Record top-20 allocations + peak RSS.
- [x] **P0.4 Baseline:** Run all benchmarks, archive results to `dev-docs/perf-baselines/`.

**Gate:** 3 benchmark scripts run and produce output files.

---

## Phase 1 — High-Impact Quick Wins (no architecture changes)

Each item is independently testable, ~1-2 hours, no behavior change.

### P1.1 — [DONE] 3D fusion: cache extracted numpy volume (HIGHEST IMPACT)

**File:** `src/core/image_resampler.py` line 581
**Problem:** `sitk_to_numpy(resampled_volume)` extracts the FULL 3D numpy array (~300 MB for 300-slice CT) on every scroll, just to take one 2D slice.
**Fix:** Add `self._numpy_cache: dict` alongside `self._cache`. On cache hit, return the already-extracted ndarray. Only call `sitk_to_numpy()` once per volume.
**Expected:** Fusion scroll latency drops 60-80%. ~300 MB allocation eliminated per scroll.
**Verify:** `tests/fusion_audit_*.py` pass; PerfTimer `fusion_3d_get_slice` drops from >100ms to <5ms.

### P1.2 — [DONE] 3D fusion: cache sorted/deduplicated dataset list

**File:** `src/core/image_resampler.py` lines 509-510
**Problem:** `_sort_datasets_by_location()` + `_filter_duplicate_locations()` run O(N^2) on every warm-cache scroll request.
**Fix:** Add `self._sorted_reference_cache: dict[str, list]` keyed by series UID. Skip sort+filter on hit. Clear when `clear_cache()` is called.
**Verify:** Assert sort is called at most once per series UID.

### P1.3 — [DONE] Fusion blend: eliminate redundant astype and stack

**File:** `src/core/fusion_processor.py` lines 162-163, 254, 285
**Problem:** Unconditional `.astype(np.float32)` even when already float32 (2 wasted copies); `np.stack([x]*3)` triples arrays instead of broadcasting (4x memory waste).
**Fix:**
- Guard casts: `if arr.dtype != np.float32: arr = arr.astype(np.float32)`
- Replace `np.stack([x]*3, axis=-1)` with `np.broadcast_to(x[..., np.newaxis], (*x.shape, 3)).copy()` or defer to blend step
- Cast colormap output to float32 immediately (line ~279 returns float64 RGBA)
**Verify:** `tests/fusion_audit_quantitative_verification.py` — all 33 slices at 0% error.

### P1.4 — [DONE] MPR display: eliminate redundant float32 casts

**File:** `src/core/mpr_controller.py` lines 870, 1687
**Problem:** Two redundant `.astype(np.float32)` on already-float32 data per scroll. `_array_to_pil()` also does two separate allocations (clip + uint8) that could be one.
**Fix:** Guard with dtype check; fuse clip+uint8 into single operation.
**Verify:** `tests/test_mpr_core.py` passes; identical visual output.

### P1.5 — [DONE] Study index: skip repeated init_schema() and keyring lookup

**File:** `src/core/study_index/index_service.py` lines 70-72
**Problem:** Every query creates a fresh `StudyIndexStore`, calls `init_schema()` (PRAGMA key + schema check), and hits `keyring.get_password()` (OS credential store) — all blocking.
**Fix:** Add `_schema_initialized: bool` flag. After first successful `init_schema()`, skip on subsequent calls. Reset on `_db_path()` change.
**Verify:** `tests/test_study_index_store.py` passes; PerfTimer improves.

### P1.6 — [DONE] Pixel stats: sample instead of decoding all slices

**File:** `src/core/dicom_pixel_stats.py` lines 45-74
**Problem:** `get_series_pixel_value_range()` decodes EVERY pixel array at series-switch time. For 300-slice CT = 300 full decompresses.
**Fix:** Sample at least 25% of slices (evenly spaced), with a floor of 20 slices: `n_sample = max(20, len(datasets) // 4)`. For series with fewer than 20 slices, decode all. Full decode available via a `sample=False` opt-out. This keeps clinical display accuracy high while cutting decode cost ~75% on large series.
**Verify:** `tests/test_mpr_overlay_and_rescale.py` passes.

### P1.7 — [DONE] Defer matplotlib.cm import

**File:** `src/core/fusion_processor.py` line 24
**Problem:** `import matplotlib.cm as cm` at module level adds 200-600ms to first fusion use (and to startup if fusion_processor is imported eagerly).
**Fix:** Move import inside `apply_colormap()`. Cache resolved colormap object in module-level dict.
**Verify:** Startup benchmark improves; fusion output unchanged.

### P1.8 — [DONE] Reduce image display copy count

**File:** `src/gui/image_viewer_view.py` lines 543-576
**Problem:** 4 copies per display update: PIL→bytes, QImage view, qimage.copy(), original_image.copy().
**Fix:** Hold `image_bytes` as instance var (`self._display_bytes_ref`) so Qt can read safely without `qimage.copy()`. Eliminates 1 copy.
**Risk:** Medium — core display path. Needs visual testing + segfault check.
**Verify:** GUI tests pass; inversion toggle works.

**Phase 1 Gate:** Re-run all Phase 0 benchmarks. Each metric must show improvement.

---

## Phase 2 — Medium-Effort Improvements (half-day to 2 days each)

### P2.1 — [DONE] Lazy-load FusionProcessor from main.py

Move `from core.fusion_processor import FusionProcessor` (line ~127) to point of first use. Use `TYPE_CHECKING` guard for annotations.

### P2.2 — [DONE] Projection mode frame cache

Cache AIP/MIP/MinIP slab results keyed by `(projection_type, tuple_of_sop_instance_uids)`. Eliminates full `np.stack` of 40 arrays per scroll. Bound to 10 entries via OrderedDict LRU.

### P2.3 — [DONE] Bound ImageResampler._cache with LRU eviction

Replace unbounded `dict` with `OrderedDict`, max 3 entries. Prevents unbounded RAM growth across fusion pair switches.

### P2.4 — [DONE] Window/level: reduce numpy allocations

Fuse 4 allocations (rescale, clip, normalize, uint8) into 2 using in-place `np.clip(out=)`, `arr -=`, `arr *=` on a float working copy.

### P2.5 — [DONE] Study index covering index for grouped search

Add composite index `idx_grouped_study_cover` on `(study_uid, study_root_path, study_date, patient_name, modality)`. Schema version bumped 2→3 with migration.

### P2.6 — [DONE] MPR: eliminate duplicate SliceStack.from_datasets() call

`src/core/mpr_volume.py` — skip second `SliceStack.from_datasets()` call when no duplicates were removed (reuse `initial_stack`).

### P2.7 — [DONE] Move GC off UI thread during loading

Disable `gc` during loading loop, schedule single deferred `QTimer.singleShot(500, gc.collect)` after loading completes. Keeps `processEvents()` every 50 files for UI responsiveness.

**Phase 2 Gate:** Re-run benchmarks. Cumulative improvement meets targets.

---

## Phase 3 — Architectural Changes (higher risk, own branches)

### P3.1 — [DONE] Move file loading off the UI thread (HIGH RISK)

**The single most impactful architectural change.** Currently `run_load_pipeline()` in `src/core/loading_pipeline.py` runs `loader_fn` → `organizer.merge_batch` → `load_first_slice` ALL serially on the UI thread. Only `processEvents()` keeps the UI alive.

**Problem in detail:**
- `DICOMLoader.load_files()` / `load_directory()` perform I/O-bound `pydicom.dcmread()` on every file
- `rglob('*')` directory scan can take seconds on network drives
- `DICOMOrganizer.merge_batch()` does O(N) sorting and deduplication
- All of this runs on the main thread; progress dialog is modal but UI stutters between files
- Multi-frame pixel pre-loading (files >200MB estimated) adds additional blocking

**Approach — `_LoaderWorker(QThread)` with batched signals:**

1. **New file: `src/core/loader_worker.py`** — a `QThread` subclass:
   ```
   class LoaderWorker(QThread):
       progress = Signal(int, int, str)      # (current, total, filename)
       batch_ready = Signal(list)             # List[Dataset] chunk (every 50 files)
       finished = Signal(list, list)          # (all_datasets, failed_files)
       error = Signal(str)                    # fatal error message
       cancelled = Signal()
   ```
   - Worker runs `loader_fn(progress_callback)` in its `run()` method
   - The progress callback emits `progress` signal (cross-thread-safe via Qt signal queue)
   - No `QApplication.processEvents()` inside worker — not needed off UI thread

2. **Modify `src/core/loading_pipeline.py`** — `run_load_pipeline()`:
   - [ ] Add `async_load: bool = True` parameter (feature flag for rollback)
   - [ ] When `async_load=True`:
     - Create `LoaderWorker` with `loader_fn`
     - Connect `worker.progress` → `loading_manager.update_progress()`
     - Connect `worker.finished` → new `_on_load_finished()` continuation
     - Start worker, return immediately (pipeline becomes async)
   - [ ] When `async_load=False`: keep existing synchronous path unchanged
   - [ ] `_on_load_finished()` slot handles: close dialog, run `merge_batch()`, call `load_first_slice_callback()`, emit status — all on main thread (safe for Qt widgets)
   - [ ] Move `merge_batch()` call to main thread in `_on_load_finished()` (it touches `DICOMOrganizer.studies` which the UI reads)

3. **Modify `src/core/dicom_loader.py`**:
   - [ ] Remove all `QApplication.processEvents()` calls from `load_files()` and `load_directory()` — they're unnecessary off the UI thread and would crash (no QApplication event loop on worker thread)
   - [ ] Keep `gc.disable()` / `gc.enable()` / deferred GC pattern (P2.7)
   - [ ] Cancellation: `self._cancelled` flag is already thread-safe (simple bool read)

4. **Modify `src/core/file_operations_handler.py`**:
   - [ ] `open_files()`, `open_folder()`, `open_recent_file()` — adjust to handle async return (no immediate `(datasets, studies)` result)
   - [ ] Store worker reference to prevent GC: `self._active_worker = worker`
   - [ ] Connect `worker.finished` to a method that updates `app.current_datasets` and `app.current_studies`

5. **UI state during loading:**
   - [ ] Progress dialog stays modal (blocks user file interactions but not rendering)
   - [ ] Cancel button calls `loader.cancel_loading()` which sets `self._cancelled = True`
   - [ ] Main window remains fully interactive (menus, scroll existing images, etc.)

**Files changed:** `loading_pipeline.py`, `dicom_loader.py`, `file_operations_handler.py`, new `loader_worker.py`
**Risk:** HIGH — changes the fundamental loading contract from sync to async. Must keep sync fallback.
**Verify:** Load 200-file folder; UI stays responsive during load; cancel works; partial load works; drag-drop works; recent files work. All existing tests pass.

---

### P3.2 — [DONE] Move VTK data conversion off UI thread (MEDIUM RISK)

**Problem:**
`VolumeRenderer.set_volume()` (volume_renderer.py lines 488-505) does the full sitk→numpy→VTK conversion on the main thread:
1. `sitk.GetArrayFromImage(sitk_image)` — extracts ~300MB numpy array
2. `np.ascontiguousarray(arr, dtype=np.float32)` — ensures contiguous float32 (~300MB)
3. `numpy_to_vtk(flat, deep=True)` — deep copy into VTK array (~300MB)
- Peak: ~900MB on UI thread, blocks for 1-3 seconds

**Note:** `_VolumeBuilderWorker` in `volume_render_dialog.py` already builds the `MprVolume` (SimpleITK image) on a background thread. But `set_volume()` — which does the expensive numpy/VTK conversion — runs on the main thread in `_on_build_finished()`.

**Approach — split `set_volume()` into prep + attach:**

1. **Modify `src/core/volume_renderer.py`**:
   - [ ] Split `set_volume(sitk_image)` into two methods:
     - `prepare_volume_data(sitk_image) -> VolumeData` — pure numpy work, thread-safe:
       ```
       arr = sitk.GetArrayFromImage(sitk_image)
       arr = np.ascontiguousarray(arr, dtype=np.float32)
       return VolumeData(arr, spacing, origin, direction)
       ```
     - `attach_volume(volume_data: VolumeData)` — VTK API calls, main-thread only:
       ```
       vtk_data_array = numpy_to_vtk(volume_data.arr.ravel(), deep=True)
       vtk_image = vtkImageData()
       # ... set dimensions, spacing, origin, scalars
       self._mapper.SetInputData(vtk_image)
       ```
   - [ ] `VolumeData` is a simple dataclass holding the array + spatial metadata
   - [ ] Keep `set_volume()` as a convenience wrapper that calls both sequentially (backward compat)

2. **Modify `src/gui/dialogs/volume_render_dialog.py`**:
   - [ ] Extend `_VolumeBuilderWorker.run()` to also call `VolumeRenderer.prepare_volume_data()` after building MprVolume
   - [ ] Worker signal becomes `finished = Signal(object, object)` — emits `(MprVolume, VolumeData)`
   - [ ] `_on_build_finished(volume, volume_data)` only calls `renderer.attach_volume(volume_data)` — a fast main-thread operation

**Files changed:** `volume_renderer.py`, `volume_render_dialog.py`
**Risk:** MEDIUM — VTK objects must only be created/manipulated on main thread. The split must ensure numpy work is thread-safe and VTK calls stay on main thread.
**Verify:** 3D volume render dialog opens and renders correctly. Rotate/zoom work. Transfer functions apply. No segfaults on close.

---

### P3.3 — [DONE] Smart VTK mapper + slider debounce (LOW-MEDIUM RISK)

**Problem (two parts):**

**(A) CPU-only volume mapper:**
`VolumeRenderer.__init__()` uses `vtkFixedPointVolumeRayCastMapper` (line 449) with `SetSampleDistance(0.5)` (line 451). This is a CPU-only ray caster — no GPU acceleration. Fine sampling (0.5) makes it even slower.

**(B) No slider debouncing:**
`VolumeViewerWidget` connects slider `valueChanged` signals directly to `_render()` (lines 541-561). Each pixel of slider drag triggers a full VTK `Render()` call. With the CPU mapper, this means 10-30 full volume renders per second of dragging — massive CPU waste.

**Approach:**

1. **Smart mapper with fallback** — modify `src/core/volume_renderer.py`:
   - [ ] Try `vtkSmartVolumeMapper` first (auto-selects GPU if available):
     ```python
     try:
         self._mapper = vtk_mod.vtkSmartVolumeMapper()
         self._mapper.SetRequestedRenderModeToDefault()  # auto GPU/CPU
     except AttributeError:
         self._mapper = vtk_mod.vtkFixedPointVolumeRayCastMapper()
     ```
   - [ ] Change `SetSampleDistance(0.5)` → `SetSampleDistance(1.0)` — doubles render speed with minimal visual difference for medical imaging
   - [ ] Add `set_interactive_quality(low: bool)` method that sets sample distance to 2.0 during interaction and 1.0 on release (progressive refinement)

2. **Slider debounce** — modify `src/gui/volume_viewer_widget.py`:
   - [ ] Add `self._render_timer = QTimer(self)` with `setSingleShot(True)`, interval 80ms
   - [ ] Connect `_render_timer.timeout` → `self._render()`
   - [ ] Replace direct `self._render()` calls in `_on_opacity_changed`, `_on_wl_changed`, `_on_threshold_changed` with `self._render_timer.start()`:
     ```python
     def _on_opacity_changed(self, value: int) -> None:
         opacity = value / 100.0
         self._opacity_label.setText(f"{value}%")
         self._renderer.set_global_opacity(opacity)
         self._render_timer.start()  # debounced render
     ```
   - [ ] Keep `_on_preset_changed` as immediate render (user expectation: preset switch = instant visual change)

3. **Progressive refinement on interaction** — modify `src/gui/volume_viewer_widget.py`:
   - [ ] Connect VTK interactor `StartInteractionEvent` → `renderer.set_interactive_quality(True)`
   - [ ] Connect VTK interactor `EndInteractionEvent` → `renderer.set_interactive_quality(False)` + `_render()`
   - [ ] During rotation/zoom, render at coarser sample distance for responsiveness

**Files changed:** `volume_renderer.py`, `volume_viewer_widget.py`
**Risk:** LOW-MEDIUM — `vtkSmartVolumeMapper` may fail on some GPU/driver combos (known issue on Parallels macOS). The fallback to `vtkFixedPointVolumeRayCastMapper` handles this. Debounce is safe.
**Verify:** 3D renders correctly on Windows. Slider adjustments feel smooth. Rotation is responsive. No visual artifacts. Test on Parallels if available.

---

### P3.4 — Dataset eviction / LRU study cache (HIGH RISK) [DONE]

**Problem:**
`DICOMOrganizer.studies` (and by reference `app.current_studies`) holds ALL loaded pydicom Dataset objects forever. Each 300-slice CT study holds ~50-150MB of Dataset objects in memory (metadata + deferred pixel references). Loading 5+ studies pushes RAM past 1GB with no eviction.

**Design decisions (resolved):**

- [x] **Eviction unit:** Per-study.
- [x] **Max entries:** Default 5 studies; memory threshold 3 GB RSS.
- [x] **User notification:** Confirmation dialog listing studies to be evicted (triggered by study limit or memory threshold).
- [x] **Re-load on access:** Not implemented (user can re-open folder). Deferred to future multi-tab work.
- [x] **Pinning:** Not implemented (deferred). Active study is never evicted.
- [x] **Interaction with series navigator:** Evicted studies removed from navigator via existing `_close_study()` path.

**Approach (pending design decisions):**

1. **New class: `src/core/study_cache.py`** — `StudyCache`:
   ```
   class StudyCache:
       def __init__(self, max_studies: int = 5):
           self._studies: OrderedDict[str, Dict[str, List[Dataset]]] = OrderedDict()
           self._source_dirs: Dict[str, str] = {}  # study_uid → source_dir for reload

       def access(self, study_uid: str) -> None:  # moves to end (LRU)
       def evict_lru(self) -> Optional[str]:       # evicts oldest, returns uid
       def add_study(self, study_uid, series_dict, source_dir): ...
       def get_study(self, study_uid) -> Optional[Dict[str, List[Dataset]]]: ...
   ```

2. **Integrate with `DICOMOrganizer`**:
   - [ ] Replace `self.studies: Dict` with `StudyCache`
   - [ ] On `merge_batch()`: add new study to cache; if over limit, evict LRU
   - [ ] On eviction: clear `loaded_file_paths` for evicted study's files
   - [ ] Store `source_dir` per study for potential re-load

3. **Integrate with `FileSeriesLoadingCoordinator`**:
   - [ ] When user navigates to an evicted study: trigger re-load from `source_dir`
   - [ ] Show brief loading indicator (not full progress dialog)

4. **Config integration**:
   - [ ] `ConfigManager.get_max_cached_studies()` — default 5
   - [ ] Settings dialog entry (optional, could defer)

**Files changed:** new `study_cache.py`, `dicom_organizer.py`, `file_series_loading_coordinator.py`, `config_manager.py`
**Risk:** HIGH — touches the core data model that every feature reads from. Must ensure no dangling references to evicted datasets (fusion, MPR, 3D, export, ROI all hold dataset references).
**Verify:** Load 6+ studies; first study evicted; navigate back to it → re-loads. Memory stays bounded. No crashes when evicted study was in use by fusion/MPR/3D.

---

## Phase 3 Sequencing

```
P3.3 (smart mapper + debounce) — LOW-MEDIUM risk, independent, do first
  │
  ├→ P3.2 (VTK data off-thread) — MEDIUM risk, independent of P3.1
  │
  ├→ P3.1 (async loading) — HIGH risk, own branch
  │     └→ feature flag for rollback
  │
  └→ P3.4 (dataset eviction) — HIGH risk, design gate
        └→ depends on P3.1 (re-load path uses async loader)
```

**Recommended order:** P3.3 → P3.2 → P3.1 → P3.4

P3.3 gives the most immediate user-visible 3D improvement with lowest risk. P3.2 is moderate work that removes the last UI-thread data conversion. P3.1 is the big one — most impactful but highest risk. P3.4 depends on P3.1 for the re-load-on-access path and needs design decisions first.

---

## What NOT to Optimize

- **MPR disk cache** (`mpr_cache.py`) — already well-designed (500MB LRU, disk-backed)
- **pydicom deferred loading** (`DEFAULT_DEFER_SIZE = 250MB`) — already correct
- **processEvents() calls** — needed until P3.1 ships (then removed)
- **SimpleITK lazy import pattern** — already correctly deferred
- **Commented-out timing code** in `dicom_loader.py` — harmless, useful for debugging

---

## Sequencing (Full)

```
Phase 0 (instrument) → baselines                              [DONE]
  ├→ P1.7, P1.4, P1.6, P1.3  (pure algorithmic)              [DONE]
  ├→ P1.1 → P1.2              (caching state)                 [DONE]
  ├→ P1.5                     (DB schema touch)               [DONE]
  └→ P1.8                     (display pipeline)              [DONE]
  → Phase 1 gate benchmarks
  ├→ P2.1-P2.7                (independent, parallelized)     [DONE]
  → Phase 2 gate benchmarks
  ├→ P3.3 (smart mapper + debounce) — LOW-MEDIUM risk
  ├→ P3.2 (VTK data off-thread)     — MEDIUM risk
  ├→ P3.1 (async loading)           — HIGH risk, own branch
  └→ P3.4 (dataset eviction)        — HIGH risk, design gate first
```

---

## Success Criteria

| Metric | Target vs Baseline |
|---|---|
| Cold startup to first window | -30% |
| 200-file folder load to display | -40% |
| Fusion scroll (3D path) latency | -60% |
| MPR slice display latency | -30% |
| Peak RAM for 300-slice CT | -25% |
| Study index search round-trip | -70% |
| 3D slider adjustment latency | <100ms (new) |
| UI responsiveness during load | no freezes >200ms (new) |

---

## Critical Files

| File | Phases | Role |
|---|---|---|
| `src/core/image_resampler.py` | P1.1, P1.2, P2.3 | 3D fusion cache + sort cache + LRU |
| `src/core/fusion_processor.py` | P1.3, P1.7 | Blend copies + matplotlib defer |
| `src/core/mpr_controller.py` | P1.4 | Redundant float32 casts |
| `src/core/dicom_pixel_stats.py` | P1.6 | Series pixel range sampling |
| `src/core/study_index/index_service.py` | P1.5 | Schema init skip |
| `src/gui/image_viewer_view.py` | P1.8 | Display copy reduction |
| `src/core/dicom_loader.py` | P2.7, P3.1 | GC scheduling + async loading |
| `src/core/loading_pipeline.py` | P3.1 | Async load orchestration |
| `src/core/loader_worker.py` | P3.1 | New QThread worker |
| `src/core/file_operations_handler.py` | P3.1 | Async load integration |
| `src/core/volume_renderer.py` | P3.2, P3.3 | VTK off-thread + smart mapper |
| `src/gui/volume_viewer_widget.py` | P3.3 | Slider debounce + progressive refinement |
| `src/gui/dialogs/volume_render_dialog.py` | P3.2 | Worker data prep extension |
| `src/core/study_cache.py` | P3.4 | New LRU study cache |
| `src/core/dicom_organizer.py` | P3.4 | Cache integration |
| `src/main.py` | P0.1, P2.1 | Startup timing + lazy imports |
