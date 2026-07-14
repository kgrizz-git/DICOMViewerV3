# P0 plan: XA fluoroscopy RDSR dose (RP) / units + “Clear this window” with SR

**Created:** 2026-04-20 · **§1.3 samples checked:** 2026-04-20 (`test-DICOM-data/pyskindose_samples/`) · **Implementation shipped:** 2026-04-21 — app **0.2.11**; [`TO_DO.md`](../../TO_DO.md) lines **40–41** `[x]`.  
**Tracks:** [`dev-docs/TO_DO.md`](../../TO_DO.md) — Performance / Packaging P0 items (dose RP validation; SR clear-window UI).  
**Execution:** follow the **master checklist** in [§3](#master-checklist); implementation detail in [§1.6](#plan-dose-b-c-export) (dose **B** / **C** / export) and [§2.6](#plan-sr-clear-overlay) (SR overlay clear). **When you finish a task:** mark it complete **in this plan first** ([§3.0 — completion protocol](#completion-protocol)), then update [`TO_DO.md`](../../TO_DO.md) as described there.

---

<a id="p0-xa-rdsr-dose-rp-units"></a>

## 1. XA fluoroscopy RDSR — Dose (RP), DAP, order of magnitude, units

### 1.1 Goal

Confirm that **Dose (RP)** (concept **113738**, DCM), **DAP** (**122130**, DCM), and related X-ray irradiation event NUMs are **shown with correct numeric interpretation** (no silent unit mix-ups, no misleading implied units) for **XA / fluoroscopy-style** radiation dose SRs (TID **10003** *Irradiation Event X-Ray Data*, code **113706**).

### 1.2 Relevant code (findings)

| Area | Location | Notes |
|------|----------|--------|
| Irradiation event row builder | [`src/core/rdsr_irradiation_events.py`](../../../src/core/rdsr_irradiation_events.py) | Standard columns include **DAP** and **Dose (RP)** via `_COL_DAP` / `_COL_DOSE_RP` and `_num_value_by_concept`. |
| NUM extraction | Same file, `_best_num_for_concept` → `_num_value_from_item` | **NumericValue / FloatingPointValue only** — **does not append** `MeasurementUnitsCodeSequence` (UCUM) to the cell string. |
| Alternative (with units) | `_num_value_from_item_with_units`, `_format_item_value` | Used for generic tree/value formatting, **not** for the fixed dose-events table columns. |
| CT-style columns | `_build_event_columns` | **CTDIvol** / **DLP** headers include explicit units in the **column title** (`mGy`, `mGy·cm`). **DAP** and **Dose (RP)** headers do **not** embed units in the title — users may assume wrong units. |
| Tools → Radiation dose report | [`src/gui/dialogs/radiation_dose_report_dialog.py`](../../../src/gui/dialogs/radiation_dose_report_dialog.py) | **CT summary** (`CtRadiationDoseSummary`); **not** the primary place for per-event XA fluoroscopy rows (those live in the **Structured Report** browser dose-events tab). |
| SR browser | [`src/gui/dialogs/structured_report_browser_dialog.py`](../../../src/gui/dialogs/structured_report_browser_dialog.py) | Calls `extract_irradiation_events` from `rdsr_irradiation_events` for the **Dose events** table. |

**Synthetic fixture** ([`tests/scripts/generate_rdsr_dose_sr_fixtures.py`](../../../tests/scripts/generate_rdsr_dose_sr_fixtures.py)): X-ray event example encodes DAP with UCUM **Gy·cm²** (`Gy.cm2` / “gray square centimeter”). The table path would display **`22.5`** for that cell (no `"Gy·cm²"` suffix), while the document tree path can show units via `_format_item_value`.

**Risk:** If vendors encode **mGy·cm²** vs **Gy·cm²** (or **µGy** at reference point vs **mGy**) correctly in **NumericValue + UCUM**, the **raw number is still correct** — but the **UI hides UCUM**, so users cannot cross-check the encoder’s unit choice and may mentally apply the wrong scale. A second risk is **legacy / inconsistent UCUM** codes vs human-readable `CodeMeaning`; relying on column titles alone is fragile for XA.

### 1.3 Deeper investigation — `test-DICOM-data/pyskindose_samples/`

**Note:** This folder is often **gitignored** (local / PySkinDose test pack); investigation used the on-disk copies under the repo root when present.

#### 1.3.1 Files vs dose-event extraction

| File | `SOPClassUID` tail | `extract_irradiation_events` rows | Notes |
|------|-------------------|-----------------------------------|--------|
| `philips_allura_clarity_u104.dcm` | `…88.67` (Enhanced X-Ray Radiation Dose SR) | **25** | Full **113706** / **122130** / **113738** path. |
| `philips_allura_clarity_u601.dcm` | `…88.67` | **29** | Same pattern, second system example. |
| `siemens_axiom_artis.dcm` | `…88.67` | **21** | Siemens-style NUM + UCUM. |
| `siemens_axiom_example_procedure.dcm` | `…88.67` | **24** | Same. |
| `dicom-test-files_reportdsi.dcm` | `…88.11` | **0** | Not a recognized radiation dose SR for our parser; notes: no **113706**/**113819** containers. |
| `dicom-test-files_reportdsi_empty_number_tags.dcm` | `…88.11` | **0** | Same. |
| `pydicom_test-SR.dcm` | `…88.33` | **0** | Generic SR fixture; not RDSR-style for dose events. |

So **four** Philips/Siemens **88.67** files are the relevant XA-style RDSR set; the smaller **88.11** DSI-style files do not populate the dose-events table with today’s detection rules.

#### 1.3.2 `113738` (Dose RP) and `122130` (DAP) — dataset vs app table

For every **122130** / **113738** `NUM` under these trees (walked with the same **DCM** concept matching as `rdsr_irradiation_events`):

- **Dose (RP) (`113738`):** `MeasurementUnitsCodeSequence` is consistently **UCUM `Gy`** (`CodeMeaning` / `CodeValue` aligned with gray). Numeric magnitudes are small positives (e.g. `3e-05`, `0.00013` **Gy**), consistent with **reference-point air kerma** per event in **Gy** (clinical displays often use **mGy** or **µGy** by rescaling, not by changing the stored pair).

- **DAP (`122130`):** Units in the objects are **not** `Gy·cm²` as in our synthetic fixture ([`generate_rdsr_dose_sr_fixtures.py`](../../../tests/scripts/generate_rdsr_dose_sr_fixtures.py)). Philips uses UCUM **`Gy.m2`** / `CodeMeaning` **Gy.m2**; Siemens uses UCUM **`Gym2`** (same physical dimension, compact UCUM). So the stored quantity is **Gy·m²** (SI).

- **App table today:** `extract_irradiation_events` → column **DAP** / **Dose (RP)** uses `_num_value_from_item` (numeric only). Spot check **matches** `NumericValue` in the object (e.g. Siemens `siemens_axiom_artis.dcm` first event: table **DAP** `7.4e-07`, **Dose (RP)** `3e-05` — same as file). So there is **no parser bug** swapping digits; the gap is **presentation** (no UCUM in the cell, no column title stating **Gy·m²** for DAP).

#### 1.3.3 Clinical scaling trap (DAP only)

If a reader assumes **DAP** is in **Gy·cm²** (or **mGy·cm²**) because that is common on consoles, they can be wrong by an order of magnitude **10⁴** relative to **Gy·m²**:

- **1 Gy·m² = 10⁴ Gy·cm²** (1 m² = 10⁴ cm²).  
- Example: **7.4×10⁻⁷ Gy·m²** (Siemens first row) **= 7.4×10⁻³ Gy·cm² = 7.4 mGy·cm²**, which is a plausible small fluoroscopy DAP when expressed the way many clinicians expect.

**Dose (RP)** in **Gy** → multiply by **10³** for **mGy**, by **10⁶** for **µGy**; no area dimension, so less confusion than DAP.

#### 1.3.4 PS3.16 / legacy units in this sample set

- No **`dGy·cm²`** (or other legacy DAP UCUM) appeared on **122130** in these four files; encoders used **Gy** and **Gy·m²** / **`Gym2`**.  
- TID **10003** still allows other UCUM encodings in the wild; **showing UCUM from the object** (plan §1.4 **A**/**B**) remains the robust mitigation.

#### 1.3.5 Residual actions (outside this folder)

- Optional **vendor PDF / interventional report** side-by-side on the same study (not in repo) to confirm displayed **mGy·cm²** matches **Gy·m² × 10⁷ → mGy·cm²** where vendors convert that way.  
- Add a **redacted** or **synthetic** **88.67** snippet under `tests/fixtures/` for CI (folder here may be absent on CI).

### 1.4 Proposed fixes (implementation options)

**A (minimal, high value):** For columns **DAP** and **Dose (RP)** (and optionally other high-risk NUMs), display using **`_num_value_from_item_with_units`** (or equivalent) so the cell shows **`{value} {CodeMeaning or UCUM}`** as in the SR tree. Optionally tighten column titles to say “(value + units as in dataset)”.

**B (presentation):** Keep raw number but add a **second column** “DAP units” / “Dose (RP) units” sourced from the winning `MeasuredValueSequence[0].MeasurementUnitsCodeSequence`.

**C (validation only):** Add a **warning row** in extraction `notes` when UCUM is missing for 113738/122130, or when magnitude is outside plausible clinical bands (heuristic, vendor-dependent — use only as a soft flag).

**Export:** Confirm CSV/JSON export for dose events uses the same string builder; align export with whatever display fix is chosen so exported tables match on-screen semantics.

### 1.5 Related plans

- [`plans/supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md`](../supporting/SR_DOSE_EVENTS_NORMALIZATION_AND_HIGHDICOM_PLAN.md)  
- [`plans/supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md`](../supporting/SR_FULL_FIDELITY_BROWSER_PLAN.md)  
- [`plans/supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md`](../supporting/HANGING_PROTOCOLS_PRIORS_RDSR_PLAN.md)

<a id="plan-dose-b-c-export"></a>

### 1.6 Complete implementation plan — §1.4 **B**, **C**, and **Export**

**Chosen track for units:** **B** — keep numeric cells unchanged; add **parallel unit columns** sourced from the same `NUM` / `MeasuredValueSequence` entry that `_best_num_for_concept` selects (first row of `MeasuredValueSequence`, matching shallowest-depth policy). **A** remains an acceptable alternative later (merge value + unit in one cell) if table width is constrained.

#### 1.6.1 Preconditions

- [x] Re-read [`src/core/rdsr_irradiation_events.py`](../../../src/core/rdsr_irradiation_events.py): `_build_event_columns`, `_best_num_for_concept`, `_num_value_from_item`, `MeasuredValueSequence`.
- [x] Re-read [`src/gui/dialogs/structured_report_browser_dialog.py`](../../../src/gui/dialogs/structured_report_browser_dialog.py): `_populate_event_table`, `_export_events_csv_xlsx` (headers = union of `row.columns` keys in first-seen order).

#### 1.6.2 Phase B — Unit columns (core + UI + export)

| Step | Task | Owner / file | Done |
|------|------|----------------|------|
| B1 | Add `_measurement_units_display_for_concept(items, code, notes)` (or extend `_best_num_for_concept` to return `(value, units)` with **one** shared selection pass) so **units string** matches the **same** `NUM` item as the numeric column. Format: prefer `CodeMeaning` from `MeasurementUnitsCodeSequence[0]`, else `CodeValue` + scheme; empty if missing. | `rdsr_irradiation_events.py` — shipped as `_best_num_item_for_concept` + `_measurement_units_display_from_num_item` | [x] |
| B2 | In `_build_event_columns`, insert **`DAP units`** immediately after **`DAP`**, and **`Dose (RP) units`** immediately after **`Dose (RP)`**, using the new helper for **122130** / **113738**. | same | [x] |
| B3 | If multiple `MeasuredValueSequence` entries exist for the winning `NUM`, join unit strings with **`; `** to mirror numeric `; ` join, or document “first MV only” in code comment — **pick one** and stay consistent. | same — **`; `** join implemented | [x] |
| B4 | **Tests:** extend [`tests/test_sr_document_tree.py`](../../../tests/test_sr_document_tree.py) (fixtures `xray_rdsr_ds` / `enhanced_rdsr_ds` and local `pyskindose_samples` skip-if-missing): assert **DAP** + **DAP units** / **Dose (RP) units** columns; **Gy**, **Gy.m2**, **Gym2** when present. | `tests/` | [x] |
| B5 | **Manual / local:** open `philips_allura_clarity_u104.dcm` or `siemens_axiom_artis.dcm` → SR browser → Dose events: confirm **DAP units** shows **Gy.m2** / **Gym2** and **Dose (RP) units** shows **Gy**. | human | [ ] |
| B6 | **Export parity:** export CSV/XLSX from the dialog; confirm new headers appear and unit cells match the table (no separate export path — `er.columns` drives both). | `structured_report_browser_dialog.py` — verify only unless headers need sorting | [x] |

**Acceptance (B):** Table and exported files show **numeric** and **unit** columns for **DAP** and **Dose (RP)**; values unchanged vs today; units match DICOM `MeasurementUnitsCodeSequence` for the selected `NUM`.

#### 1.6.3 Phase C — Validation `notes` (soft flags)

| Step | Task | Done |
|------|------|------|
| C1 | After resolving **113738** / **122130**, if numeric value is **non-empty** but **units string is empty**, append one note per **concept** per **event** (or dedupe: e.g. `"Event row N: DAP (122130) NUM has no MeasurementUnitsCodeSequence."`) — avoid flooding: cap **e.g. 10** similar notes per document. | [x] |
| C2 | **Optional heuristic (defer if noisy):** if units present and numeric **≤ 0** for these codes, append a single soft warning — many zeros are legitimate; **default off** unless product agrees. | [ ] *(deferred)* |
| C3 | **Tests:** one synthetic `NUM` without `MeasuredValueSequence` or without `MeasurementUnitsCodeSequence` triggers a **note** (assert substring in `extraction.notes`). | [x] |
| C4 | SR browser already surfaces `IrradiationEventExtraction.notes` — confirm new notes appear in the existing warnings UI (no new widget unless missing). | [x] |

**Acceptance (C):** Missing UCUM / units on **113738**/**122130** is visible in **notes**, not silent.

#### 1.6.4 Phase Export — explicit verification

| Step | Task | Done |
|------|------|------|
| E1 | Confirm **no** second code path builds dose-event rows for export (only `IrradiationEventRow.columns`). | [x] |
| E2 | If column **order** in the UI must match clinical expectation (DAP, DAP units, …), ensure `_build_event_columns` **insertion order** defines first-seen headers in `_populate_event_table`; adjust only if current dynamic-column merge breaks order. | [x] |
| E3 | **Regression:** existing RDSR tests + SR browser tests still pass. | [x] |

**Acceptance (export):** Exported **CSV/XLSX** column set and cell values **match** the on-screen dose-events table for the same dataset.

#### 1.6.5 Documentation and release

- [x] Follow [§3.0 — completion protocol](#completion-protocol): mark **§1.6** table `Done` cells and **§3** checkboxes when B/C/E ship.
- [x] [`CHANGELOG.md`](../../../CHANGELOG.md) **Unreleased** — user-visible: dose-events table **unit columns** + any **notes** behavior; reference **P0** RDSR UX.
- [x] [`AGENTS.md`](../../../AGENTS.md) or dev-docs only if behavior is non-obvious for future agents (optional).

---

<a id="p0-sr-clear-window-overlay"></a>

## 2. “Clear this window” on an SR pane — message and button remain

### 2.1 Goal

After **Clear this window** (context menu), the **no-pixel SR** bottom bar (**hint + “Open structured report…”**) must **hide** like other pane content, leaving an empty pane consistent with cleared windows.

### 2.2 Relevant code (findings)

| Area | Location | Notes |
|------|----------|--------|
| SR bar widget | [`src/gui/no_pixel_placeholder_overlay.py`](../../../src/gui/no_pixel_placeholder_overlay.py) | `configure(active=…)` controls visibility of hint + button. |
| Show/hide API | [`src/gui/image_viewer.py`](../../../src/gui/image_viewer.py) — `set_no_pixel_placeholder_bar` | Delegates to overlay `configure`. |
| When the bar is shown | [`src/core/slice_display_manager.py`](../../../src/core/slice_display_manager.py) — `_render_base_image_pipeline` | If `no_pixel_placeholder` and `Modality == "SR"`, calls `set_no_pixel_placeholder_bar(True, …)`; else **`False`**. |
| Clear pane | [`src/main.py`](../../../src/main.py) — `_clear_subwindow` | Clears scene, managers (including `slice_display_manager.clear_display_state()`), resets `subwindow_data`. |
| `clear_display_state` | [`src/core/slice_display_manager.py`](../../../src/core/slice_display_manager.py) | **Fixed (0.2.11):** after reset, calls `set_no_pixel_placeholder_bar(False)` so the SR no-pixel bar clears with the pane. |

**Prior root cause (fixed):** The overlay was driven only from the **display / render** path when a dataset was present; **clear** did not reset the bar until `clear_display_state` hid it explicitly.

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

- Context menu wires clear: [`src/core/subwindow_lifecycle_controller.py`](../../../src/core/subwindow_lifecycle_controller.py) (`clear_window_content_requested` → `app._on_clear_subwindow_content_requested`).

<a id="plan-sr-clear-overlay"></a>

### 2.6 Complete implementation plan — §2.3 **`clear_display_state`**

**Chosen approach:** **Preferred** — hide the SR / no-pixel bar inside [`SliceDisplayManager.clear_display_state()`](../../../src/core/slice_display_manager.py) so every path that clears display manager state (including [`DICOMViewerApp._clear_subwindow`](../../../src/main.py)) resets the overlay without duplicating calls in `main.py`.

#### 2.6.1 Preconditions

- [x] Confirm **all** callers of `clear_display_state()` are safe to hide the bar (e.g. closing a series on a **non-focused** subwindow should not leave a stale bar — hiding is always correct when there is no active slice render for that manager).
- [x] Grep for `clear_display_state` across `src/` and note any path where `image_viewer` might be in a transitional state.

#### 2.6.2 Implementation steps

| Step | Task | File | Done |
|------|------|------|------|
| S1 | At end of `clear_display_state()`, call `self.image_viewer.set_no_pixel_placeholder_bar(False)` (guard with `hasattr` / `getattr` only if needed for tests or partial mocks). | `slice_display_manager.py` | [x] |
| S2 | One-line comment: **why** (clear pane / close series must reset SR hint bar; render path alone does not run). | same | [x] |
| S3 | **Manual QA:** §2.4 steps 1–4 on Windows (and macOS if available). | human | [ ] |
| S4 | **Automated (optional):** If the project has a pattern for `QWidget` / `ImageViewer` unit tests, add a test that `clear_display_state()` leaves `NoPixelPlaceholderOverlay` inactive; otherwise document “manual only” in test ledger. | `tests/` or QA notes | [ ] |
| S5 | **Regression:** run targeted pytest for slice display / subwindow if present (`pytest tests/ -k …` with reasonable timeout). | CI / local | [x] |

#### 2.6.3 Acceptance

- After **Clear this window** on an SR-only pane, the bottom **Structured Report** hint and button are **gone**; reloading SR shows them again.
- **Close series** / **close study** clearing a pane that showed SR does not leave the bar visible on an empty viewer.

#### 2.6.4 Documentation and release

- [x] [`CHANGELOG.md`](../../../CHANGELOG.md) **Unreleased** — fix: SR placeholder bar clears with pane.
- [x] Follow [§3.0 — completion protocol](#completion-protocol): mark **§2.6.2** table `Done` cells and **§3.4** / **§3.5**, then [`TO_DO.md`](../../TO_DO.md) line 41.

---

<a id="master-checklist"></a>

## 3. Master to-do checklist (execution order)

Use this list for **tracking**; detailed sub-steps live in **§1.6** ([`#plan-dose-b-c-export`](#plan-dose-b-c-export)) and **§2.6** ([`#plan-sr-clear-overlay`](#plan-sr-clear-overlay)).

<a id="completion-protocol"></a>

### 3.0 Completion protocol — checkboxes in this plan + `TO_DO.md`

**Rule:** Keep **this plan** the source of truth for granular progress; [`TO_DO.md`](../../TO_DO.md) lines **40–41** reflect **product-level** closure of the two P0 tracks.

1. **As work completes (ongoing)**  
   - Turn `[ ]` → `[x]` for the matching items in **§3.1–§3.5** below.  
   - In **§1.6.2** and **§1.6.3**, set the **`Done`** column to **`[x]`** for each table row (B1–B6, C1–C4) when that step is finished.  
   - In **§2.6.2**, set **`Done`** to **`[x]`** for S1–S5 when finished.  
   - In **§1.6.1** preconditions and **§2.6.1** preconditions, check off when satisfied.  
   - If a step is **cancelled** or **explicitly deferred** (e.g. §1.6.3 **C2**), mark it `[x]` or `N/A` **in this plan only** and add a one-line note in **§3** or under the relevant subsection so the checklist does not look “stuck.”

2. **When the dose RP / units / export track is fully done** (§**3.2** + **3.3** as scoped, plus **3.5** items that apply to that release, e.g. CHANGELOG if shipping)  
   - Set [`TO_DO.md`](../../TO_DO.md) **line 40** from `- [ ]` to `- [x]`.  
   - Bump **`Last updated`** and append a short bullet under **`Changes`** for that edit.

3. **When the SR “Clear this window” track is fully done** (§**3.4** + relevant **3.5** items)  
   - Set [`TO_DO.md`](../../TO_DO.md) **line 41** from `- [ ]` to `- [x]`.  
   - Bump **`Last updated`** / **`Changes`** as above.

4. **When both tracks are done**  
   - Confirm every applicable **§3** box and **§1.6 / §2.6** table row is `[x]` or documented `N/A`.  
   - Both **TO_DO** lines **40** and **41** should be **`[x]`**.  
   - Optional: add a dated one-line “**Closed**” note at the top of this plan’s metadata block.

### 3.1 Investigation / research (done or optional)

- [x] **§1.3** — UCUM behavior documented on `pyskindose_samples` Philips/Siemens **88.67** RDSRs.  
- [ ] Optional: vendor PDF / additional vendors; optional **88.67** CI fixture under `tests/fixtures/` (§1.3.5).

### 3.2 Dose events — **B** (unit columns) + **Export** (§1.6.2, §1.6.4)

- [x] **B1–B3** — Core extraction: units helper + `_build_event_columns` inserts **DAP units** / **Dose (RP) units**.  
- [x] **B4** — Automated tests (`tests/test_sr_document_tree.py` or dedicated `test_rdsr_irradiation_events.py` if split later).  
- [ ] **B5** — Manual check on real local **88.67** sample.  
- [x] **B6** + **E1–E3** — Export CSV/XLSX matches table; regression suite green. *(Code path verified; optional human CSV export from dialog.)*

### 3.3 Dose events — **C** (validation notes) (§1.6.3)

- [x] **C1** — Missing `MeasurementUnitsCodeSequence` when numeric present → capped `notes`.  
- [ ] **C2** — Optional ≤0 heuristic (**defer** unless approved).  
- [x] **C3–C4** — Tests + confirm notes visible in SR browser.

### 3.4 SR “Clear this window” overlay (§2.6)

- [x] **S1–S2** — `clear_display_state()` calls `set_no_pixel_placeholder_bar(False)`.  
- [ ] **S3** — Manual QA §2.4.  
- [ ] **S4–S5** — Optional automated test + pytest subset. *(S5: irradiation + RDSR pytest subsets run.)*

### 3.5 Release hygiene

- [x] **CHANGELOG** — one or two bullets: dose-events unit columns + SR clear fix (when shipped).  
- [x] **`TO_DO.md` lines 40–41** — follow [§3.0](#completion-protocol): set **`[x]`** on line **40** when the dose track is done, line **41** when the SR-clear track is done; update **`Last updated`** / **`Changes`** each time you edit `TO_DO.md`.  
- [x] **Semantic version** — typically **patch** for SR clear (**bugfix**); **minor** if dose-events table is treated as user-visible feature enhancement (team choice). *(Shipped as **patch 0.2.11**.)*
