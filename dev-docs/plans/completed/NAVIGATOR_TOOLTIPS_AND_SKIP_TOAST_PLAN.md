# Navigator Tooltips + Duplicate-Skip Toast Plan

**Status:** **Shipped and archived** (see `CHANGELOG.md`: series navigator hover tooltips with privacy masking; duplicate-skip toast placement and opacity).

**Created:** 2026-03-21  
**Covers TO_DO items:**

1. Navigator hover tooltips for study labels and thumbnails (privacy-aware)
2. Duplicate-skip toast placement/style update (centered + more opaque)

---

## Goals

- Add informative hover tooltips in the series navigator:
  - Study label tooltip: study description, study date, patient name.
  - Thumbnail tooltip: same fields plus series description.
- Respect privacy mode in tooltip content.
- Adjust duplicate-skip toast UX:
  - Place it in screen center (not lower edge).
  - Increase background opacity slightly.

---

## Existing Behavior (Current State)

- Navigator widgets (`StudyLabel`, `SeriesThumbnail`) currently do not set tooltip text.
- Privacy mode exists at app level (`DICOMViewerApp.privacy_view_enabled`) and is propagated through a dedicated controller path.
- Duplicate-skip toast currently uses `MainWindow.show_toast_message(...)` with a bottom-center placement and RGBA background alpha of 0.75.
- Duplicate-skip toast is triggered from multiple code paths in `file_series_loading_coordinator.py`.

---

## Decisions To Confirm Before Implementation

1. Privacy masking scope for tooltip fields:
   - Option A (recommended): mask only patient name when privacy mode is on.
   - Option B: mask patient name + study description.
   - Keep behavior aligned with other privacy UI patterns in app.
2. Study date format:
   - Raw DICOM date (`YYYYMMDD`) or formatted human-readable (`YYYY-MM-DD`).
   - Recommendation: `YYYY-MM-DD` when parseable; fallback to raw.
3. Tooltip format style:
   - Plain text (recommended for native look), or rich text (`<b>Label:</b> value`).
4. Toast center anchor:
   - Center of the main window client area (recommended), not desktop/screen center.

---

## Detailed Implementation Steps

## 1. Navigator Tooltips (Privacy-Aware)

### 1.1 Add tooltip metadata extraction helpers in `series_navigator.py`

- Add private helper methods in `SeriesNavigator`:
  - `_format_study_date(value: object) -> str`
  - `_safe_dicom_text(dataset: Dataset, tag_name: str, fallback: str = "") -> str`
  - `_build_study_tooltip_text(dataset: Dataset) -> str`
  - `_build_series_tooltip_text(dataset: Dataset) -> str`
- Fields to read:
  - Study description: `StudyDescription`
  - Study date: `StudyDate`
  - Patient name: `PatientName`
  - Series description (thumbnail-only): `SeriesDescription`
- Normalize empty/missing values to `Unknown`.

### 1.2 Add privacy state to navigator

- Add member on `SeriesNavigator`, e.g. `self._privacy_mode_enabled = False`.
- Add public setter:
  - `set_privacy_mode(self, enabled: bool) -> None`
- In tooltip builders, when privacy is enabled:
  - Replace patient name with `PRIVACY MODE` (or selected final text).
- Keep study/series labels unaffected unless product decision says otherwise.

### 1.3 Set tooltips during `update_series_list(...)`

- When creating each `StudyLabel`, set tooltip built from the first dataset in that study.
- When creating each main `SeriesThumbnail`, set tooltip from that series first dataset.
- For instance thumbnails (when expanded), also set tooltip:
  - Reuse series tooltip + optionally add instance label/slice index line.

### 1.4 Refresh tooltip content when privacy changes

- Wire app privacy toggle flow to update navigator privacy state and refresh visible tooltips.
- Recommended minimal approach:
  - In `main.py` inside `_on_privacy_view_toggled`, call:
    - `self.series_navigator.set_privacy_mode(enabled)`
    - `self.series_navigator.update_series_list(...)` using current state
    - existing navigator state refresh calls afterward.
- Alternative approach (optional): add `SeriesNavigator.refresh_tooltips_only()` to avoid full rebuild.

### 1.5 Keep tooltip text generation centralized

- Avoid duplicating string formatting logic in `StudyLabel` and `SeriesThumbnail` classes.
- Build text in `SeriesNavigator`, pass string into widgets, and call `setToolTip(...)` there.

---

## 2. Duplicate-Skip Toast (Center + More Opaque)

### 2.1 Extend `MainWindow.show_toast_message(...)` API safely

- Keep existing behavior as default to avoid breaking current callers.
- Add optional parameters, e.g.:
  - `position: str = "bottom-center"`
  - `bg_alpha: float = 0.75`
- Clamp alpha to [0.0, 1.0].
- Build stylesheet RGBA alpha from parameter.

### 2.2 Add centered placement mode

- In `show_toast_message(...)`, placement rules:
  - `bottom-center`: current behavior (`y = self.height() - 100`).
  - `center`: `x = (self.width() - label.width()) // 2`, `y = (self.height() - label.height()) // 2`.
- Ensure label is raised above content and remains within window bounds.

### 2.3 Update duplicate-skip toast call sites only

- In `file_series_loading_coordinator.py`, update duplicate-skip calls to:
  - `show_toast_message(..., position="center", bg_alpha=0.85)`
- Do not change unrelated toasts unless explicitly requested.

### 2.4 Optional cleanup: single helper for duplicate-skip toast

- Add small coordinator helper method:
  - `_show_duplicate_skip_toast(app, skipped_count)`
- Use this helper from all duplicate-skip branches to prevent callsite drift.

---

## Testing Checklist

## Manual UX checks

1. Load multiple studies/series and hover study labels.
2. Hover series thumbnails and expanded instance thumbnails.
3. Confirm tooltip lines show expected fields and fallback text for missing tags.
4. Toggle privacy mode ON:
   - Patient name masked in both label and thumbnail tooltips.
5. Toggle privacy mode OFF:
   - Original patient name visible again.
6. Trigger duplicate-skip scenario by loading already-loaded files:
   - Toast appears centered.
   - Background opacity visibly stronger than current baseline.
7. Resize main window while toast is visible:
   - Toast remains in reasonable position (no severe clipping/offscreen placement).

## Regression checks

1. Navigator selection, drag/drop, and context menu behavior remain unchanged.
2. Series navigator rebuild performance remains acceptable for large study sets.
3. Existing non-duplicate toasts still render as before.

---

## Risks and Things To Be Careful About

1. Privacy consistency risk:
   - Tooltips can become a data-leak path if not updated on privacy toggle.
2. Performance risk:
   - Rebuilding whole navigator on each privacy toggle may be heavier with many thumbnails.
   - Acceptable initially; optimize to tooltip-only refresh if needed.
3. Multi-source duplicate-skip toasts:
   - Several branches trigger this message; missing one leads to inconsistent UX.
4. Tooltip content source:
   - First dataset in a series should be used consistently to avoid random metadata changes.
5. DICOM date parsing:
   - Some values may be malformed; formatting helper must fail safely.

---

## Suggested Delivery Order

1. Toast API extension + duplicate-skip callsite updates (small, self-contained).
2. Navigator tooltip helpers + basic tooltip assignment.
3. Privacy wiring for tooltip masking + refresh behavior.
4. Manual validation pass with privacy and duplicate-load scenarios.

---

## Files Expected To Change (Implementation Phase)

- `src/gui/series_navigator.py`
- `src/main.py`
- `src/gui/main_window.py`
- `src/core/file_series_loading_coordinator.py`

Implementation completed in the files above; this document is kept for design history.
