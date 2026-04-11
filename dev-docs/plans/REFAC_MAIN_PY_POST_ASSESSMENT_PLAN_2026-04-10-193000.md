# Plan: `main.py` post-assessment refactor (phased)

| Field | Value |
|--------|--------|
| **Plan timestamp** | 2026-04-10 19:30:00 (local) |
| **Source assessment** | `dev-docs/refactor-assessments/main-py-refactor-assessment-2026-04-10-183500.md` |
| **Primary target** | `src/main.py` (and small new `src/core/` helpers as listed) |

---

## Goal and success criteria

- **Reduce** `main.py` size (currently approx 3804 lines before refactor) and repeated patterns where the assessment shows **clear, safe** wins.
- **Improve** efficiency (fewer redundant passes) and code quality (narrow exceptions, clearer imports) **without** changing user-visible behavior.
- **Preserve** `DICOMViewerApp` init order and signal-wiring conventions described in `AGENTS.md`.
- **Success**: each completed phase has tests run (or scoped tests where agreed), manual smoke notes where required, and this document’s phase checklists updated (`[x]`).

---

## What we are acting on (chosen from the assessment)

| Assessment item | In this plan? | Rationale |
|-----------------|---------------|-----------|
| **C** — `_close_files` duplicate fusion reset + small loop hygiene | **Yes — Phase 1** | Low risk, immediate efficiency/correctness |
| **exception_hook** bare `except` | **Yes — Phase 1** | Safety/clarity |
| Commented debug prints in W/L preset handler | **Yes — Phase 1** | Hygiene |
| **B** — Subwindow display propagation (merge loops + shared view-toggle helpers) | **Yes — Phase 2** | High readability payoff, low risk if behavior is copied exactly |
| **Inline import** audit (hoist / document cycles) | **Yes — Phase 3** | Reduces noise; must not introduce import cycles |
| Histogram timer duplication | **Yes — Phase 4** | Small consolidation; keep intervals and slots identical |
| **A** — Extract subwindow manager factory | **Yes — Phase 5** | Large line reduction; **byte-stable** move only in first commit |
| **E** — Annotation paste shims / wiring | **Yes — Phase 6 (optional)** | Good line reduction; verify every signal signature |
| **D** — W/L preset body → `ViewStateManager` / handler | **Deferred — backlog** | Medium risk; needs focused tests |
| **F** — Cine façade | **Deferred — backlog** | Lower payoff vs. effort for this cycle |
| **G** — `eventFilter` extraction | **Deferred — backlog** | Easy to break shortcuts; separate hardening pass |

---

## Context and links

- `AGENTS.md` — `__init__` sequence; `_connect_signals` family includes `core/app_signal_wiring.py`.
- `src/core/app_signal_wiring.py` — do not scatter new `connect()` calls outside the wiring module without updating the same rule in `AGENTS.md`.
- Signal targets may remain on `DICOMViewerApp`; new modules should be **pure helpers** or **factories** unless the plan explicitly moves slots.

---

## Phases

### Phase 0 — Preconditions (read-only)

- [ ] Re-read `dev-docs/refactor-assessments/main-py-refactor-assessment-2026-04-10-183500.md` (constraints section).
- [ ] Confirm venv and test entrypoints: `python tests/run_tests.py` or `python -m pytest tests/ -v` per `AGENTS.md`.
- [ ] Optional: capture current `main.py` line count baseline (e.g. `Get-Content src/main.py | Measure-Object -Line`) for before/after comparison.

#### Phase 0 completion (check when Phase 0 is done)

- [ ] Preconditions above are satisfied (or explicitly waived in **Completion notes** with reason).
- [ ] Baseline metric recorded in **Completion notes** (optional).

---

### Phase 1 — Low-risk correctness and hygiene (`main.py`)

**Intent:** Fix redundant work and tighten exception handling without touching init order or signal graphs.

- [x] **`_close_files`**: Remove the **duplicate** call to `_reset_fusion_for_all_subwindows()`; keep **one** call at the semantically correct point (after overlay/scene clearing, consistent with current behavior). Manually verify fusion UI and status after **Close**.
- [x] **`_close_files`**: Where the overlay-clear loop currently re-fetches `subwindows` per index, **hoist** a single `subwindows = self.multi_window_layout.get_all_subwindows()` for that loop scope (or equivalent refactor with identical indexing behavior).
- [x] **`exception_hook`**: Replace bare `except:` around the Qt message box path with `except Exception:` (or narrower), preserving the “print then try dialog” flow. Confirm `KeyboardInterrupt` still exits as expected.
- [x] **`_on_window_level_preset_selected`**: Remove commented `# print(...)` debug lines.

#### Phase 1 testing

- [x] Run full test suite in project venv.
- [ ] Manual smoke: open study → enable fusion if available → **Close** → confirm fusion disabled and no stale status; open again.
- [x] Quick check: trigger an intentional error path if feasible, or code-review `exception_hook` only.

#### Phase 1 completion (check when Phase 1 is done)

- [x] All Phase 1 tasks above are `[x]` or deferred with note under **Completion notes**.
- [x] Tests run recorded (command + pass/fail).
- [ ] Manual smoke notes recorded for fusion-after-close.

---

### Phase 2 — Subwindow display propagation helper

**Intent:** One place for “apply config to every `image_viewer`” and shared patterns for View-menu toggles, matching current behavior exactly.

**Suggested module (name adjustable):** `src/core/subwindow_image_viewer_sync.py`  
**Suggested API shape (illustrative):**

- Functions or a small class taking `app: DICOMViewerApp` (or narrow protocols) and implementing:
  - [x] `apply_initial_viewer_state_from_config(app)` — replaces the **six** sequential loops in `_post_init_subwindows_and_handlers` with **one** pass over subwindows (read config once per call, set all properties on each viewer that the loops currently set). *(Implemented as `apply_initial_image_viewer_display_state`.)*
  - [x] Optional helpers used by `_on_smooth_when_zoomed_toggled`, `_on_scale_markers_toggled`, `_on_direction_labels_toggled`, `_on_scale_markers_color_changed`, `_on_direction_labels_color_changed` so each slot remains thin: persist config → call helper → sync `main_window` check state.

**Rules:**

- [x] Do **not** change the **order** of side effects unless a test proves the old order was accidental; default is **identical** ordering of property sets per viewer as today.
- [x] Keep `DICOMViewerApp` methods as the **Qt slots** unless `app_signal_wiring` is updated deliberately (prefer keeping slots on the app).

#### Phase 2 testing

- [x] Full test suite.
- [ ] Manual: 2×2 layout, toggle smooth / scale markers / direction labels / colors from View menu and image context menu; privacy + slice sync still apply on startup.

#### Phase 2 completion (check when Phase 2 is done)

- [x] New helper module exists and is imported from `main.py` (or wired via a single internal method).
- [x] `_post_init_subwindows_and_handlers` uses the merged initial pass.
- [x] View-toggle handlers use shared helpers or clearly document why not.
- [x] Automated tests completed; manual smoke noted in **Completion notes** (pending locally).

---

### Phase 3 — Inline import audit (`main.py` + touched modules)

**Intent:** Hoist imports to module top where **no circular import**; document one-line **why** when deferral is required.

- [x] Inventory every function-level `import` in `main.py` (list in **Completion notes** or inline comments).
- [x] For symbols **already** imported at module top (e.g. `QKeyEvent`, `Qt`, `QTimer` where applicable), **remove** redundant inner imports.
- [x] For imports that exist to break cycles (e.g. lazy `MprController`, `DisclaimerDialog`), add a **short comment** at the import site: `# deferred: breaks cycle with …` (accurate reason). *(Hoisted `MprController`, `DisclaimerDialog`, annotation tools/coordinators, `TagExportUnionWorker`, `register_fonts_with_qt`, `traceback`; no cycle comments needed.)*
- [ ] Run `pyright` / project type check on edited files if that is part of your usual workflow (optional but recommended).

#### Phase 3 testing

- [x] Full test suite.
- [ ] Smoke: cold start `python src/main.py` (or project launcher) — no `ImportError` on startup.

#### Phase 3 completion (check when Phase 3 is done)

- [x] Audit table or comment summary completed.
- [x] No new import cycles (if any doubt, document in **Completion notes**).

---

### Phase 4 — Histogram throttle helper (small)

**Intent:** Deduplicate lazy `QTimer` creation for histogram W/L vs full refresh **without** changing intervals (100 ms / 300 ms) or connected slots.

- [x] Extract a tiny private helper or nested pattern on `DICOMViewerApp` (or a small collaborator owned by the app) that ensures single-shot timers are created once and restarted the same way `_schedule_histogram_wl_only` and `_update_histogram_for_focused_subwindow` do today. *(Implemented as `_restart_single_shot_timer`.)*
- [x] Preserve public behavior of `dialog_coordinator.update_histogram_*` calls.

#### Phase 4 testing

- [x] Full test suite (or tests touching histogram if any).
- [ ] Manual: open histogram, drag W/L, change slice — UI stays responsive, no duplicate updates/regressions.

#### Phase 4 completion (check when Phase 4 is done)

- [x] Timer behavior documented (intervals unchanged).
- [x] Tests + any manual notes recorded.

---

### Phase 5 — Extract subwindow manager factory (high payoff)

**Intent:** Move `_build_managers_for_subwindow` to e.g. `src/core/subwindow_manager_factory.py` as `build_managers_for_subwindow(app, idx, subwindow) -> Dict[str, Any]`.

- [ ] **First commit / step: byte-stable move** — same logic, same lambdas, same closure defaults (`i=idx`); only location and `self` → `app` (or equivalent) renaming.
- [ ] Update `main.py` to call the factory; keep `_initialize_subwindow_managers` / `_create_managers_for_subwindow` behavior identical.
- [ ] Watch for **circular imports**: factory module must not import `main` at runtime in a way that creates a cycle; prefer typing-only imports or local imports only if unavoidable (document).
- [ ] Update `AGENTS.md` **only if** the module structure change is user-facing for agents (optional one-line under `core/` tree).

#### Phase 5 testing

- [ ] Full test suite.
- [ ] Manual: 1×1 ↔ 2×2, new subwindow manager creation, ROI/measurement/fusion in multiple panes, MPR path if available.

#### Phase 5 completion (check when Phase 5 is done)

- [ ] `main.py` line count reduced materially; factory module listed in **Completion notes**.
- [ ] No intentional logic changes in the first merge (refactors follow in separate PRs if needed).

---

### Phase 6 — Annotation clipboard surface (optional)

**Intent:** Reduce ~150+ lines of thin `_paste_*` / `_get_selected_*` wrappers.

- [ ] Trace each caller (signals in `app_signal_wiring` or elsewhere); compare signatures to `AnnotationPasteHandler` methods.
- [ ] Either: (a) wire `AnnotationPasteHandler` methods directly in `app_signal_wiring`, or (b) keep one-liner delegates with **minimal** docstrings.

#### Phase 6 testing

- [ ] Run full tests + manual copy/paste ROI and annotations across slices/windows.

#### Phase 6 completion (check when Phase 6 is done or skipped)

- [ ] Option (a) or (b) completed, or phase **skipped** with reason in **Completion notes**.

---

## Backlog (not in active phases)

Track separately; do **not** block the above phases.

- [ ] **D** — Move `_on_window_level_preset_selected` logic to `ViewStateManager` or `WindowLevelPresetHandler` + add/extend automated tests for rescale/raw toggles.
- [ ] **F** — `CineAppFacade` (group cine slots for readability).
- [ ] **G** — Move `eventFilter` / `_is_widget_allowed_for_layout_shortcuts` to a dedicated helper with keyboard shortcut regression checklist.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Subtle multi-window regressions | Phase-by-phase merges; full tests + layout smoke after Phases 2, 5, 6 |
| Import cycles after factory or helpers | Factory imports typed dependencies from existing modules, not `main` at runtime; use `TYPE_CHECKING` where appropriate |
| Fusion state after close | Explicit manual check after Phase 1 |
| Histogram throttle regressions | Keep timer ms values and single-shot semantics identical in Phase 4 |

---

## Modularity and file-size guardrails

- New files should stay **under ~500 lines**; split factory vs. display sync if needed.
- Avoid growing `main.py` again with duplicate helpers — prefer `core/` pure functions or small classes.

---

## Testing strategy

- Default: **full** `python tests/run_tests.py` or `python -m pytest tests/ -v` after **each** phase merge.
- Phases 1–2: add manual smoke bullets from this plan (fusion close, view toggles).
- Phase 5: extended multi-pane smoke.

---

## Completion notes (fill in during implementation)

_Phase completions, test commands, line counts, PR links, and any deferred items go here._

- Phase 0: Optional baseline skipped for this pass.
- Phase 1–4 (2026-04-10): Implemented in repo. Backup: `backups/main_pre_REFAC_MAIN_PY_20260410.py`. Tests: `python -m pytest tests/ -q` — **370 passed** (venv). Manual smoke (fusion close, 2×2 view toggles, histogram, cold start): **pending** — run locally before release.
- Phase 3 inventory: remaining function-level imports in `main.py` after pass — none (module uses top-level `traceback`; `exception_hook` / `main` use `QApplication` / `QMessageBox` from existing QtWidgets import).
- Phase 5–6: **Not started** (factory extract; optional annotation shims).

---

## Ready for handoff

This plan is **ready for orchestrator/coder assignment**: execute phases **in order** (0 → 1 → …); do **not** skip Phase 1 verification before starting Phase 5. Optional Phase 6 may run after Phase 5 or be postponed without blocking Phases 1–5.

---

*End of plan.*
