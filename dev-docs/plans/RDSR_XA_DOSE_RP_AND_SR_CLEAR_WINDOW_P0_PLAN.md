# P0 plan: XA fluoroscopy RDSR dose (RP) / units + “Clear this window” with SR

**Created:** 2026-04-20  
**Tracks:** [`dev-docs/TO_DO.md`](../TO_DO.md) — Performance / Packaging P0 items (dose RP validation; SR clear-window UI).

---

<a id="p0-xa-rdsr-dose-rp-units"></a>

## 1. XA fluoroscopy RDSR — Dose (RP), DAP, order of magnitude, units

### 1.1 Goal

Confirm that **Dose (RP)** (concept **113738**, DCM), **DAP** (**122130**, DCM), and related X-ray irradiation event NUMs are **shown with correct numeric interpretation** (no silent unit mix-ups, no misleading implied units) for **XA / fluoroscopy-style** radiation dose SRs (TID **10003** *Irradiation Event X-Ray Data*, code **113706**).

### 1.2 Relevant code (findings)

| Area | Location | Notes |
|------|----------|--------|
| Irradiation event row builder | [`src/core/rdsr_irradiation_events.py`](../../src/core/rdsr_irradiation_events.py) | Standard columns include **DAP** and **Dose (RP)** via `_COL_DAP` / `_COL_DOSE_RP` and `_num_value_by_concept`. |
| NUM extraction | Same file, `_best_num_for_concept` → `_num_value_from_item` | **NumericValue / FloatingPointValue only** — **does not append** `MeasurementUnitsCodeSequence` (UCUM) to the cell string. |
| Alternative (with units) | `_num_value_from_item_with_units`, `_format_item_value` | Used for generic tree/value formatting, **not** for the fixed dose-events table columns. |
| CT-style columns | `_build_event_columns` | **CTDIvol** / **DLP** headers include explicit units in the **column title** (`mGy`, `mGy·cm`). **DAP** and **Dose (RP)** headers do **not** embed units in the title — users may assume wrong units. |
| Tools → Radiation dose report | [`src/gui/dialogs/radiation_dose_report_dialog.py`](../../src/gui/dialogs/radiation_dose_report_dialog.py) | **CT summary** (`CtRadiationDoseSummary`); **not** the primary place for per-event XA fluoroscopy rows (those live in the **Structured Report** browser dose-events tab). |
| SR browser | [`src/gui/dialogs/structured_report_browser_dialog.py`](../../src/gui/dialogs/structured_report_browser_dialog.py) | Calls `extract_irradiation_events` from `rdsr_irradiation_events` for the **Dose events** table. |

**Synthetic fixture** ([`tests/scripts/generate_rdsr_dose_sr_fixtures.py`](../../tests/scripts/generate_rdsr_dose_sr_fixtures.py)): X-ray event example encodes DAP with UCUM **Gy·cm²** (`Gy.cm2` / “gray square centimeter”). The table path would display **`22.5`** for that cell (no `"Gy·cm²"` suffix), while the document tree path can show units via `_format_item_value`.

**Risk:** If vendors encode **mGy·cm²** vs **Gy·cm²** (or **µGy** at reference point vs **mGy**) correctly in **NumericValue + UCUM**, the **raw number is still correct** — but the **UI hides UCUM**, so users cannot cross-check the encoder’s unit choice and may mentally apply the wrong scale. A second risk is **legacy / inconsistent UCUM** codes vs human-readable `CodeMeaning`; relying on column titles alone is fragile for XA.

### 1.3 Deeper investigation (recommended)

1. **Acquire de-identified XA RDSR samples** (multiple vendors): compare app **Dose events** row for **113738** / **122130** to vendor PDF/browser or DICOMweb viewer that shows UCUM.
2. **Log or unit-test** parsed `(NumericValue, MeasurementUnitsCodeSequence)` for those concept codes on real files (no PHI in repo — keep fixtures synthetic or redacted).
3. **Cross-check DICOM PS3.16** templates for TID 10003: allowed units for **Dose (RP)** and **DAP** (and whether **dGy·cm²** legacy patterns still appear).

### 1.4 Proposed fixes (implementation options)

**A (minimal, high value):** For columns **DAP** and **Dose (RP)** (and optionally other high-risk NUMs), display using **`_num_value_from_item_with_units`** (or equivalent) so the cell shows **`{value} {CodeMeaning or UCUM}`** as in the SR tree. Optionally tighten column titles to say “(value + units as in dataset)”.

**B (presentation):** Keep raw number but add a **second column** “DAP units” / “Dose (RP) units” sourced from the winning `MeasuredValueSequence[0].MeasurementUnitsCodeSequence`.

**C (validation only):** Add a **warning row** in extraction `notes` when UCUM is missing for 113738/122130, or when magnitude is outside plausible clinical bands (heuristic, vendor-dependent — use only as a soft flag).

**Export:** Confirm CSV/JSON export for dose events uses the same string builder; align export with whatever display fix is chosen so exported tables match on-screen semantics.

### 1.5 Related plans

- [`plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md`](supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md)  
- [`plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`](supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md)  
- [`plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md`](supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md)

---

<a id="p0-sr-clear-window-overlay"></a>

## 2. “Clear this window” on an SR pane — message and button remain

### 2.1 Goal

After **Clear this window** (context menu), the **no-pixel SR** bottom bar (**hint + “Open structured report…”**) must **hide** like other pane content, leaving an empty pane consistent with cleared windows.

### 2.2 Relevant code (findings)

| Area | Location | Notes |
|------|----------|--------|
| SR bar widget | [`src/gui/no_pixel_placeholder_overlay.py`](../../src/gui/no_pixel_placeholder_overlay.py) | `configure(active=…)` controls visibility of hint + button. |
| Show/hide API | [`src/gui/image_viewer.py`](../../src/gui/image_viewer.py) — `set_no_pixel_placeholder_bar` | Delegates to overlay `configure`. |
| When the bar is shown | [`src/core/slice_display_manager.py`](../../src/core/slice_display_manager.py) — `_render_base_image_pipeline` | If `no_pixel_placeholder` and `Modality == "SR"`, calls `set_no_pixel_placeholder_bar(True, …)`; else **`False`**. |
| Clear pane | [`src/main.py`](../../src/main.py) — `_clear_subwindow` | Clears scene, managers (including `slice_display_manager.clear_display_state()`), resets `subwindow_data` — **does not** call `set_no_pixel_placeholder_bar(False)`. |
| `clear_display_state` | [`src/core/slice_display_manager.py`](../../src/core/slice_display_manager.py) (≈246–258) | Clears cached study/series/dataset and projection flags — **does not** reset the SR overlay. |

**Root cause:** The overlay is driven only from the **display / render** path when a dataset is present. **Clear** removes the dataset but **does not re-run** `_render_base_image_pipeline` with an empty state, so the overlay **stays in its last configured state** (still visible).

### 2.3 Proposed fix

**Preferred (localized):** In `SliceDisplayManager.clear_display_state()`, after resetting fields, call:

```python
self.image_viewer.set_no_pixel_placeholder_bar(False)
```

This runs whenever `_clear_subwindow` clears the slice display manager (same path as close series/study for that subwindow), so **Clear this window** and other clears stay consistent.

**Alternative:** Call `set_no_pixel_placeholder_bar(False)` from `_clear_subwindow` in `main.py` immediately after `scene.clear()` / when `subwindow.image_viewer` exists — slightly more duplicated if multiple callers bypass `clear_display_state`.

### 2.4 Verification

1. Load an **SR** instance into a pane (no pixels) — confirm bar visible.  
2. **Clear this window** — bar must disappear; viewport should show empty / gray canvas behavior consistent with other cleared panes.  
3. Regression: load SR again — bar returns.  
4. Optional: non-SR **no image** placeholder path (`Modality != "SR"`) should remain unchanged (bar should stay off).

### 2.5 Related UI

- Context menu wires clear: [`src/core/subwindow_lifecycle_controller.py`](../../src/core/subwindow_lifecycle_controller.py) (`clear_window_content_requested` → `app._on_clear_subwindow_content_requested`).

---

## 3. Checklist

- [ ] Dose RP / DAP: document UCUM behavior on N real XA RDSRs (table + export).  
- [ ] Dose RP / DAP: implement display (and export) fix per §1.4 **A** or **B**, plus tests on synthetic + one redacted fixture.  
- [ ] SR clear window: implement §2.3; manual QA + optional small unit/integration test if harness allows QWidget without full GUI run.  
- [ ] Update [`CHANGELOG.md`](../../CHANGELOG.md) under **Unreleased** when product code ships for either item.
