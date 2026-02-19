# Test history

**Last updated:** 2026-02-19 12:10 PM (update this date and time whenever this file is edited.)

---

## Instructions

- **When you update this file:** Update the "Last updated" line at the top with the current date and time (e.g. YYYY-MM-DD HH:MM or your preferred format).
- **When tests are run in the future:** Keep the same format. For each test entry:
  - Update the **Last run** sub-item with the date and time of the run.
  - Update the **Result** sub-item with a short summary (e.g. "All passed", "X passed, Y failed", failure details).
- **New tests:** Add new entries when new test modules or test cases are added; use the same sub-items (Summary, Last run, Result).

---

## Last full run

- **Date:** 2026-02-19 12:10 PM
- **Command:** `python -m pytest tests/ -v --tb=short` (from project root, with venv)
- **Result:** 44 passed in 5.33s

---

## Entries

### test_dicom_loader

- **Summary:** DICOM loader initialization, loading a non-existent file, and clearing loaded files (core.dicom_loader).
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 3 tests passed.

### test_dicom_parser

- **Summary:** DICOM parser initialization, get-all-tags with no dataset, get-tag-value with no dataset (core.dicom_parser).
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 3 tests passed.

### test_dicom_utils

- **Summary:** Pure DICOM utility functions: format_distance, pixels_to_mm, mm_to_pixels, is_patient_tag, get_patient_tag_keywords (utils.dicom_utils).
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 16 tests passed.

### test_export_manager

- **Summary:** ExportManager (core.export_manager) instantiation and process_image_by_photometric_interpretation (MONOCHROME1/2, empty/unknown photometric). Phase 1 refactor tests.
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 5 tests passed.

### test_main_window_theme

- **Summary:** Theme module (gui.main_window_theme): get_theme_stylesheet for dark/light/unknown, get_theme_viewer_background_color. Phase 1 refactor tests.
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 10 tests passed.

### test_measurement_items

- **Summary:** Measurement graphics items (tools.measurement_items): imports and re-exports from measurement_tool, MeasurementItem construction and distance, DraggableMeasurementText, MeasurementHandle. Phase 1 refactor tests.
- **Last run:** 2026-02-19 12:10 PM
- **Result:** All 7 tests passed.
