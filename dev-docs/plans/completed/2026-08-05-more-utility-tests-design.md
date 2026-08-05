# Design Spec: Extra Test Coverage for Utilities (Debug Flags, Bundled Fonts, ROI Persistence)

**Date:** 2026-08-05  
**Status:** Approved by User  
**Target files:**
- `src/utils/debug_flags.py`
- `src/utils/bundled_fonts.py`
- `src/utils/roi_persistence.py`

**Test files to create:**
- `tests/utils/test_debug_flags.py`
- `tests/utils/test_bundled_fonts.py`
- `tests/utils/test_roi_persistence.py`

---

## 1. Objectives & Guidelines

*   **Test Isolation:** All tests are unit-level, running under offscreen Qt rendering context.
*   **Zero PHI/PII:** No real patient data or real DICOM files.
*   **Verifications:** Tests verify correct default configuration states, API fallback conditions, and serialization outputs.

---

## 2. Test Specifications

### Module: `src/utils/debug_flags.py`
**Test File:** `tests/utils/test_debug_flags.py` (5 tests)
1.  `test_all_debug_flags_default_to_false`: Inspects all variables starting with `DEBUG_` in `utils.debug_flags` and asserts they are `False`.
2.  `test_perf_log_respects_env_disabled`: Verifies that `PERF_LOG` is `False` when the environment variable `DICOM_PERF_LOG` is not set or not `"1"`.
3.  `test_perf_log_respects_env_enabled`: Uses monkeypatch to set `DICOM_PERF_LOG=1` and reloads the module, verifying it turns `True`.
4.  `test_debug_flags_exclusivity`: Validates that no unexpected keys or variables are exported by the module.
5.  `test_debug_flags_type`: Asserts that all defined `DEBUG_*` flags are strictly of type `bool`.

### Module: `src/utils/bundled_fonts.py`
**Test File:** `tests/utils/test_bundled_fonts.py` (5 tests)
6.  `test_get_font_families`: Verifies `get_font_families` returns a non-empty list containing `DEFAULT_FONT_FAMILY`.
7.  `test_get_font_variants`: Verifies list of variant names is returned, and falls back to default variants for unknown family.
8.  `test_resolve_font_with_fallback`: Verifies fallback logic for unknown family and unknown variant.
9.  `test_get_bundled_ttf_path`: Checks that the returned path is a string pointing to a `.ttf` filename extension.
10. `test_make_qfont_valid_and_invalid`: Asserts that `make_qfont` creates a `QFont` object with expected family/size/weight and fallback properties.

### Module: `src/utils/roi_persistence.py`
**Test File:** `tests/utils/test_roi_persistence.py` (5 tests)
11. `test_serialize_roi_rect`: Duck-types an ROI rect object and asserts that `serialize_roi_for_clipboard` maps coordinates and sizes correctly.
12. `test_serialize_roi_ellipse`: Duck-types an ROI ellipse object and verifies correct mapping.
13. `test_serialize_roi_with_statistics`: Duck-types an ROI with a `visible_statistics` attribute and asserts it is serialized as a list.
14. `test_serialize_roi_pen_width_fallback`: Checks pen width fallback logic when floating-point precision pen width is 0 or negative.
15. `test_serialize_rois_list`: Verifies `serialize_rois_for_clipboard` serializes multiple ROIs correctly.
