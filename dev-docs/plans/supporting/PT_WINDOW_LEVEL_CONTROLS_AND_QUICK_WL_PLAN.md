# Plan: PT Window/Level Controls and Quick W/L (BQML)

**Created:** 2026-05-31  
**Covers TO_DO (Bugs / Correctness):**

1. **[P1] Quick window/level input cap on PT (BQML)** — spinbox appears capped near ~1000; will not accept more than three typed digits.
2. **[P1] W/L slider vs spinbox mismatch on PT** — sliders pinned right after load; spinbox edits move sliders the wrong way.

These items share one root area: how the right-panel W/L widget and Quick W/L dialog derive **allowed ranges** and how **sliders stay in sync** with spinboxes.

---

## Goal and success criteria

### User-visible goals

- On PT series with **BQML** (or other rescaled activity units), users can enter clinically meaningful **Window Center** and **Window Width** in:
  - right-panel spinboxes,
  - **Quick Window/Level (Q)** dialog,
  - and via right-drag W/L (within the same policy).
- After load and after any spinbox edit, **horizontal sliders visually match** the numeric center/width (no “pinned right” while numbers change oppositely).
- Embedded DICOM W/L (which may be far outside observed pixel min/max) remains displayable without silent clamping to a ~1000-scale pixel envelope.

### Success criteria (testable)

| Check | Pass condition |
|-------|----------------|
| Large DICOM W/L | Load PT with `WindowCenter`/`WindowWidth` ≫ series pixel max (e.g. changelog case ~35121 / ~63217); spinboxes show those values; Quick W/L accepts the same magnitudes. |
| BQML pixel cap | If series rescaled max ≈ 50 Bq/ml, user can still set center/width > 50 when needed (presets, manual entry, DICOM defaults). |
| Slider sync | After load, both sliders reflect spinbox values; editing center or width spinbox moves sliders monotonically in the same direction. |
| Regression | CT/MR series: existing W/L behavior unchanged (ranges still sensible; no spurious `valueChanged` on series switch per CHANGELOG fix). |
| Automated | New unit tests on `WindowLevelControls` mapping and range computation (no full GUI harness required). |

---

## Context and links

### Backlog

- `dev-docs/TO_DO.md` — Bugs / Correctness, lines for Quick W/L cap and slider mismatch.

### Primary code (confirmed in repo)

| Area | Path | Role |
|------|------|------|
| W/L UI | `src/gui/window_level_controls.py` | Spinboxes, 0–1000 normalized sliders, `set_ranges`, `set_window_level` |
| Quick W/L | `src/gui/dialogs/quick_window_level_dialog.py` | Modal spinboxes; ranges copied from `window_level_controls` |
| Quick open | `src/core/actions/dialog_actions.py` → `open_quick_window_level` | Passes `center_range` / `width_range` from controls |
| Range on display | `src/core/slice_display_manager.py` → `_sync_controls_and_metadata` | Sets ranges from **series pixel min/max** |
| Same pattern | `src/core/view_state_manager.py` | `set_ranges` when updating slice / rescale |
| Pixel stats | `src/core/dicom_pixel_stats.py` | `get_pixel_value_range`, `get_series_pixel_value_range` |
| DICOM W/L | `src/core/dicom_window_level.py` | Embedded WC/WW after rescale |
| PT presets | `src/core/wl_builtin_presets.py` | SUV-style presets (small numeric range) |
| Prior fix | `CHANGELOG.md` (2026-04 area) | **set_window_level before set_ranges** on series switch to avoid Qt clamp + `valueChanged` |

### DICOM / clinical reference (external)

Per [DICOM PS3.3 C.11.2 VOI LUT](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html):

- **Window Center / Window Width** apply to values **after** Modality LUT and **Rescale Slope/Intercept** (i.e. the same space as displayed rescaled pixels when rescale is used).
- For PET, [C.8.9.4 PET Image Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.9.4.html): `Rescale Intercept` is **0**; `Rescale Slope` maps stored values to **Units (0054,1001)** such as **BQML**.

Implication for the viewer: **observed activity in a series** (e.g. 0–30 Bq/ml) is often **much smaller** than **manufacturer default WC/WW** or counts-scaled tags still present in the file. Using **only** sampled pixel min/max as spinbox hard limits is incorrect for PT and explains both reported bugs.

### Related in-repo plans (do not duplicate wholesale)

- [UX_IMPROVEMENTS_BATCH1_PLAN.md](UX_IMPROVEMENTS_BATCH1_PLAN.md) §4 — bit-depth **theoretical** pixel range (complements observed series range).
- [WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md](WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md) — done; BQML unit labels now correct in presets menu.
- [PRIVACY_MODE_WINDOW_LEVEL_BUG_FIX.md](PRIVACY_MODE_WINDOW_LEVEL_BUG_FIX.md) — `update_controls=False` on background `display_slice`.

---

## Root cause analysis (code-backed)

### Issue A — “~1000 max” / three digits (Quick W/L and panel spinboxes)

1. **Spinbox maximum is tied to observed pixel statistics**, not to W/L semantics:
   - `center_range = (series_pixel_min, series_pixel_max)`
   - `width_range = (1.0, series_pixel_max - series_pixel_min)`
   - See `slice_display_manager.py` `_sync_controls_and_metadata` (~621–636) and `view_state_manager.py` (~576–587).

2. For many PT series, rescaled **series_pixel_max** is on the order of **tens to low hundreds** (BQML). Then:
   - `width_range` max ≈ that span (e.g. **&lt; 1000**),
   - `center_range` max ≈ same,
   - `QDoubleSpinBox` cannot hold a fourth digit (e.g. **1000** blocked when max is **999.x**).

3. **Quick W/L** reuses the same ranges (`dialog_actions.open_quick_window_level`), so it inherits the cap.

4. **Default** `width_range` in `WindowLevelControls.__init__` is `(1.0, 10000.0)` until first `set_ranges`; a brief clamp can still occur if `set_window_level` runs with large DICOM WW **before** ranges widen (see ordering below).

5. **`slice_display_manager`** may **rewrite** W/L to mid-range when center/width fall outside pixel envelope (~665–677) on non-new-series paths — separate from spinbox cap but can confuse PT testing.

### Issue B — slider vs spinbox mismatch

1. Sliders are always mapped to **0–1000** integers; actual values map via `center_range` / `width_range` (`window_level_controls.py` ~186–201, 232–276).

2. If **current center/width &gt; range max** (common when DICOM WC/WW ≫ pixel max), normalization **clamps** slider to **1000** (“pinned right”) while spinbox may still show a large value until `setRange` clamps it.

3. **`_on_center_changed` / `_on_width_changed` do not update sliders** — only slider handlers update spinboxes. Any spinbox edit leaves sliders stale (opposite motion vs user expectation).

4. **`set_ranges`** updates spinbox limits but **`_update_slider_ranges` is a no-op** (`pass` at ~138–142) and does not reposition sliders after range changes.

5. **Order of operations** on new series (current code): `set_window_level` then `set_ranges`. Values are set before range change (good for CHANGELOG clamp bug), but if post-`set_ranges` values sit outside the new narrow pixel range, Qt may clamp on `setRange` and sliders were positioned using **pre-`set_ranges`** `center_range` during `set_window_level`.

---

## Proposed design

### 1. Single “control envelope” helper (new, small module or function in `dicom_pixel_stats` / `dicom_window_level`)

Compute `(center_min, center_max)` and `(width_min, width_max)` for UI controls:

**Inputs:** modality, `series_pixel_min/max`, current `(wc, ww)`, optional list of preset pairs, optional bit-depth theoretical range, optional embedded DICOM WC/WW.

**Policy (recommended v1):**

```
pixel_lo, pixel_hi = series range (or per-slice fallback)
candidates_hi = [pixel_hi, wc, ww, all preset centers/widths, dicom_wc + dicom_ww/2, ...]
candidates_lo = [pixel_lo, wc - ww/2, ...]

center_min = min(candidates_lo) with floor (e.g. allow negative for signed CT; for PT often 0)
center_max = max(candidates_hi) * margin (e.g. 1.25) or + padding

width_min = 1.0 (or epsilon)
width_max = max(width from presets, dicom_ww, pixel_hi - pixel_lo, wc span) * margin
```

**Minimum width** for PT: do not cap `width_max` at **only** `(pixel_hi - pixel_lo)` when `dicom_ww` or current `ww` is larger.

**Optional v2 (link to UX batch 1):** union with `get_bit_depth_pixel_range()` rescaled — see [UX_IMPROVEMENTS_BATCH1_PLAN.md](UX_IMPROVEMENTS_BATCH1_PLAN.md) §4.

**Out of scope for v1:** changing rendering LUT math; only control limits and slider sync.

### 2. `WindowLevelControls` behavior

- Add `_sync_sliders_from_spinboxes()` (or fold into `_set_values_internal`) called from:
  - `set_window_level`
  - `set_ranges` (after `setRange`)
  - `_on_center_changed` / `_on_width_changed`
- Implement `_update_slider_ranges` as alias to slider sync (or remove dead stub).
- When syncing sliders from spinbox, use **blockSignals** on sliders to avoid feedback loops.
- Consider **decimals**: PT BQML may need 2–3 decimal places for small activities; keep 1 decimal for HU CT unless user asks — document in completion notes.

### 3. Call sites

- Replace duplicated `(pixel_min, pixel_max)` → range logic in:
  - `slice_display_manager._sync_controls_and_metadata`
  - `view_state_manager` (both places that call `set_ranges`)
- Pass **current** `window_center` / `window_width` and **embedded DICOM** WC/WW when computing envelope.
- **Order:** `set_ranges(envelope)` then `set_window_level(wc, ww, block_signals=True)` on new series (invert current order if needed so sliders compute with final ranges). Re-verify CHANGELOG series-switch scenario (PET → CT).

### 4. Quick W/L

- No separate cap logic: ranges from updated `window_level_controls.center_range` / `width_range` after envelope helper runs.
- Optionally add **wider fallback** in dialog only if controls not yet synced (defensive): e.g. `(-1e6, 1e6)` when ranges are degenerate — prefer fixing envelope at source.

### 5. Validation block in `slice_display_manager`

- Revisit ~665–677: clamping user/DICOM W/L into **pixel-only** envelope may be wrong for PT. Prefer:
  - clamp only to **control envelope**, or
  - warn / soft-clamp on apply, not on load of DICOM defaults.

---

## Task graph and gates

### Ordering

- **S1** (spike, optional) → **T1** → **T2** → **T3** → **T4** → **T5** → **T6** → **T7**
- **T4** (UI sync) can start after **T2** (helper API frozen); **T3** tests can be written against helper before UI lands.

### Verification gates

| Gate | Requirement |
|------|-------------|
| G1 | Unit tests for envelope + slider mapping pass before manual PT smoke. |
| G2 | Manual PT BQML load: sliders track spinboxes; Quick W/L accepts values &gt; 1000 when DICOM/preset requires. |
| G3 | Regression: CT series switch PET → CT still applies correct WL (CHANGELOG scenario). |

### File ownership

| Path | Owner |
|------|--------|
| `src/gui/window_level_controls.py` | coder |
| `src/core/dicom_pixel_stats.py` or new `src/core/wl_control_range.py` | coder |
| `src/core/slice_display_manager.py`, `src/core/view_state_manager.py` | coder |
| `tests/test_window_level_controls.py` (new) | coder / tester |
| `dev-docs/TO_DO.md` | mark done after G2–G3 |

---

## Phases

### Phase 0 — Reproduce (tester / user dataset)

- [ ] (T0) Load reported PT BQML study; record `series_pixel_min/max`, DICOM `WindowCenter`/`WindowWidth`, rescaled `RescaleType`, spinbox maxima, slider positions, Quick W/L limits (owner: tester, parallel-safe: no, stream: none, after: none).

### Phase 1 — Control envelope helper

- [ ] (T1) Add `compute_wl_control_ranges(...)` with docstring citing DICOM VOI + PET rescale; inputs listed in design §1 (owner: coder, parallel-safe: no, stream: none, after: T0).
- [ ] (T2) Wire helper into `slice_display_manager._sync_controls_and_metadata` and `view_state_manager` range updates; include current WC/WW and embedded DICOM values in candidates (owner: coder, parallel-safe: no, stream: none, after: T1).
- [ ] (T3) Unit tests: PT-like pixel 0–50, DICOM WC 35000 / WW 60000 → center_max and width_max exceed 1000; BQML small pixel range still allows preset SUV 0–10 (owner: coder, parallel-safe: yes, stream: none, after: T1).

### Phase 2 — Slider ↔ spinbox sync

- [ ] (T4) Implement `_sync_sliders_from_spinboxes()`; call from `set_window_level`, `set_ranges`, `_on_center_changed`, `_on_width_changed`; remove or implement `_update_slider_ranges` (owner: coder, parallel-safe: no, stream: none, after: T2).
- [ ] (T5) Adjust new-series order: `set_ranges` then `set_window_level` if tests show clamp/slider bug; block signals during `setRange` if Qt still emits (owner: coder, parallel-safe: no, stream: none, after: T4).
- [ ] (T6) Unit tests: values above old pixel max → slider not stuck at 1000 after `set_window_level`; spinbox increase → slider increases (owner: coder, parallel-safe: yes, stream: none, after: T4).

### Phase 3 — Quick W/L and validation cleanup

- [ ] (T7) Confirm `open_quick_window_level` inherits widened ranges; manual Quick W/L entry &gt; 1000 on PT fixture (owner: tester, parallel-safe: no, stream: none, after: T2).
- [ ] (T8) Review `slice_display_manager` pixel-only W/L validation (~665–677); align with envelope or disable for embedded DICOM defaults (owner: coder, parallel-safe: no, stream: none, after: T2).

### Phase 4 — Regression and docs

- [ ] (T9) Run `pytest` subset: new tests + `tests/test_dicom_window_level.py` + `tests/test_window_level_preset_handler.py` (owner: tester, parallel-safe: no, stream: none, after: T6).
- [ ] (T10) Manual smoke: CT load, PET→CT switch, right-drag W/L, preset apply (owner: tester, parallel-safe: no, stream: none, after: T9).
- [ ] (T11) Update `CHANGELOG.md` (patch: PT W/L control range + slider sync); check off both TO_DO items with plan link (owner: coder, parallel-safe: no, stream: none, after: T10).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Over-wide ranges make sliders coarse | Keep 0–1000 slider mapping; only change **world** min/max. Optional future: log-scale slider for PT. |
| `setRange` emits `valueChanged` and corrupts view state | Keep `blockSignals` on spinboxes during `set_ranges`; preserve “set values before range” invariant; add test. |
| Envelope too wide for CT HU | Use modality-agnostic max of candidates; CT pixel range already large. |
| Duplicate range logic remains in MPR path | Grep `set_ranges` after T2; update any second call site. |

---

## Modularity and file-size guardrails

- Prefer one **&lt; 120 line** helper module `wl_control_range.py` over growing `slice_display_manager.py`.
- `window_level_controls.py` stays UI-only; no DICOM parsing inside widget.

---

## Testing strategy

```text
.\.venv\Scripts\python.exe -m pytest tests/test_window_level_controls.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_dicom_window_level.py tests/test_window_level_preset_handler.py -v
```

Manual (document dataset ID in completion notes):

1. Open PT BQML series from user report.
2. Note sliders vs spinboxes at load.
3. **Q** → enter center/width above prior cap.
4. Apply DICOM W/L preset if present; confirm spinboxes and sliders match.

---

## UX / UI

- No visual redesign; fix mapping and limits only.
- If spinbox decimals are increased for BQML, keep CT HU at 1 decimal unless usability review says otherwise (defer to **ux** if unclear).

---

## Questions for user

1. **Sample dataset:** Can you attach or name the PT BQML study used when filing the bug (for T0 and regression folder)?
2. **Clamp policy:** When DICOM WC/WW is far above observed activity, should the viewer **preserve** DICOM values on load (preferred in this plan) or **auto-fit** to series min/max?
3. **Scope:** Should envelope widening apply to **NM** and other non-CT modalities in the same change, or PT-only first?

Non-blocking: default implementation preserves DICOM/load values and widens controls for all modalities using the same helper.

---

## Completion notes

*(Fill when implemented: tests run, dataset used, whether Quick W/L and right-drag were checked, CHANGELOG entry.)*
