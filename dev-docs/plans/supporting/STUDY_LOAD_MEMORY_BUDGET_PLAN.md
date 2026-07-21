# Study Load Memory Budget (fraction of RAM) — Plan

**Status:** In progress (2026-07-21)
**Priority:** P1
**Branch:** `feat/study-load-memory-budget`

Replace the fixed **`max_studies=5`** primary cap on loaded studies with a
**memory budget = configurable fraction of total system RAM**, measured against
the estimated in-memory footprint of loaded studies. A high study-count cap
stays only as a safety net.

## Current behavior (baseline)
- `main.py:381`: `self.study_cache = StudyCache(max_studies=5)`.
- `core/study_cache.py::StudyCache`: has `max_studies` (5) **and** `memory_threshold_mb` (3000 RSS). Eviction candidates are chosen by **count only** (`get_eviction_candidates`). It also has `estimate_study_size_mb()` (currently unused for eviction) and `get_process_memory_mb()` (RSS).
- `gui/file_series_loading_coordinator.py:452`: `needs_eviction = len(current_studies) > max_studies or would_exceed_memory()`; on eviction it shows `show_eviction_confirmation(...)` and evicts the count-based candidates (never the active study); cancel undoes the just-loaded studies.

## Design
- **Primary limit:** `budget_mb = fraction × total_system_ram_mb`, clamped to `[floor_mb, ∞)`. Defaults: **fraction 0.40**, **floor 1024 MB**. If total RAM can't be determined, fall back to the existing absolute `memory_threshold_mb` so behavior degrades gracefully.
- **Measured quantity:** estimated in-memory footprint = `sum(estimate_study_size_mb(uid) for uid in loaded studies)`. Also keep the RSS check (`would_exceed_memory(budget_mb)`) as a hard secondary trigger.
- **Safety-net count cap:** keep `max_studies` but raise the default to **20** — it only guards against pathological many-tiny-studies cases; the budget is the real limit.
- **Eviction:** size-aware — evict LRU oldest-first until the estimated footprint is at/below the budget (leave a little headroom), never evicting the active study; fall back to count-based candidates if size data is missing.

## Tasks

### 1 — Estimator fix + RAM detection (`core/study_cache.py`) (commit 1)
- [ ] **Fix `estimate_study_size_mb`**: for cached NumPy arrays use `array.nbytes` (the current `sys.getsizeof(cached)` returns only object overhead, badly undercounting decompressed pixels). Keep the `PixelData` byte-length term as a fallback when no cached array is present (avoid double-counting: prefer `nbytes` when the cached array exists, else the raw element length). Guard for objects without `.nbytes`.
- [ ] Add `get_total_system_memory_mb() -> float` (0.0 if unknown), cross-platform in the file's existing ctypes/`os` style:
  - Windows: `GlobalMemoryStatusEx` (MEMORYSTATUSEX.ullTotalPhys) via ctypes.
  - Linux/macOS: `os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')`; on macOS fall back to `sysctl -n hw.memsize` (subprocess) if `SC_PHYS_PAGES` is missing.
  - No new dependencies (no psutil).
- [ ] Add helpers on `StudyCache`: store a `memory_fraction` and `memory_floor_mb`; `get_memory_budget_mb()` = `clamp(fraction × total_ram, floor, ∞)` with the RSS-threshold fallback; `estimate_total_loaded_mb(studies_dict)`.
- [ ] **Tests** (`tests/test_study_cache*.py` — extend or add): `nbytes` estimate reflects a real array's size; total-RAM detection returns > 0 on this platform (or 0 handled); budget clamps to floor; budget falls back when RAM unknown.

### 2 — Size-aware eviction (`core/study_cache.py`) (commit 2, may fold into 1)
- [ ] `get_eviction_candidates_by_size(studies_dict, budget_mb, active_study_uid) -> list[str]`: walk LRU oldest-first, accumulate `estimate_study_size_mb`, collect until `estimated_total − freed ≤ budget` (with a small headroom factor); never include the active study; fall back to the existing count-based method when sizes are all zero/unavailable.
- [ ] **Tests**: given a fake `studies_dict` with known sizes, evicts the right LRU set to get under budget; never evicts active; respects the count safety cap; no-op when already under budget.

### 3 — Config + construction (commit 3)
- [ ] `utils/config/…`: add `study_load_memory_fraction` (float, default 0.40) and `study_load_max_studies_cap` (int, default 20) with getters/setters (follow an existing config mixin pattern). Validate ranges (fraction in e.g. [0.1, 0.9]).
- [ ] `main.py`: construct `StudyCache(max_studies=<cap>, memory_fraction=<fraction>, memory_floor_mb=1024)` from config instead of the literal `max_studies=5`.
- [ ] **Tests**: config round-trips and clamps out-of-range values.

### 4 — Coordinator wiring (`gui/file_series_loading_coordinator.py`) (commit 4)
- [ ] Replace the `needs_eviction` condition with: `estimate_total_loaded_mb(...) > budget` **or** `would_exceed_memory(budget)` **or** `len(current_studies) > cap`. Use `get_eviction_candidates_by_size(...)` for candidates. Update the reason string ("memory budget" vs "study count cap"). Keep the existing confirmation dialog and cancel/undo path.
- [ ] **Tests**: with a fake app/study_cache, a load that exceeds the budget produces size-based eviction candidates and the confirmation path; under budget → no eviction.

### 5 — Settings UI (optional within this PR) (commit 5)
- [ ] If a natural home exists (e.g. `gui/privacy_storage_settings.py` or a memory/performance settings panel), expose the fraction and the cap with a short explanation and the computed budget preview. Otherwise config-only; note it in the PR and add a TO_DO follow-up.

## Checkpoints
Run after each commit: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/test_study_cache*.py tests/gui -q` (+ any new files); `ruff check`; `scripts/check_repo_harness.py`. Full suite (`python -m pytest -q`) before the PR.

## Conventions
- Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` (author email already GitHub noreply — do not change git config).
- Do not push; the coordinator pushes + opens the PR.
