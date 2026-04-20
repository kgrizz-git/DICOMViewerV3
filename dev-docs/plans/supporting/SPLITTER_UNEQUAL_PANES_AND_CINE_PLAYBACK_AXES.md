# Unequal multi-pane splitters and cine playback axes

**Scope:** Two related UX items from [`TO_DO.md`](TO_DO.md):

1. Draggable **window dividers** for **unequal** multi-view pane sizes (multi-window image grid).
2. **Cine** controls that clearly separate **frames**, **instances**, and **slices**, with optional playback modes.

**Related code (starting points):**

| Area | Primary modules |
|------|-----------------|
| Multi-view grid | [`src/gui/multi_window_layout.py`](../src/gui/multi_window_layout.py) — `QGridLayout`, `set_layout`, `SubWindowContainer` |
| Main chrome splitters | [`src/gui/main_window.py`](../src/gui/main_window.py) — three-way `QSplitter`, `splitter_sizes` in config |
| Cine orchestration | [`src/core/cine_app_facade.py`](../src/core/cine_app_facade.py), [`src/gui/cine_player.py`](../src/gui/cine_player.py) |
| Slice vs frame grouping | [`src/core/slice_grouping.py`](../src/core/slice_grouping.py) |
| Multi-frame background | [`dev-docs/info/MULTI_FRAME_DICOM_RESEARCH.md`](info/MULTI_FRAME_DICOM_RESEARCH.md), completed plan [`dev-docs/plans/completed/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md`](plans/completed/MULTI_FRAME_INSTANCE_NAVIGATION_PLAN.md) |

---

## 1. Unequal divisions between image panes

### Current behavior

- The **main window** already uses a **horizontal `QSplitter`** between the **left metadata pane**, **center image area**, and **right tools pane**. Users can drag those dividers; sizes are persisted (`splitter_sizes` via `ConfigManager`).
- The **multi-window image area** (`MultiWindowLayout`) lays out subwindows with a **`QGridLayout`** on `layout_widget`. Grid cells typically get **equal** stretch; there is **no** draggable sash **between** the 1×2 / 2×1 / 2×2 image panes—only discrete layout modes (View → Layout).

So the checklist item targets **intra–image-grid** proportions (e.g. one large viewer and one narrow strip), not the outer left/center/right splitter.

### Feasibility and difficulty

| Aspect | Assessment |
|--------|----------------|
| **Feasibility** | **High** — Qt is designed for this (`QSplitter`, nested splitters). |
| **Difficulty** | **Medium** — not a single-widget tweak: layout transitions, persistence, mins/maxes, and interaction with **focus**, **swap**, **1×1 expand**, and **window map** must stay coherent. |
| **Risk** | **Medium** — regressions in resize/viewport refit paths (`SubwindowLifecycleController` coalesced resize timers, pan preservation) are likely unless tested per layout. |

### Implementation outline

1. **Replace or wrap the grid** with **nested `QSplitter`s** whose hierarchy depends on mode:
   - **2×2:** e.g. vertical splitter of two horizontal splitters (or one outer horizontal splitting two vertical stacks—pick one convention and stick to it).
   - **1×2 / 2×1:** single splitter with two children (each child may still be a container holding one `SubWindowContainer`).
2. **Map logical slots** (0–3) to splitter leaves consistently with existing `slot_to_view` / swap semantics; document the mapping in code comments.
3. **Persist sizes** per layout mode (and optionally per `slot_to_view` permutation), e.g. `multi_window_splitter_sizes_2x2: [w_top, w_bottom, ...]` — shape must be validated on load like `splitter_sizes`.
4. **Minimum sizes:** enforce `setMinimumWidth` / `setMinimumHeight` on panes so a divider cannot collapse a pane to zero unless we explicitly support “collapse” (probably out of scope for v1).
5. **Layout switches:** when changing `1x2` → `2x2`, **restore** last saved splitter state for the target mode or apply sensible defaults from current total geometry.
6. **Tests:** headless or widget tests that set sizes, switch layout, and assert child visibility and `sizes()` round-trip through config.

### Out of scope / follow-ups

- **Subdividing a single subwindow into tiles** is a separate, heavier item (see [`plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md`](plans/WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md) if present).
- **Preset asymmetric layouts** (e.g. one large + two small) overlaps with other TO_DO items about fixed templates; draggable splitters give users **continuous** control without defining every template.

---

## 2. Frames, instances, and slices in the cine player

### DICOM and viewer vocabulary (short)

| Term | Meaning in DICOM / this codebase |
|------|----------------------------------|
| **SOP Instance** | One identifiable object (often one file). Has `SOPInstanceUID`. |
| **Frame** | One 2D image plane inside a **multi-frame instance** (`NumberOfFrames` (0028,0008) > 1). After load, the organizer may expand these into **per-frame** display objects (see multi-frame docs). |
| **Slice (spatial)** | A distinct **physical** slice position, often inferred from **geometry** tags, not from a single mandatory “slice number” tag. |
| **“Slice” in the navigator / cine index** | Often the **index in the ordered series list** after organization—may be **one instance** or **one expanded frame**, depending on modality and loader behavior. |

### Is there a “slice number” tag?

- There is **no single standard tag** that always equals “slice index in the stack.”
- Common **hints** (modality-dependent): **`ImagePositionPatient`** (0020,0032) with **`ImageOrientationPatient`** (0020,0037) for ordering along the normal; optional **`SliceLocation`** (0020,1041); **`InstanceNumber`** (0020,0013) is **acquisition instance order** and can disagree with true spatial order—still useful for labeling.
- Enhanced MR/CT may use **functional groups** (`SharedFunctionalGroupsSequence` / `PerFrameFunctionalGroupsSequence`) for per-frame geometry; a future tier of work is noted in [`TO_DO.md`](TO_DO.md) under *Data / Platform*.

### What the app does today

- **`CinePlayer._advance_frame`** (when `current_datasets` is set) uses **`slice_grouping`**: advance **frame-by-frame within the same “slice group”** (same original multi-frame source or single-frame instance), then jump to the **first frame of the next slice group**. That is already a **combined** spatial + temporal walk, but the **UI** mostly presents a **single linear slider** and labels like **“Slice”** in some paths—so users cannot see **which axis** they are scrubbing or restrict playback to one axis.

### User goals (examples)

- **Cardiac / dynamic:** loop **only temporal frames** on the **current** slice (same `ImagePositionPatient`), without advancing to the next spatial location.
- **Stack cine:** play **spatial progression** (classic CT/MR stack)—either one frame per instance or “skip to next instance” when multi-frame exists.
- **Mixed:** “play all frames on slice *k*, then move to slice *k+1*” (close to current behavior) vs “play slice *k* once (middle frame) then next slice.”

### UX approaches (pros / cons)

1. **`QComboBox` or compact toolbar “Play mode”**  
   - **Pros:** little space; one clear persisted enum.  
   - **Cons:** needs good labels + tooltip; advanced combos may need a dialog anyway.

2. **Radio button group** (on cine widget or in **Cine options…**)  
   - **Pros:** very explicit; good for 3–5 mutually exclusive modes.  
   - **Cons:** eats vertical space if on the main bar.

3. **Toggle + modifier** (e.g. **Shift+Play** = alternate mode)  
   - **Pros:** power users.  
   - **Cons:** poor discoverability unless documented in **USER_GUIDE**.

4. **Small dialog: “Cine playback…”**  
   - **Pros:** room for definitions, per-modality hints, future advanced options (loop bounds per axis).  
   - **Cons:** extra click for common changes—mitigate with “last mode” on main UI.

**Recommendation:** persist a **`cine_playback_axis`** (or similar) in config; expose via **combo on the cine bar** for the 2–3 most common modes, with **“More…”** opening a dialog for the full matrix below.

### Suggested playback modes (initial set)

Define modes in **implementation terms** (map to indices in `slice_navigator` / slice groups):

| Mode | Advance rule (conceptual) |
|------|---------------------------|
| **`full_linear`** (default, current) | Next **list index**; with `slice_grouping`, that means **frames within slice group, then next group**. |
| **`frames_only_current_slice`** | If current position is inside a multi-frame **slice group**, loop **only** indices belonging to that group (respect loop bounds clipped to group). If single-frame, no-op or disable with tooltip. |
| **`instances_only`** | Jump to **first frame index** of each slice group, skipping intermediate frame indices (spatial “instance” steps). |
| **`temporal_then_spatial`** | Same as **`full_linear`** if naming helps users; alias for documentation. |

Optional later:

- **`spatial_then_temporal`** — for each slice index, play all frames before moving slice (may match **`full_linear`** depending on list ordering—verify before exposing two names).
- **Explicit “DICOM instance” step** — step by **unique `SOPInstanceUID`** in series order (can differ from slice-group boundaries if organization changes).

### Engineering tasks

1. **Refactor advance logic** out of a single `_advance_frame` into a strategy or small functions keyed by mode (keeps `CinePlayer` testable).
2. **Align slider and labels** with the active mode: e.g. “Frame 3/14 (slice 7/120)” or dual readouts—requires knowing **group index** + **index within group** from [`slice_grouping.py`](../src/core/slice_grouping.py).
3. **Loop bounds:** decide whether A–B loop applies to **linear index** only or also to **frame-only** sub-ranges (document choice).
4. **Cine export / video** ([`src/core/cine_video_export.py`](../src/core/cine_video_export.py)): ensure exported frame sequence matches the selected mode (or warn “export uses full linear order”).
5. **Tests:** synthetic multi-frame series in `tests/` verifying each mode’s index sequence.

### Feasibility and difficulty

| Aspect | Assessment |
|--------|------------|
| **Feasibility** | **High** for labeling + **frames-only** / **instances-only** on top of existing grouping; **medium** if tied to strict DICOM geometry ordering independent of list order. |
| **Difficulty** | **Medium** (UI + state + tests); **higher** if you require **functional-groups–aware** axes before list organization is upgraded. |
| **Risk** | Confusing labels if **InstanceNumber** is shown as “slice”; mitigate with tooltips and USER_GUIDE glossary. |

---

## Summary

| Item | Feasibility | Effort | Main work |
|------|-------------|--------|-----------|
| Unequal pane dividers | High | Medium | Replace `QGridLayout` image area with nested `QSplitter`s + persisted sizes + layout-mode matrix |
| Cine frame/slice/instance clarity | High | Medium | Playback strategy enum, UI (combo + optional dialog), slider copy, tests, export alignment |

**Last updated:** 2026-04-16
