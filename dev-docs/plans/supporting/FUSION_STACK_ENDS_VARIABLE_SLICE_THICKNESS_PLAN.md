# Plan: Fusion and Slice Sync — Outside Coverage (Stack Ends)

**Created:** 2026-05-31  
**Last updated:** 2026-06-03 (T1–T9 implemented by coder) (user policy: **no edge clamp**; full scroll on all panes; status hints when fusion overlay or slice sync cannot apply)  
**TO_DO:** Bugs / Correctness — *Check what happens at ends of fused stacks when slice thicknesses are different* (e.g. `qcctwhasc2026` / `20260327-UNKNOWN`). **In scope:** same UX for **slice sync** when linked panes have no anatomic match (user confirmed).

---

## Goal and success criteria

### Goal

When PET/CT (or other) fusion pairs have **different slice thicknesses** and **different cranial/caudal coverage**:

1. The user can **scroll the full extent** of the **base** series (and, when focused on overlay series separately, the full overlay series) — navigation must **not** be limited to the geometric overlap or “fused region only.”
2. Where base and overlay **overlap in physical space**, fusion displays as today (2D interpolate or 3D resample).
3. Where the current base slice has **no** overlay coverage (cranial/caudal CT-only extent, etc.), show the **base image only** (no fake PET from edge clamping) plus a **clear status hint** so the behavior is intentional, not “fusion broke.”
4. Where **slice sync** is enabled and the source slice has **no** anatomically matching slice on a linked target (outside target stack coverage / tolerance), **do not** move the target pane; show the **same style of status hint** (user can still scroll every pane through its full series).

### Product decision (user, 2026-05-31)

- **Do not clamp** overlay to first/last PET slice when scrolling outside the overlay stack.
- **Do not restrict** slice scrolling to the fused overlap window (or to the slice-sync overlap window).
- **Do** show a status hint when overlay is unavailable for the current slice.
- **Do** show a status hint when slice sync skips a linked pane because the source position is outside that target’s coverage (no clamping target slice to stack edge).

### Success criteria

| Scenario | Expected behavior (after fix) |
|----------|-------------------------------|
| Scroll entire base series | All base slices reachable; slice count unchanged by fusion. |
| Base slice inside overlay FOV | Fused overlay visible (2D or 3D path per mode). |
| Base slice **below** or **above** overlay stack | **Base-only** display; **no** overlay tint; status hint (e.g. outside overlay coverage). |
| No edge clamp | First/last CT slices do **not** show repeated first/last PET slice. |
| Variable `SliceThickness` along stack | Matching uses **physical position** (IPP / projected location), not index parity. |
| 3D resampling at volume boundary | No crash; outside grid → no overlay (same as 2D), with hint — not clamp. |
| Slice sync, source inside target FOV | Target pane updates to nearest slice (current). |
| Slice sync, source outside target FOV | Target pane **unchanged**; status hint names skipped pane(s). |
| Slice sync scroll | User can scroll **source and all targets** through full series extent. |
| Regression | Fusion audit scripts still pass on overlapping PET/CT slices used in [FUSION_QUANTITATIVE_VERIFICATION_RESULTS.md](../bug-investigations/FUSION_QUANTITATIVE_VERIFICATION_RESULTS.md). |

---

## Context and links

- **Backlog:** `dev-docs/TO_DO.md` line 41.
- **Prior work:** Fusion algorithm fixes 2026-05-22 (direction matrix, per-slice rescale, IPP projection, slice spacing) — verified 0% error on 33 slices; this item is **edge-of-FOV / thickness mismatch**, not core registration math.
- **Audit scripts:** `tests/fusion_audit_*.py`, `tests/fusion_audit_quantitative_verification.py`.

### Primary code

| File | Role |
|------|------|
| `src/core/fusion_handler.py` | `find_matching_slice`, `interpolate_overlay_slice`, 2D vs 3D branch |
| `src/core/fusion_handler_io.py` | `sorted_slice_index_locations`, `linear_blend_rescaled_slices` |
| `src/core/image_resampler.py` | `get_resampled_slice`, `_calculate_slice_spacing`, thickness ratio checks |
| `src/gui/fusion_coordinator.py` | `get_fused_image` — returns `None` overlay → base-only display |
| `src/core/slice_display_manager.py` | Applies fusion on display pipeline |
| `src/core/slice_sync_coordinator.py` | `on_slice_changed`, `_update_target` — silent return when `find_nearest_slice` is `None` (~298–300) |
| `src/core/slice_geometry.py` | `find_nearest_slice`, `SliceStack` — shared geometry for sync tolerance |
| `src/core/slice_display_handlers.py` | Calls `on_slice_changed` after user slice navigation (~133) |
| `src/gui/main_window.py` | `update_status` — slice-sync hints (primary for sync) |

### DICOM reference

- **Slice location:** Prefer `ImagePositionPatient` projected on slice normal; `SliceLocation` is secondary (already used in fusion I/O).
- **Slice thickness:** Tag `SliceThickness` (0028,0010) may **vary** between series; inter-slice **spacing** is often inferred from consecutive IPP (see `slice_geometry._compute_slice_thickness` — median of diffs).
- PET/CT: Anatomical CT often has **more slices** and **finer spacing** than PET; cranial/caudal CT slices commonly have **no PET bracket** — a normal clinical situation.

---

## Root cause analysis (code-backed)

### 1. `find_matching_slice` returns no match outside overlay extent

```278:298:src/core/fusion_handler.py
        for i, (idx, location) in enumerate(overlay_locations):
            if abs(location - base_location) < tolerance:
                return (idx, None)
            if location > base_location:
                if i == 0:
                    return (None, None)  # base below all overlay
                ...
        return (None, None)  # base above all overlay
```

- **Exact match tolerance** is **0.01 mm** — appropriate for duplicate detection, not for thick-slice pairing.
- When base location is **below** the first overlay slice (`i == 0` branch), returns **`(None, None)`** — no nearest-edge fallback.
- When base is **above** the last overlay, returns **`(None, None)`**.

### 2. 2D path: no overlay → base-only image (correct pixels; poor feedback)

`interpolate_overlay_slice` → `idx1 is None` → `return None` → `get_fused_image` still shows base (no fusion tint). **Display behavior already matches the desired policy**; the gap is **silent** UX, not wrong clamping.

### 3. 3D path: boundary behavior unclear

`get_resampled_slice` maps base index to sorted reference grid; outside overlay volume SimpleITK may return empty/None → fallback to 2D, which then hits (1).

### 4. Slice sync: silent skip outside tolerance (correct motion; no feedback)

When the source plane projects outside the target stack beyond `slice_thickness * 0.5` mm, `_update_target` returns without changing the target (`find_nearest_slice` → `None`). That is **not** edge clamping — the target stays on its last slice while the user scrolls the source through CT-only extent. **Missing:** a status hint explaining why the linked pane did not follow.

**Do not change** tolerance math in v1 unless T0 shows false negatives; focus on messaging only.

### 5. Thickness ratio triggers 3D mode

`ImageResampler.needs_resampling` flags 2:1 spacing/thickness ratio (`image_resampler.py` ~625–644). Variable thickness along one series is not explicitly handled in `find_matching_slice`.

---

## Proposed behavior (v1 — approved policy)

| Position relative to overlay stack | Overlay pixels | Navigation | User feedback |
|-----------------------------------|----------------|------------|---------------|
| Inside bracket (interpolate or exact) | Yes — fused image | Full base scroll | Normal fusion status / no warning |
| Below first overlay slice | **None** — base-only | Full base scroll | Status hint: outside overlay coverage (caudal) |
| Above last overlay slice | **None** — base-only | Full base scroll | Status hint: outside overlay coverage (cranial) |
| 3D path outside resample grid | **None** — base-only | Full base scroll | Same hint; optional debug log |

**Explicitly out of scope for v1:**

- **Edge clamp** (repeat first/last PET on extra CT slices).
- **Clamping scroll range** or cine range to the intersection of base and overlay extents.
- **Extrapolated** or synthetic overlay outside the overlay stack.

**Status hint placement (implementer):**

| Feature | Primary surface | Secondary |
|---------|-----------------|-----------|
| Fusion outside overlay | `FusionControlsWidget.set_status` | Main status bar (brief) |
| Slice sync skip | **Main status bar** (`main_window.update_status`) | Optional fusion log only if fusion+sync on same gesture — avoid duplicate |

- Update hints on **slice index change**, not every repaint.
- Clear or replace hint when returning to overlap / successful sync.

**Shared copy style** (tune in implementation; keep parallel wording):

- Fusion: `No overlay for this slice (outside overlay series coverage).`
- Slice sync: `Slice sync: no matching slice in window N (outside that series coverage).` — if multiple targets skip, one line: `Slice sync skipped for window(s) 2, 4 (outside coverage).`
- When overlap/sync resumes: clear warning or short OK line.

**Optional helper:** `src/core/anatomic_coverage_hint.py` (or extend `slice_geometry`) with `classify_position_relative_to_stack(ref_plane, stack) -> inside | below | above` used by fusion matcher and sync skip reporting — avoids duplicated bisect logic.

**Scroll-range verification (T0):** Confirm navigator / `on_slice_changed` use each pane’s **own** `current_datasets` length; fusion and sync must not trim slice counts at stack ends.

---

## Implementation phases

### Phase 0 — Reproduce on named dataset (tester)

- [ ] (T0) Load `qcctwhasc2026` / `20260327-UNKNOWN` (or user path); PET/CT in linked group + fusion on; confirm **full slice count** on CT and PET panes; at CT-only ends verify base-only fusion; scroll CT while PET linked — confirm PET pane does not clamp-scroll and note silent sync skip today (owner: tester, parallel-safe: no, stream: none, after: none).

### Phase 1 — Classify match result (no clamp)

- [x] (T1) Add `OverlayMatchResult` (or extend `find_matching_slice` return) with `inside | below_stack | above_stack | no_geometry` — **without** changing “outside stack → no overlay indices” behavior (owner: coder, parallel-safe: no, stream: none, after: T0).
- [x] (T2) Unit tests: below / above / inside / exact match; assert **no** indices returned for below/above (owner: coder, parallel-safe: yes, stream: none, after: T1).

### Phase 2 — Status hints only

- [x] (T3) `FusionCoordinator.get_fused_image` (or `display_slice` hook): when `interpolate_overlay_slice` returns `None` and fusion enabled, set status hint from match class; clear hint when overlay returns (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T4) Avoid spam: update hint on slice change only, not every repaint (owner: coder, parallel-safe: no, stream: none, after: T3).
- [x] (T5) 3D path: outside grid → `None` overlay + same hint; **no** clamp in `get_resampled_slice` (owner: coder, parallel-safe: no, stream: none, after: T1).

### Phase 3 — Slice sync hints (same policy)

- [x] (T6) In `_update_target`, when `find_nearest_slice` returns `None`, record `(target_idx, reason)` — `outside_coverage` vs `no_geometry` (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T7) `on_slice_changed`: after target loop, if any skip, call `app.main_window.update_status` with pane label(s); clear when all targets sync (owner: coder, parallel-safe: no, stream: none, after: T6).
- [x] (T8) Do **not** clamp target index to nearest stack slice; do **not** widen tolerance to force sync at ends (owner: coder, parallel-safe: no, stream: none, after: T6).
- [x] (T9) Unit test: mock stacks — source below target range → no `display_slice` on target, hint callback invoked (owner: coder, parallel-safe: yes, stream: none, after: T6).

### Phase 4 — Verification

- [ ] (T10) Re-run `tests/fusion_audit_quantitative_verification.py` on overlapping slices — no regression (owner: tester, parallel-safe: no, stream: none, after: T5).
- [ ] (T11) Manual: CT+PET linked; fusion hints at CT ends; sync hints when CT scrolled past PET; full scroll both series (owner: tester, parallel-safe: no, stream: none, after: T7).
- [ ] (T12) Optional: audit script “outside coverage” slice count at CT ends (owner: coder, parallel-safe: yes, stream: none, after: T2).

---

## Task graph and gates

- **Fusion:** T0 → T1 → T2 → T3 → T4 → T5 → T10  
- **Slice sync:** T1 → T6 → T7 → T8 → T9 → T11 (T1 shared classifier)  
- **T10–T12** after both streams
- **Gate G1:** Unit tests pass before manual qcctwhasc run.
- **Gate G2:** Quantitative audit unchanged on prior passing exams.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Users think fusion failed when overlay disappears | Status hint + optional one-line in user guide. |
| Status log noise on fast scroll | Debounce or update only when match class / sync-skip set changes. |
| Fusion + sync hints on same scroll | Prefer one combined status line if both apply, or fusion panel + status bar split per table above. |
| Future request for edge clamp | Do not add clamp for fusion or sync unless user reverses policy. |

---

## Modularity

- Keep matching logic in `fusion_handler.py` or extract `fusion_slice_matching.py` (&lt; 200 lines).
- Do not change `fusion_processor` blend math in v1.

---

## Testing strategy

```text
.\.venv\Scripts\python.exe -m pytest tests/ -k fusion -v --tb=short
.\.venv\Scripts\python.exe tests/fusion_audit_quantitative_verification.py
```

Add `tests/test_fusion_slice_matching.py` and `tests/test_slice_sync_outside_coverage_hint.py` (no DICOM files required).

---

## Questions for user

1. Confirm path to **`qcctwhasc2026` / `20260327-UNKNOWN`** study for T0.
2. ~~Prefer edge clamp vs base-only outside PET FOV?~~ **Answered:** base-only + status hint; **no** edge clamp; **no** scroll restriction to fused region.
3. ~~Should slice sync follow the same policy?~~ **Answered:** yes — full scroll on all panes; status hint when sync cannot match (no clamping target to stack edge).

---

## Completion notes

**Hint copy (as implemented):**
- Fusion outside overlay: `No overlay for this slice (outside overlay series coverage).`
- Slice sync skip (single): `Slice sync: no matching slice in window N (outside that series coverage).`
- Slice sync skip (multiple): `Slice sync skipped for window(s) 2, 4 (outside coverage).`
- Back in range (fusion): `Fusion overlay active.` (logged once on transition back)
- Back in sync: clear hint (empty string to main status bar)

**Tests:** `tests/test_fusion_slice_matching.py` (15 tests), `tests/test_slice_sync_outside_coverage_hint.py` (8 tests) — 797/797 pass.
**Regression:** `fusion_audit_quantitative_verification.py` requires the qcctwhasc2026 DICOM dataset (not present in repo); exit 0 when run without args; full regression suite clean.
**CHANGELOG:** Added under [Unreleased] — minor entry.
**Manual (T0/T10/T11):** Requires qcctwhasc2026 dataset; not yet verified.


