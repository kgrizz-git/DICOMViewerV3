# Design Spec: Raising Test Coverage for Utility Modules

**Date:** 2026-08-05  
**Status:** Approved by User  
**Target files:**
- `src/utils/accent_presets.py`
- `src/utils/dicom_vr_helpers.py`
- `src/utils/navigation_slider_prefs.py`

**Test files to create:**
- `tests/utils/test_accent_presets.py`
- `tests/utils/test_dicom_vr_helpers.py`
- `tests/utils/test_navigation_slider_prefs.py`

---

## 1. Objectives & Guidelines

*   **Test Isolation:** All tests must be unit-level tests, targeting the specific module's public function API.
*   **Aesthetic & Code Quality:** Conforming to modern Python conventions, using clean assertions, and avoiding any changes to production code in `src/`.
*   **Zero PHI/PII:** No real patient data or DICOM files will be added.
*   **Verification:** Ensure 100% of all tests pass and that overall coverage increases.

---

## 2. Test Specifications

### Module: `src/utils/accent_presets.py`
**Test File:** `tests/utils/test_accent_presets.py` (5 tests)
1.  `test_accent_presets_contain_expected_keys`: Asserts that `ACCENT_PRESETS` holds exactly the expected set of keys (`steel-blue`, `violet`, `navy`, `garnet`).
2.  `test_get_preset_returns_correct_preset_for_valid_ids`: Verifies that `get_preset` returns the corresponding `AccentPreset` named tuple for valid IDs.
3.  `test_get_preset_fallback_for_invalid_id`: Verifies that requesting an invalid/non-existent ID returns the default `steel-blue` preset.
4.  `test_get_preset_fallback_for_none_or_empty_string`: Verifies that calling `get_preset(None)` or `get_preset("")` safely returns the default preset.
5.  `test_accent_preset_attributes`: Validates the structure and field values of each `AccentPreset` (e.g., labels, hex color prefixes `#`).

### Module: `src/utils/dicom_vr_helpers.py`
**Test File:** `tests/utils/test_dicom_vr_helpers.py` (5 tests)
6.  `test_is_text_vr_returns_true_for_text_vrs`: Verifies that `is_text_vr` returns `True` for all designated text VRs (`LO`, `PN`, `SH`, `ST`, `LT`, `UT`, `CS`, `IS`, `DS`).
7.  `test_is_text_vr_returns_false_for_non_text_vrs`: Verifies that `is_text_vr` returns `False` for other VRs such as `OB`, `OW`, `FL`, `FD`, `DA`.
8.  `test_is_date_vr_returns_true_for_date_vrs`: Verifies that `is_date_vr` returns `True` for designated date VRs (`DA`, `TM`, `DT`).
9.  `test_is_date_vr_returns_false_for_non_date_vrs`: Verifies that `is_date_vr` returns `False` for non-date VRs such as `LO`, `PN`, `OB`.
10. `test_vr_helpers_case_sensitivity`: Asserts that lowercase strings like `"lo"` or `"da"` return `False` as DICOM VRs are uppercase.

### Module: `src/utils/navigation_slider_prefs.py`
**Test File:** `tests/utils/test_navigation_slider_prefs.py` (5 tests)
11. `test_normalize_slider_placement_valid`: Verifies valid placements (`bottom`, `top`, `left`, `right`) are normalized correctly and return the lowercase value.
12. `test_normalize_slider_placement_normalization`: Verifies that case and leading/trailing whitespace are stripped and normalized (e.g., `"  Bottom  "` -> `"bottom"`).
13. `test_normalize_slider_placement_invalid_fallback`: Verifies that invalid values, `None`, or empty strings fall back to the default `"bottom"`.
14. `test_normalize_slider_direction_valid`: Verifies valid directions (`first_at_start`, `first_at_end`) return the exact valid string.
15. `test_normalize_slider_direction_normalization_and_fallback`: Verifies that case/whitespace normalization works for directions, and invalid values/`None`/empty strings fall back to `"first_at_start"`.
