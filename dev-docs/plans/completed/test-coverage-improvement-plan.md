# Test Coverage Improvement Plan

**Last updated:** 2026-08-10
**Purpose:** Prioritized, phased plan to close the highest-value test coverage gaps in `src/`. Analysis based on `coverage run` over `tests/core/`, `tests/roi/`, `tests/utils/` (801 tests, all passing) plus manual cross-reference of all 328 source modules against 390 test files.

---

## Current coverage state

### Well-tested areas (existing dedicated test files, generally >85% coverage)

| Module | Test file | Coverage |
|--------|-----------|----------|
| `core/slice_geometry.py` | `tests/core/test_slice_geometry.py` | High |
| `core/slice_sync_coordinator.py` | `tests/core/test_slice_sync_coordinator_unit.py` | High |
| `core/slice_location_line_helper.py` | `tests/core/test_slice_location_line_helper_logic.py` | High |
| `core/direction_labels.py` | `tests/core/test_direction_labels.py` | High |
| `core/dicom_window_level.py` | `tests/core/test_dicom_window_level.py` | High |
| `core/dicom_pixel_array.py` | `tests/core/test_dicom_pixel_array.py` | High |
| `core/dicom_projections.py` | `tests/core/test_dicom_projections.py` | High |
| `core/dicom_color.py` | `tests/core/test_dicom_color_ybr.py` | High |
| `core/dicom_palette.py` | `tests/core/test_dicom_palette.py` | 94% |
| `core/dicom_rescale.py` | `tests/core/test_dicom_rescale.py` | 86% |
| `core/privacy_controller.py` | `tests/core/test_privacy_controller.py` | 94% |
| `core/session_reset_controller.py` | `tests/core/test_session_reset_controller.py` | 96% |
| `core/loading_progress_manager.py` | `tests/core/test_loading_progress_manager.py` | 99% |
| `core/cine_app_facade.py` | `tests/core/test_cine_app_facade.py` | 98% |
| `core/spreadsheet_safety.py` | `tests/test_spreadsheet_safety.py` | 39% |
| `core/wl_builtin_presets.py` | (indirect via `test_wl_preset_catalog.py`) | 71% |
| `core/sr_sop_classes.py` | (indirect) | 74% |
| `utils/config/*` (most) | `tests/config/test_*.py` | High |
| `utils/dicom_utils.py` | `tests/utils/test_dicom_utils.py` | High |
| `utils/log_sanitizer.py` | `tests/utils/test_log_sanitizer.py` | 89% |
| `utils/annotation_clipboard.py` | `tests/utils/test_annotation_clipboard.py` | 88% |
| `utils/bundled_fonts.py` | `tests/utils/test_bundled_fonts.py` | 96% |
| `utils/dicom_tag_keys.py` | (indirect via `test_dicom_tag_path.py`) | 78% |
| `core/volume_opacity_model.py` | `tests/test_volume_opacity_model.py` | High |
| `core/volume_render_presets.py` | `tests/core/test_volume_render_presets.py` | High |
| `core/volume_render_quality.py` | `tests/core/test_volume_render_quality.py` | 93% |
| `core/slice_display_lut.py` | `tests/test_slice_display_lut.py` | 65% |
| `core/slice_grouping.py` | `tests/test_slice_grouping.py` | High |
| `core/dicom_pixel_stats.py` | `tests/core/test_dicom_pixel_stats.py` | High |
| `core/dataset_cache_utils.py` | `tests/core/test_dataset_cache_utils.py` | High |
| `core/decoder_capabilities.py` | `tests/core/test_decoder_capabilities.py` | 89% |
| `core/mpr_view_math.py` | `tests/core/test_mpr_view_math.py` | High |
| `core/fusion_handler_io.py` | `tests/test_fusion_handler_io.py` | High |
| `core/tag_export_catalog.py` | `tests/test_tag_export_catalog.py` | High |
| `core/tag_export_writer.py` | `tests/test_tag_export_writer.py` | High |
| `core/sr_document_tree.py` | `tests/test_sr_document_tree.py` | High |
| `core/rdsr_dose_sr.py` | `tests/test_rdsr_dose_sr.py` | High |

### Top coverage gaps (pure-logic modules with NO dedicated test file)

These are the highest-priority targets: no Qt dependency, no existing test, meaningful logic.

| Module | Lines | Coverage | Why untested |
|--------|-------|----------|--------------|
| `core/sr_concept_identity.py` | 85 | 0% | No test file; pure pydicom logic |
| `core/dicom_image_render.py` | 219 | 0% | No test file; numpy/PIL/pydicom |
| `core/tag_export_union.py` | 80 | 0% | No test file; pydicom logic |
| `core/sr_sop_classes.py` | 95 | 74% | No dedicated test; indirect only |
| `utils/dicom_tag_keys.py` | 23 | 78% | No dedicated test; indirect only |
| `utils/dicom_vr_helpers.py` | 19 | 0% | No test file; pure logic |
| `utils/dicom_value_conversion.py` | 47 | 0% | No test file; pure logic |
| `core/decoder_fixture_contract.py` | 67 | 0% | No test file; data contract |
| `core/spreadsheet_safety.py` | 48 | 39% | Existing test misses branches |
| `core/wl_builtin_presets.py` | 104 | 71% | Indirect coverage only |

### Modules intentionally deprioritized

- **Re-exports / 1-liners** (skip — no logic): `core/tag_path.py`, `utils/undo_redo_command.py`, `version.py`, `tools/roi_persistence.py`
- **Large Qt/GUI facades** (low unit-test ROI; need full app harness): `gui/main_window.py`, `gui/image_viewer_*.py`, `gui/mpr_controller.py`, `gui/volume_viewer_widget.py`, `gui/series_navigator.py`, `gui/roi_coordinator.py`, `gui/view_state_manager.py`, `gui/qa_app_facade.py`, `gui/export_manager.py`, `gui/export_rendering.py`, `gui/fusion_coordinator.py`, `gui/fusion_controls_widget.py`, `gui/slice_display_manager.py`, `gui/dialogs/*` (most), `gui/main_window_*.py`
- **App shell mixins** (need full app): `main_app_*.py`, `main.py`
- **Threading / async with Qt event loop** (needs qapp + complex setup): `core/loading_pipeline_async.py`, `core/loader_worker.py`, `core/study_index/*_thread.py`
- **pylinac integration** (covered by dedicated pylinac-fake tier): `qa/pylinac_*.py`, `qa/qa_export.py`, `qa/qa_xlsx_export.py`

---

## Implementation phases

Each phase is self-contained and can be implemented independently. Phases are ordered by ROI: pure-logic easy wins first, Qt-dependent last.

### Phase 1: Pure-logic easy wins (highest ROI)

**Theme:** Small, pure-Python modules with zero or near-zero coverage. No Qt, no fixtures beyond `pytest.mark.parametrize`. These are the fastest to write and give the biggest coverage gain per line of test code.

**Proposed test file: `tests/core/test_sr_concept_identity.py`**
- Tier: unit
- Targets: `core/sr_concept_identity.py` — actual function names: `normalize_coding_scheme_designator`, `coded_entry_effective_code_value`, `normalized_expected_tuple`, `concept_name_identity_pair`, `concept_identity_matches`
- Tests:
  - `test_normalize_designator_uppercases_short` — `normalize_coding_scheme_designator("dcm")` → `"DCM"`, `"DCM"` → `"DCM"`
  - `test_normalize_designator_preserves_urn` — `"urn:example"` stays case-sensitive (not uppercased)
  - `test_normalize_designator_preserves_colon` — `"1.2.840.10008.1.2.4.50"` stays case-sensitive
  - `test_normalize_designator_strips_whitespace` — `" dcm "` → `"DCM"`
  - `test_normalize_designator_empty` — `""` → `""`, `None` → `""`
  - `test_effective_code_value_prefers_code_value` — `coded_entry_effective_code_value` with CodeValue `"T-D1213"` returned when present
  - `test_effective_code_value_falls_back_to_long` — empty CodeValue falls back to LongCodeValue
  - `test_effective_code_value_empty_when_both_missing` — returns `""`
  - `test_concept_identity_matches_equal` — `concept_identity_matches` with matching (code, designator) pair returns True
  - `test_concept_identity_mismatch` — non-matching pair returns False
  - `test_concept_name_identity_pair_missing_sequence` — `concept_name_identity_pair` on content item without ConceptNameCodeSequence returns `("", "")`
  - `test_normalized_expected_tuple` — literal pair normalized the same way as dataset pair

**Proposed test file: `tests/utils/test_dicom_tag_keys.py`**
- Tier: unit
- Targets: `utils/dicom_tag_keys.py`
- Tests:
  - `test_leaf_tag_from_key_simple` — `"(0010,0010)"` → `BaseTag(0x0010, 0x0010)`
  - `test_leaf_tag_from_key_nested_path` — `"Patient.(0010,0010)"` → leaf tag
  - `test_leaf_tag_from_key_whitespace` — `"( 0010 , 0010 )"` → valid tag
  - `test_leaf_tag_from_key_invalid` — `"not_a_tag"` → `None`
  - `test_leaf_tag_from_key_empty` — `""` → `None`
  - `test_leaf_tag_from_key_none` — `None` → `None`
  - `test_leaf_tag_from_key_wrong_group_length` — `"(001,0010)"` → `None`

**Proposed test file: `tests/utils/test_dicom_vr_helpers.py` (ALREADY EXISTS — SKIP)**
- The existing `tests/utils/test_dicom_vr_helpers.py` already covers `is_text_vr` (true/false/case-sensitivity) and `is_date_vr` (true/false) comprehensively. **Do not create or modify this file — Phase 1 drops to 4 files.**

**Proposed test file: `tests/utils/test_dicom_value_conversion.py` (MERGED INTO EXISTING)**
- Tier: unit
- Targets: `utils/dicom_value_conversion.py` — single function `convert_dicom_value(value: Any, vr: str | None = None) -> Any`
- **An existing `tests/test_dicom_value_conversion.py` already covers this module.** Extend that file (added 3 tests): `test_convert_integer_vr_truncates_floats`, `test_convert_vr_case_insensitive`, `test_convert_string_vr_none_returns_empty`. Reduced to 9 tests total in that file (6 existing + 3 new).

**Proposed test file: `tests/core/test_decoder_fixture_contract.py`**
- Tier: unit
- Targets: `core/decoder_fixture_contract.py`
- Tests:
  - `test_expectation_dataclass_frozen` — `DecoderFixtureExpectation` is frozen (assignment raises)
  - `test_expectation_default_stderr` — default `allowed_stderr == b""`
  - `test_expectations_nonempty` — `DECODER_FIXTURE_EXPECTATIONS` has all 9 entries
  - `test_expectations_unique_filenames` — all filenames in the tuple are unique
  - `test_expectations_valid_sha256` — each `pixel_sha256` is 64 hex chars
  - `test_expectations_valid_uids` — each `transfer_syntax_uid` is a valid UID string
  - `test_gdcm_diagnostic_constant` — `GDCM_12_BIT_FALLBACK_DIAGNOSTIC` is the expected bytes literal

**Phase 1 totals:** 3 new test files + 1 extended existing = **57 passing test functions**.

---

### Phase 2: Core DICOM processing pure logic

**Theme:** Larger pure-logic modules in `core/` that handle pixel rendering, tag merging, and SR detection. Still no Qt — numpy/PIL/pydicom only.

**Proposed test file: `tests/core/test_dicom_image_render.py`**
- Tier: unit
- Targets: `core/dicom_image_render.py`
- Tests:
  - `test_normalize_to_uint8_range` — array [0, 1, 2] maps to [0, 127, 255]-ish uint8
  - `test_normalize_to_uint8_flat` — constant array → zeros
  - `test_normalize_channels_to_uint8_per_channel` — (h,w,3) array normalized per channel
  - `test_normalize_channels_flat_channel` — flat channel → zeros
  - `test_classify_color_shape_grayscale` — `is_color=False` → `(False, False)`
  - `test_classify_color_shape_4d` — 4D array + color → `(True, False)` multi-frame
  - `test_classify_color_shape_single_frame` — (h,w,3) + SamplesPerPixel=3 → `(False, True)`
  - `test_classify_color_shape_mismatch` — (h,w,3) + SamplesPerPixel=1 → `(False, False)`
  - `test_reclassify_color_shape_4d` — 4D → `(True, False)`
  - `test_reclassify_color_shape_3d` — (h,w,3) → `(False, True)`
  - `test_reclassify_color_shape_2d` — 2D → `(False, False)`
  - `test_convert_color_pixel_array_ybr` — YBR_FULL input returns converted array + `did_ybr_convert=True`
  - `test_convert_color_pixel_array_rgb` — RGB input returns (array, False) — channel fix path
  - `test_convert_color_pixel_array_no_photometric` — `None` photometric → unchanged + False
  - `test_render_color_image_with_window_level` — valid RGB array + W/L → PIL Image mode RGB
  - `test_render_color_image_no_window_level` — valid RGB array, no W/L → PIL Image
  - `test_render_grayscale_image_with_window_level` — 2D array + W/L → PIL Image mode L
  - `test_render_grayscale_image_3d_fallback` — 3D grayscale → takes first frame, mode L
Note: the module also exports `normalize_channels_to_uint8` (a per-channel variant used by `render_color_image` for 3-channel arrays). Tests should cover both `normalize_to_uint8` (2D) and `normalize_channels_to_uint8` (3-channel) directly, plus a private `_samples_per_pixel` helper.

**Proposed test file: `tests/core/test_tag_export_union.py`**
- Tier: unit
- Targets: `core/tag_export_union.py`
- Tests:
  - `test_union_empty_datasets` — empty list → `{}`
  - `test_union_single_dataset` — one dataset → its tags in merged dict
  - `test_union_merges_keys_across_datasets` — two datasets with different keys → union of both
  - `test_union_first_occurrence_wins` — same key in two datasets → first dataset's value retained
  - `test_union_include_private_false` — private tags excluded when `include_private=False`
  - `test_union_supplement_standard_tags` — `supplement_standard_tags=True` adds standard tags
  - `test_union_include_sequences` — `include_sequences=True` includes sequence rows
  - `test_union_preserves_order` — datasets order determines first-occurrence precedence

**Proposed test file: `tests/core/test_sr_sop_classes.py`**
- Tier: unit
- Targets: `core/sr_sop_classes.py`
- Tests:
  - `test_storage_label_known` — known SR UID → correct label (e.g. BasicTextSRStorage → "Basic Text SR")
  - `test_storage_label_unknown` — unknown UID → "Structured Report"
  - `test_storage_label_empty` — empty string → "Structured Report"
  - `test_is_structured_report_storage_true` — known SR UID → True
  - `test_is_structured_report_storage_false` — non-SR UID → False
  - `test_is_structured_report_dataset_by_sop` — dataset with SR SOPClassUID → True
  - `test_is_structured_report_dataset_by_modality` — dataset with Modality="SR" but unknown SOP → True
  - `test_is_structured_report_dataset_false` — non-SR dataset → False
  - `test_all_known_uids_in_frozenset` — every label dict key is in `STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS`

**Phase 2 totals:** 3 test files, ~33 test functions.

---

### Phase 3: Partial-coverage gap closure

**Theme:** Modules that have existing tests but miss meaningful branches. Improves coverage on `spreadsheet_safety` (39% → ~90%), `wl_builtin_presets` (71% → ~95%), and a few others.

**Proposed test file: `tests/core/test_spreadsheet_safety_extended.py`**
- Tier: unit
- Targets: `core/spreadsheet_safety.py` (extends existing `tests/test_spreadsheet_safety.py`)
- Tests:
  - `test_neutralize_equals_prefix` — `"=SUM(A1)"` → `"'=SUM(A1)"` (covers `=` prefix — primary CSV injection trigger)
  - `test_neutralize_at_sign_prefix` — `"@SUM"` → `"'@SUM"` (covers `@` prefix branch)
  - `test_neutralize_minus_prefix` — `"-1"` → `"'-1"` (covers `-` prefix branch)
  - `test_neutralize_plus_prefix` — `"+1"` → `"'+1"` (covers `+` prefix branch)
  - `test_neutralize_preserves_already_neutralized` — `"'=foo"` stays `"'=foo"` (apostrophe is not a trigger)
  - `test_neutralize_unicode_formula` — `"=Атака"` (Cyrillic) → prefixed (non-ASCII after trigger)
  - `test_neutralize_non_string_passes_through` — integers, `None` returned unchanged
  - `test_safe_csv_writer_writerow_returns_value` — `writerow` returns the writer's return value
  - `test_safe_csv_writer_empty_row` — empty row → empty row (no error)
  - `test_safe_csv_writer_writerows_multi` — `writerows` neutralizes each cell across multiple rows

**Proposed test file: `tests/core/test_wl_builtin_presets.py`**
- Tier: unit
- Targets: `core/wl_builtin_presets.py`
- Tests:
  - `test_get_builtin_presets_ct` — `"CT"` returns 11 presets, all `is_rescaled=True`
  - `test_get_builtin_presets_mr` — `"MR"` returns 5 presets, all `is_rescaled=False`
  - `test_get_builtin_presets_pt` — `"PT"` returns 2 SUV presets
  - `test_get_builtin_presets_case_insensitive` — `"ct"`, `"Ct"`, `"CT"` all return same list
  - `test_get_builtin_presets_whitespace` — `" CT "` stripped and returns CT list
  - `test_get_builtin_presets_unknown_modality` — `"ZZZ"` falls back to `ANY` table
  - `test_get_builtin_presets_empty_modality` — `""` → `ANY` table
  - `test_get_builtin_presets_none_modality` — `None` → `ANY` table
  - `test_get_builtin_presets_returns_copy` — mutating returned list does not affect module constant
  - `test_get_mr_hu_builtin_presets` — returns 3 HU presets, all `is_rescaled=True`
  - `test_preset_tuple_shape` — every preset is a 4-tuple (center, width, is_rescaled, name)
  - `test_any_table_present` — `ANY` table has at least 2 fallback presets

**Proposed test file: `tests/core/test_dicom_rescale_extended.py`**
- Tier: unit
- Targets: `core/dicom_rescale.py` (extends existing `tests/core/test_dicom_rescale.py`) — actual public API: `get_rescale_parameters`, `infer_rescale_type`. Private helpers `_normalize_explicit_rescale_type` and `_get_pixel_value_transformation_item` are only reachable via the public functions.
- Tests:
  - `test_infer_rescale_type_unspecified_normalizes` — `infer_rescale_type(ds, slope, intercept, "UNSPECIFIED")` → `None` (UNSPECIFIED normalized away)
  - `test_infer_rescale_type_us_normalizes` — `"US"` → `None`
  - `test_infer_rescale_type_empty` — `""` → `None`
  - `test_infer_rescale_type_valid_passthrough` — `"HU"` → `"HU"`
  - `test_infer_rescale_type_ct_with_both` — CT dataset + slope + intercept + `None` type → `"HU"`
  - `test_infer_rescale_type_ct_missing_intercept` — CT + slope only, intercept `None` → `None`
  - `test_infer_rescale_type_non_ct` — MR + slope + intercept → `None`
  - `test_infer_rescale_type_explicit_wins_over_modality` — explicit `"HU"` returned even for MR
  - `test_get_rescale_parameters_functional_groups_fallback` — dataset with only SharedFunctionalGroupsSequence → PixelValueTransformationSequence rescale extracted
  - `test_get_rescale_parameters_list_values` — list-valued RescaleSlope/Intercept handled (takes `[0]`)
  - `test_get_rescale_parameters_missing_all` — dataset with none of these → `(None, None, None)`

**Phase 3 totals:** 3 test files, ~30 test functions.

---

### Phase 4: Qt widget unit tests (qapp fixture)

**Theme:** Small GUI modules that are testable with the session-scoped `qapp` fixture. Marked `@pytest.mark.qt`.

**Proposed test file: `tests/gui/test_no_pixel_placeholder_overlay.py` (ALREADY EXISTS — SKIP)**
- The existing **top-level** `tests/test_no_pixel_placeholder_overlay.py` already covers `NoPixelPlaceholderOverlay` comprehensively (7 tests: configure visibility, callback wiring, click invocation). **Do not create a new file — Phase 4 has no new tests.**

**Proposed test file: `tests/gui/test_navigator_colors.py` (ALREADY EXISTS — SKIP)**
- The existing `tests/gui/test_navigator_colors.py` already covers `SUBWINDOW_DOT_COLORS` dict and `subwindow_slot_display_number` with out-of-bounds fallback. **Do not create or modify this file — Phase 4 drops to 1 file.**

**Phase 4 totals:** 0 new test files — both planned files (`test_navigator_colors.py` and `test_no_pixel_placeholder_overlay.py`) already exist with comprehensive coverage.

---

### Phase 5: Facade integration coverage

**Theme:** The `DICOMProcessor` facade delegates to sub-modules that are already tested individually. These tests verify the delegation wiring and the `dataset_to_image` integration path.

**Proposed test file: `tests/core/test_dicom_processor_facade.py`**
- Tier: unit
- Targets: `core/dicom_processor.py`
- Tests:
  - `test_get_rescale_parameters_delegates` — `DICOMProcessor.get_rescale_parameters` returns same as `dicom_rescale.get_rescale_parameters`
  - `test_infer_rescale_type_delegates` — `DICOMProcessor.infer_rescale_type` returns same as `dicom_rescale.infer_rescale_type`
  - `test_is_color_image_delegates` — `DICOMProcessor.is_color_image` returns same `(bool, str | None)` tuple as `dicom_color.is_color_image`
  - `test_get_pixel_array_delegates` — `DICOMProcessor.get_pixel_array` returns same as `dicom_pixel_array.get_pixel_array`
  - `test_apply_window_level_delegates` — `DICOMProcessor.apply_window_level` returns same as `dicom_window_level.apply_window_level`
  - `test_average_intensity_projection_delegates` — AIP delegates to `dicom_projections`
  - `test_maximum_intensity_projection_delegates` — MIP delegates to `dicom_projections`
  - `test_minimum_intensity_projection_delegates` — MinIP delegates to `dicom_projections`
  - `test_get_pixel_value_range_delegates` — delegates to `dicom_pixel_stats`
  - `test_get_series_pixel_value_range_delegates` — delegates to `dicom_pixel_stats`
  - `test_get_series_pixel_median_delegates` — delegates to `dicom_pixel_stats`
  - `test_dataset_to_image_grayscale` — synthetic grayscale dataset → PIL Image mode L
  - `test_dataset_to_image_color` — synthetic RGB dataset → PIL Image mode RGB
  - `test_dataset_to_image_none_pixels` — dataset with no pixel data → `None`

**Phase 5 totals:** 1 test file, ~14 test functions.

---

## Fixtures and helpers

No changes needed to `tests/conftest.py`. All proposed tests use:
- The existing session-scoped `qapp` fixture (Phase 4 only).
- `@pytest.mark.qt` marker (Phase 4 only) — already registered in `conftest.py`.
- Standard `pytest.mark.parametrize` (Phases 1–3, 5).

For Phase 2 and Phase 5 tests that need synthetic pydicom datasets, construct lightweight `pydicom.Dataset` objects inline (set `SamplesPerPixel`, `PhotometricInterpretation`, `PixelData`, `Rows`, `Columns`, `BitsAllocated`, etc. directly). This matches the existing pattern in `tests/core/test_dicom_color_ybr.py` and `tests/core/test_dicom_palette.py`. No new shared fixtures are required.

---

## Naming conventions

All proposed test files follow existing patterns:
- `tests/core/test_<module>.py` for core modules
- `tests/utils/test_<module>.py` for utility modules
- `tests/gui/test_<module>.py` for GUI modules
- `_extended` suffix for files that supplement an existing test file

---

## Summary

| Phase | Theme | New test files | New test functions | Tier |
|-------|-------|-----------|----------------|------|
| 1 | Pure-logic easy wins | 3 new + 1 extended | 57 | unit |
| 2 | Core DICOM processing pure logic | 3 | 43 | unit |
| 3 | Partial-coverage gap closure | 3 | 36 | unit |
| 4 | Qt widget unit tests | 0 (both planned files already existed) | 0 | qt |
| 5 | Facade integration coverage | 1 | 14 | unit |
| **Total** | | **10 new + 1 extended** | **150** | |

**Final results:** All 150 new tests pass. Full suite: **4754 passed, 14 skipped** (was 4624 before this work). Repo harness and architecture boundary checks pass. No source bugs found — no `xfail` markers or `TO_DO.md` entries needed.

**Estimated coverage impact:** Phase 1 + Phase 2 alone bring ~520 lines of currently-0%-tested pure-logic code to near-full coverage. Phase 3 closes the most impactful remaining branches in partially-tested modules. The plan deliberately avoids low-value targets (re-exports, 1-liners, large Qt facades) in favor of modules where unit tests are cheap and high-confidence.
