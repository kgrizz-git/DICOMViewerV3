# Post-Load First Paint Diagnostics Inventory (R2)

**Date:** 2026-07-12
**Task:** (R2) Inventory existing diagnostics relevant to this work, especially `DEBUG_LOADING`, `DEBUG_NAV`, `PERF_LOG`, and any existing timing helpers; recommend whether S1 can reuse them or needs a new `DEBUG_LOADING_FIRST_PAINT` flag, but leave the decision to the coder in T2.

> Research-only note. No product code, tests, or final implementation decision here. The T2 decision belongs to the coder.

## Existing diagnostics inventory

### Debug print flags (`src/utils/debug_flags.py`)

All `DEBUG_*` flags are boolean, default `False`, and gate `print()` tracing. CI (`.github/workflows/security-checks.yml`, debug-flags-check) fails if any is left `True`.

| Flag | Default | Affects (per file comment) | Relevance to first paint |
|------|---------|-----------------------------|---------------------------|
| `DEBUG_LOADING` | `False` | `file_series_loading_coordinator` | **High** — already lives in the primary handler (`handle_load_first_slice` / `handle_additive_load`). Currently only used once, gating stale-data-clearing trace at `src/gui/file_series_loading_coordinator.py:270`. |
| `DEBUG_NAV` | `False` | `series_navigator`, `image_viewer`, `file_series_loading_coordinator` | **Medium** — spans navigator + coordinator, but current uses are keypress/navigation-request tracing (`series_navigator.py:1114,1122`), not rebuild/thumbnail timing. |
| `DEBUG_SERIES` | `False` | `file_series_loading_coordinator`, `slice_display_manager` | **Medium** — generic series load/nav/state tracing; used in coordinator (`:271,330,334`) and display manager (`slice_display_manager.py:1229-1289`). Covers both display + coordinator, but semantics are "series/state", not "timing". |
| `DEBUG_WL` | `False` | `slice_display_manager` | Low — W/L transition tracing only. |
| `PERF_LOG` | env `DICOM_PERF_LOG=1` | `main.py` (startup timing), `utils/perf_timer.py` | **High** — the only *timing* diagnostic. See below. |

Other `DEBUG_*` flags (LAYOUT, CROSSHAIR, MAGNIFIER, MPR, MEASUREMENT_*, PROJECTION, OFFSET, SPATIAL_ALIGNMENT, DIAG, WIDGET_PAN, RESIZE, ANNOTATION, AGENT_LOG, FONT_VARIANT, PATIENT_COORDS, YBR, PYLINAC_QA, VOLUME_3D) are unrelated to post-load first paint.

### Timing helper: `PERF_LOG` + `perf_timer`

- `PERF_LOG` (`src/utils/debug_flags.py:131`) is unique among the flags: it is **not** a hardcoded `False` but reads env `DICOM_PERF_LOG=1`. This means it is CI-safe by default (stays `False` in the repo) and can be turned on at runtime without editing source — a good fit for opt-in load timing.
- `perf_timer(label)` (`src/utils/perf_timer.py`) is a zero-overhead context manager that logs `"[PERF] <label>: <ms>ms"` at INFO on the `"perf"` logger, but only when `PERF_LOG` is true. Otherwise it yields immediately with no `time.perf_counter()` call.
- **Current usage (pre-S1 snapshot):** `perf_timer` the context manager was only exercised by `tests/test_perf_timer.py`; no `src/` module wrapped a block with it yet. S1 later added first-paint instrumentation using this helper; see the archived plan completion notes.
- Tooling: `scripts/benchmark_startup.py` launches the app with `DICOM_PERF_LOG=1` and parses `[PERF]` lines — a precedent for automated timing capture that T1/T6/T12 could mirror.

### Deferred-work markers already in the hot path (from R1)

Not diagnostics, but relevant context for where instrumentation should sit — these are the only already-async points in `handle_load_first_slice`:

- `QTimer.singleShot(100, store_initial_view_state)` (`:380`)
- `QTimer.singleShot(50, fit_to_view)` (`:394`)
- `QTimer.singleShot(100, slice_location_line_coordinator.refresh_all)` (`:398`)
- `QTimer.singleShot(0, _process_next_thumbnail)` (`series_navigator.py:630`) — thumbnails are already chunked.

## Assessment: reuse vs. new flag

Facts for the coder to weigh in T2 (this note does not decide):

**Arguments for reusing `PERF_LOG` / `perf_timer`:**
- It is the only existing *timing* mechanism; the milestone list in R1 (loader completion → `display_slice` → `update_series_list` → `_refresh_series_navigator_state` → event-loop return) maps naturally onto `perf_timer("...")` blocks or `_logger.info("[PERF] ...")` lines.
- Env-gated, so it is CI-safe by default and needs no debug-flags-check exception; can be toggled at runtime without a source edit.
- `scripts/benchmark_startup.py` already parses `[PERF]` output, so T1/T6/T12 capture tooling can be reused/extended.
- `perf_timer` is truly zero-overhead when disabled.

**Arguments for a new `DEBUG_LOADING_FIRST_PAINT` flag:**
- `PERF_LOG` currently connotes *startup* timing; overloading it with per-load first-paint spam may be noisy when someone only wants startup numbers. A dedicated flag isolates first-paint tracing.
- A print-style `DEBUG_*` flag is consistent with the surrounding coordinator/navigator tracing (`DEBUG_LOADING`, `DEBUG_NAV`, `DEBUG_SERIES`) and can emit human-readable, per-milestone lines with timestamps like the existing `DEBUG_NAV` prints.
- Instrumentation across `file_series_loading_coordinator`, `slice_display_manager`, and `series_navigator` spans three modules; a single purpose-named flag documents intent better than piggybacking on `DEBUG_LOADING` (coordinator-only) or `DEBUG_SERIES` (series/state semantics).

**Cost of a new flag:** must default `False`, be documented in `debug_flags.py`, and be reverted before commit (debug-flags-check). A new flag would need an S1 addition; `PERF_LOG` needs none.

### Non-binding recommendation

A reasonable path (coder decides in T2): use `PERF_LOG` + `perf_timer` for the **numeric milestone timings** (reuses env-gating, logger, and `benchmark_startup.py` parsing, no new CI surface), and only add `DEBUG_LOADING_FIRST_PAINT` if the coder wants verbose per-milestone print tracing with timestamps beyond what `[PERF]` lines give. Either way, keep all flags default-`False`/env-off before commit. If a new flag is added, document affected modules (coordinator, slice display manager, series navigator) in `debug_flags.py`.

## Key anchors

| Item | File | Line(s) |
|------|------|---------|
| `DEBUG_LOADING` definition | `src/utils/debug_flags.py` | 31 |
| `DEBUG_NAV` definition | `src/utils/debug_flags.py` | 39 |
| `DEBUG_SERIES` definition | `src/utils/debug_flags.py` | 111 |
| `PERF_LOG` definition (env-gated) | `src/utils/debug_flags.py` | 126-131 |
| `perf_timer` context manager | `src/utils/perf_timer.py` | 12-21 |
| `PERF_LOG` startup line | `src/main.py` | 583-587 |
| `DEBUG_LOADING` use (coordinator) | `src/gui/file_series_loading_coordinator.py` | 88, 270 |
| `DEBUG_SERIES` use (coordinator) | `src/gui/file_series_loading_coordinator.py` | 271, 330, 334 |
| `DEBUG_NAV` use (navigator) | `src/gui/series_navigator.py` | 55, 1114, 1122 |
| Benchmark harness precedent | `scripts/benchmark_startup.py` | 1, 20 |
| `perf_timer` tests | `tests/test_perf_timer.py` | — |
