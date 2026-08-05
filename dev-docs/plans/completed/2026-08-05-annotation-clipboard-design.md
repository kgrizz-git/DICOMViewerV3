# Design Spec: Raising Test Coverage for Annotation Clipboard

**Date:** 2026-08-05  
**Status:** Approved by User  
**Target files:**
- `src/utils/annotation_clipboard.py`

**Test files to create:**
- `tests/utils/test_annotation_clipboard.py`

---

## 1. Objectives & Guidelines

*   **Test Isolation:** All tests must target the `AnnotationClipboard` class, validating the serialization and deserialization functions.
*   **Zero PHI/PII:** No real patient data or real DICOM files.
*   **Verification:** Ensure all tests pass cleanly under offscreen Qt rendering.

---

## 2. Test Specifications

### Module: `src/utils/annotation_clipboard.py`
**Test File:** `tests/utils/test_annotation_clipboard.py` (15 tests)
1.  `test_clipboard_initial_state`: Asserts that `clipboard_data`, `source_slice_key`, and `has_data()` are None/False when initialized.
2.  `test_clipboard_clear`: Asserts that `clear` resets the internal state to None/False/copy.
3.  `test_clipboard_copy_empty`: Asserts that copying empty lists produces a dictionary with the correct structure and empty lists.
4.  `test_paste_annotations`: Asserts that `paste_annotations` returns None initially and returns the copied dictionary after `copy_annotations`.
5.  `test_get_source_slice_key`: Asserts that `get_source_slice_key` matches the values passed to `copy_annotations`.
6.  `test_get_paste_offset_different_slice`: Asserts that the offset is `(0.0, 0.0)` for a different slice key.
7.  `test_get_paste_offset_same_slice_cut`: Asserts that the offset is `(0.0, 0.0)` on the same slice when the operation is `"cut"`.
8.  `test_get_paste_offset_same_slice_copy`: Asserts that the offset is `(10.0, 10.0)` on the same slice when the operation is `"copy"`.
9.  `test_serialize_distance_measurement`: Mocks a distance measurement object (with `start_point`, `end_point`, `pixel_spacing`) and asserts that it serializes correctly.
10. `test_serialize_angle_measurement`: Mocks an angle measurement object (with `p1`, `p2`, `p3`, `text_offset_viewport`) and asserts that it serializes correctly.
11. `test_serialize_crosshairs`: Mocks crosshair objects (with `position`, `pixel_value_str`, `x_coord`, `y_coord`, `z_coord`, `text_offset_viewport`) and asserts correct serialization.
12. `test_serialize_text_annotations`: Mocks text annotations (with `toPlainText()`, `pos()`, `defaultTextColor()`, `font()`) and asserts correct serialization.
13. `test_serialize_arrow_annotations`: Mocks arrow annotations (with `start_point`, `end_point`, `color`) and asserts correct serialization.
14. `test_serialize_rois_delegation`: Asserts that ROIs are serialized correctly by mocking/substituting `serialize_rois_for_clipboard`.
15. `test_has_data_state_transitions`: Verifies the transitions of `has_data()` before copying, after copying, and after clearing.
