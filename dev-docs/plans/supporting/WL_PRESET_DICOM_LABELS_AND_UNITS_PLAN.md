# Window/Level DICOM Preset Labels and Units Plan

**Created:** 2026-05-30  
**Motivating issue:** A non-CT / non-HU dataset can still show `HU` for all `Window/Level Presets -> From DICOM` entries, and available DICOM explanation names from `(0028,1055)` are not used.

---

## Summary

Fix two related correctness issues in the DICOM-derived W/L preset menu:

1. Do not show fake `HU` unit labels for DICOM presets when the active dataset does not have a meaningful HU rescale unit.
2. Use DICOM `WindowCenterWidthExplanation` `(0028,1055)` values as the visible preset names when available; otherwise use simple numeric fallback labels such as `1`, `2`, `3`.

This is a display-labeling and metadata-interpretation fix. It should not change how window/level values are applied, converted, or persisted.

---

## Current Findings

### Incorrect HU fallback

- `src/core/wl_preset_catalog.py::storage_space_label()` currently returns:
  - `raw` for non-rescaled presets
  - the explicit unit when it is meaningful
  - **`HU` as the default fallback** for any other rescaled preset
- That means a DICOM-derived preset can be labeled `(HU)` even when:
  - the dataset is not CT
  - the inferred/display unit is unknown
  - the rescale type was intentionally hidden because it is non-meaningful for display

### DICOM explanation names are ignored

- `src/core/dicom_window_level.py::get_window_level_presets_from_dataset()` reads multi-valued `WindowCenter` and `WindowWidth`.
- It currently does **not** read `WindowCenterWidthExplanation` `(0028,1055)`.
- Current fallback naming is:
  - first preset: unnamed, later rendered as `From DICOM`
  - later presets: `Preset 2`, `Preset 3`, etc.
- In the reported case, `(0028,1055)` contains names like:
  - `NORMAL`
  - `HARDER`
  - `SOFTER`
- Those names should be used directly in the menu.

### Existing menu structure is otherwise sound

- The top-level source grouping is already good:
  - `From DICOM`
  - `Built-in`
  - `Custom`
- The bug is in the per-item names and unit suffixes inside that grouped menu, not in the menu structure itself.

---

## Desired Behavior

### Units

- Show `HU` only when the resolved display unit is actually `HU`.
- Show another meaningful unit such as `BQML` when that is the resolved unit.
- For rescaled presets with unknown, hidden, or non-meaningful units:
  - do **not** invent `HU`
  - omit the unit suffix instead
- Keep `raw` for raw-space presets.

Examples:

- `Lung (HU)`
- `SUV 0-5 (BQML)`
- `Brain T1 (raw)`
- `NORMAL`
- `SOFTER`
- `2`

Do not show:

- `From DICOM (HU)` for non-HU datasets
- `Preset 2 (HU)` unless the actual resolved unit is HU

### Names

- If `(0028,1055)` is present, use those values as the DICOM preset names.
- If `(0028,1055)` is absent, use numeric fallback labels:
  - `1`
  - `2`
  - `3`
- If only some explanation names are present, fill missing entries with numeric fallback labels by index.

### Scope boundary

- Keep top-level menu grouping unchanged.
- Do not redesign built-in or custom preset behavior in this fix.
- Do not change W/L math or preset application behavior unless required for label correctness.

---

## Implementation Plan

### 1. Extend DICOM preset extraction to read `(0028,1055)`

Update `src/core/dicom_window_level.py::get_window_level_presets_from_dataset()` to:

- parse `WindowCenterWidthExplanation` alongside `WindowCenter` and `WindowWidth`
- support multi-valued explanation strings the same way multi-valued WC/WW are handled
- align explanation values to preset index
- emit the explanation text as the preset name when available

Fallback behavior:

- no explanation available for a given preset -> use numeric label by 1-based index
- partial explanation list -> fill missing labels with numeric fallback

If enhanced multi-frame VOI functional-group fallback is used for WC/WW, preserve current extraction behavior and add explanation support only if the explanation is available in the same effective source path.

### 2. Remove the generic HU fallback for unknown rescaled units

Update `src/core/wl_preset_catalog.py` so:

- rescaled presets only show a unit suffix when the effective unit is meaningful and known
- unknown/hidden/non-meaningful rescaled units do not render as `HU`
- raw presets continue to render as `raw`

Implementation intent:

- keep `storage_space_label()` or equivalent helper as the source of truth
- change it so the "rescaled but unknown unit" case returns no display suffix rather than `HU`
- ensure menu label formatting and status label formatting both use the same corrected semantics

### 3. Keep menu rendering logic thin

Leave `src/gui/wl_preset_menu.py` as a renderer only.

- Do not move DICOM parsing into GUI code.
- Do not duplicate unit-decision logic in menu code.
- Let the catalog/extraction layer produce correct preset names and unit metadata.

### 4. Preserve preset-application behavior

Do not change:

- raw/rescaled conversion logic when applying a preset
- current-preset selection/index behavior
- grouping into `From DICOM`, `Built-in`, and `Custom`
- built-in modality tables, except insofar as they inherit corrected unit-label formatting

---

## Test Plan

Add or update targeted tests covering both extraction and label formatting.

### DICOM extraction tests

- dataset with 3 WC values, 3 WW values, and 3 explanation names returns:
  - `NORMAL`
  - `HARDER`
  - `SOFTER`
- dataset with multiple WC/WW values and no explanation names returns:
  - `1`
  - `2`
  - `3`
- dataset with partial explanation names fills missing entries with numeric fallback labels
- single-preset dataset with one explanation returns that explanation as the name

### Unit-label tests

- rescaled preset with `unit="HU"` shows `(HU)`
- rescaled preset with `unit="BQML"` shows `(BQML)`
- rescaled preset with `unit=None` does not show `(HU)`
- rescaled preset with `unit=""`, `UNSPECIFIED`, or `US` does not show `(HU)`
- raw preset still shows `(raw)`

### Integration/menu tests

- `populate_wl_preset_menu()` renders DICOM submenu entries with explanation-based names
- unnamed DICOM entries render with numeric labels
- checked/current item behavior remains unchanged
- applying a preset still uses the same WC/WW conversion path as before

---

## Acceptance Criteria

- A non-CT / non-HU dataset no longer shows fake `HU` suffixes in the DICOM W/L submenu.
- DICOM explanation names from `(0028,1055)` appear in the submenu when present.
- Unnamed DICOM presets display as `1`, `2`, `3`, etc. rather than generic `Preset 2` / `Preset 3`.
- Existing built-in/custom preset behavior remains intact.
- No regression in preset application, status updates, or menu grouping.
