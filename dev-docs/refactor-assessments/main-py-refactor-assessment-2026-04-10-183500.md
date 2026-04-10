# Refactor assessment: `src/main.py`

| Field | Value |
|--------|--------|
| **Assessment timestamp** | 2026-04-10 18:35:00 (local) |
| **Scope** | `src/main.py` only |
| **Goal** | Reduce size and improve quality/efficiency without changing behavior or weakening execution safety |
| **Code changes** | None (assessment only) |

---

## Executive summary

`main.py` is the composition root for DICOM Viewer V3: **`DICOMViewerApp`** (~3,770 lines of class body) plus **`exception_hook`**, **`main()`**, and `if __name__ == "__main__"`. The file is already partially modularized (per-subwindow factory, signal wiring module, QA/export/projection façades, lifecycle and file coordinators). The largest wins now are **(1)** extracting repeated “iterate all subwindows / propagate view state” patterns, **(2)** moving the per-subwindow manager graph out of the class body, **(3)** collapsing thin annotation-paste shims or wiring the handler directly, **(4)** hoisting deferred/inline imports where cycles allow, and **(5)** small correctness/efficiency cleanups (e.g. duplicate fusion reset). None of these require changing user-visible behavior if done with regression tests and preserved init order.

---

## Metrics (current tree)

| Metric | Value |
|--------|--------|
| **Physical lines** | 3,803 |
| **`DICOMViewerApp` instance methods** | 100 (`def` at standard class indent) |
| **Module-level callables** | `exception_hook`, `main` |
| **Type alias** | `StudiesNestedDict` |
| **Heavy import surface** | ~80+ top-level imports from `core/`, `gui/`, `tools/`, `metadata/`, `roi/`, `qa/` |

---

## What improved since earlier `main.py` assessments

The March 2026 note in `main-py-refactor-assessment-2026-03-04.md` called out duplicated per-subwindow manager construction. The current code **already centralizes** creation in **`_build_managers_for_subwindow`** (used from `_initialize_subwindow_managers` / `_create_managers_for_subwindow`), which removes a major maintenance risk.

Signal connection bulk is **already in** `core/app_signal_wiring.py` (`wire_all_signals`); `DICOMViewerApp._connect_signals` is a one-line delegate. That matches `AGENTS.md` (“signal connections live in the `_connect_signals` family” — the family now spans `main` + `app_signal_wiring`).

QA, export path/prompt flows, and much pylinac UI are **delegated** through **`QAAppFacade`**, **`ExportAppFacade`**, and related modules, which is the right direction for shrinking the orchestrator.

---

## Architectural strengths (keep as-is conceptually)

1. **Explicit five-phase `__init__`** documented in the class docstring and `AGENTS.md`; many subtle bugs come from reordering this — any extract must preserve it.
2. **Controllers and coordinators** already own domain behavior; `main` mostly wires callbacks and holds shared Qt widgets.
3. **Focused-subwindow indirection** via `SubwindowLifecycleController` and `subwindow_managers` keeps multi-pane logic centralized.

---

## Line-count and complexity hotspots

Approximate line spans (for navigation; boundaries are indicative):

| Region | Approx. lines | Role |
|--------|----------------|------|
| Imports + docstring | ~1–134 | Large import graph; drives cold start and coupling |
| `__init__` + `_init_*` | ~169–523 | Ordered bootstrap |
| `_post_init_subwindows_and_handlers` | ~347–487 | UI assembly, managers, MPR, initial viewer propagation, facades, signals |
| `_build_managers_for_subwindow` | ~524–699 | Graph of per-pane managers + lambdas |
| `_initialize_handlers` | ~878–1037 | Coordinator/handler construction |
| `_clear_data` / `_close_files` / close helpers | ~1097–1494 | File lifecycle, memory, UI reset |
| Layout / focus / window-slot map | ~1692–1902 | Qt UX glue |
| View toggles (sync, lines, smoothing, scale, direction, instances) | ~2162–2306 | Similar loops over subwindows |
| QA/export façade delegations | ~2355–2497 | Mostly one-liners (good) but verbose |
| Settings / overlay / annotation reactions | ~2499–2648 | Overlap with `_on_settings_applied` |
| Coordinator “handle_*” slots | ~2649–2856 | Thin — many lines, low cyclomatic complexity |
| Histogram throttling | ~2857–2891 | Timer setup duplicated in spirit |
| W/L preset selection | ~2999–3048 | Domain logic still on app |
| `_on_slice_changed` | ~3128–3215 | Multi-branch (MPR vs stack); high coupling |
| Cine block | ~3230–3397 | Could group under a small façade |
| Annotation clipboard shims | ~3466–3645 | Repeated docstrings + delegate |
| `eventFilter` + layout shortcut guard | ~3647–3732 | Mixed with inline imports |
| `run` + module entry | ~3734–3803 | Disclaimer, window show, exception hook |

---

## Code quality findings

### 1. Duplicate work in `_close_files`

`_reset_fusion_for_all_subwindows()` is invoked **twice** in `_close_files` (currently around lines 1168 and 1190). The routine clears fusion caches and UI state; double invocation is **redundant work** on close (extra iteration and cache clears) with no user benefit. **Recommendation:** keep a **single** call in the intended place (after overlay/scene clearing or immediately before clearing `subwindow_data`, depending on desired ordering) and verify fusion widget state still resets correctly.

### 2. Many inline imports

Several methods use inner `import` (e.g. `MprController`, annotation tools/coordinators inside `_build_managers_for_subwindow`, `TagExportUnionWorker`, `QPoint`/`QCursor` for window-slot popup, `QPixmap`/`Qt` in `_get_thumbnail_for_view`, `QKeyEvent`/`QApplication` in `eventFilter`, `DisclaimerDialog` in `run`, `ImageViewer` in `_is_widget_allowed_for_layout_shortcuts`). Some may exist to **avoid import cycles** or **defer heavy Qt** — that is defensible — but others duplicate symbols already imported at module top (e.g. `QKeyEvent`, `Qt`, `QTimer`). **Recommendation:** audit each: move to top level when **no cycle**; if cycles remain, document **why** next to the import (one line) so future edits do not “optimize” them blindly.

### 3. Broad `except` in `exception_hook`

`exception_hook` uses `except:` around the Qt message box path. **Recommendation:** narrow to `Exception` (or log and re-raise as appropriate) so `KeyboardInterrupt` / `SystemExit` are not swallowed unexpectedly.

### 4. Commented debug prints

`_on_window_level_preset_selected` retains commented `# print(...)` traces. Low risk; removing them slightly improves signal-to-noise.

### 5. Repeated “for each subwindow image viewer” loops

`_post_init_subwindows_and_handlers` applies privacy, slice sync, smoothing, scale markers, direction labels, and colors in **six** sequential loops over `get_all_subwindows()`. Behavior is correct; **efficiency and readability** improve if merged into **one** pass that reads config once and calls a small private helper (e.g. `_apply_initial_image_viewer_display_state(subwindow)`).

View-menu handlers (`_on_smooth_when_zoomed_toggled`, `_on_scale_markers_toggled`, `_on_direction_labels_toggled`, color changers) share the same skeleton: **persist → iterate viewers → sync menu check state**. A shared helper reduces copy-paste errors when a new toggle is added.

---

## Efficiency notes (micro — but real at scale)

- **`get_all_subwindows()`** is called repeatedly in hot UI paths. Batching updates (one loop, multiple property sets) reduces Python overhead and keeps menu/viewer state in sync with fewer passes.
- **`_close_files`** inner loop over overlays re-fetches `subwindows` per index; could fetch once per method scope.
- **Histogram timers:** `_schedule_histogram_wl_only` and `_update_histogram_for_focused_subwindow` duplicate lazy `QTimer` creation patterns; consolidating does not change behavior if intervals and slots stay identical.

---

## Refactoring opportunities (prioritized for safety vs. payoff)

### A. High payoff / medium risk — extract subwindow manager factory

**Idea:** Move `_build_managers_for_subwindow` to e.g. `core/subwindow_manager_factory.py` as a function `build_managers(app: DICOMViewerApp, idx: int, subwindow: SubWindowContainer) -> Dict[str, Any]`, keeping **identical** constructor arguments and lambda closures.

**Why:** Drops ~170+ lines from `main.py` and isolates the highest-coupling “wiring” graph.

**Safety:** High regression risk if any callback closure or `self` capture changes. Mitigate with **byte-stable** move (no logic edits in the first commit) + full test run + manual multi-layout smoke.

### B. High payoff / lower risk — `SubwindowDisplayPropagator` (name illustrative)

**Idea:** One module or small class with methods: `apply_config_to_all_image_viewers(app)`, `set_smooth_all(enabled)`, `set_scale_markers_all(enabled)`, etc., used from `_post_init_*` and View handlers.

**Why:** Removes dozens of repeated loops; single place for “all panes” behavior.

**Safety:** Low if each method is a straight extract of existing loops.

### C. Medium payoff / low risk — merge `_close_files` cleanup

**Idea:** Remove duplicate `_reset_fusion_for_all_subwindows`, hoist `subwindows = ...` once where it helps, keep ordering comments explicit.

**Safety:** Low; treat as a bugfix-style change with a quick fusion UI check after close.

### D. Medium payoff / medium risk — window-level preset handler

**Idea:** Move body of `_on_window_level_preset_selected` to `ViewStateManager` or a tiny `WindowLevelPresetHandler` that receives `dicom_processor`, `window_level_controls`, `main_window`, `image_viewer`, `view_state_manager`.

**Why:** `main` should not own rescale/raw conversion rules.

**Safety:** Medium — W/L and rescale flags are user-sensitive; needs tests around preset + rescale toggle.

### E. Medium payoff / low risk — annotation paste surface

**Idea:** Either shrink docstrings on `_paste_*` / `_get_selected_*` to one line, or register `AnnotationPasteHandler` methods directly in signal wiring (if signatures match), deleting ~150–200 lines of shims.

**Safety:** Low if signatures are unchanged.

### F. Lower priority — cine façade

**Idea:** `CineAppFacade` holding `_on_cine_*` and `_update_cine_player_context` to group ~200 lines.

**Why:** Readability; modest line reduction in `main.py`.

**Safety:** Low–medium (signal names must stay wired the same).

### G. `eventFilter` and keyboard routing

**Idea:** Move `eventFilter` + `_is_widget_allowed_for_layout_shortcuts` to `KeyboardEventHandler` or a dedicated `MainWindowEventFilter` owned by the app.

**Why:** `main.py` focuses on lifecycle; filter logic is cohesive elsewhere.

**Safety:** Medium — shortcut behavior is easy to break; needs targeted manual tests.

---

## Constraints and non-goals

- **Do not** reorder `_init_core_managers` → `_post_init_subwindows_and_handlers` without rereading `AGENTS.md` and the class docstring; tests may not cover all Qt init races.
- **`from main import DICOMViewerApp`** appears in `app_signal_wiring` under `TYPE_CHECKING` and possibly elsewhere — any rename or split of `main.py` must update those imports and watch for **circular imports**.
- **Behavioral parity** is mandatory: multi-window focus, slice sync, MPR, fusion reset, tag export union generation, and quit hooks are all high-risk touch points.

---

## Suggested verification (after any refactor)

1. `python tests/run_tests.py` or `python -m pytest tests/ -v` with project venv activated (`AGENTS.md`).
2. Manual smoke: open folder, 2×2 layout, swap views, close study/series, fusion on/off, ACR QA dialog open/cancel, slice sync groups, MPR toggle if applicable, quit.
3. If touching close path: confirm **single** fusion reset still clears widget status and does not leave timers running.

---

## References in-repo

- `AGENTS.md` — `DICOMViewerApp.__init__` order and `_connect_signals` convention.
- `dev-docs/refactor-assessments/main-py-refactor-assessment-2026-03-04.md` — earlier opportunities (partially addressed).
- `src/core/app_signal_wiring.py` — current signal wiring extraction.

---

*End of assessment.*
