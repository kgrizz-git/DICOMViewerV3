from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from pydicom.dataset import Dataset

from core.slice_window_level_resolver import (
    _apply_rescale_and_store_defaults,
    _build_presets_and_extract_wl,
    _compute_pixel_range_wl,
    _compute_wl_from_series_pixel_range,
    _compute_wl_from_single_slice,
    _init_new_series_state,
    _restore_user_wl_cache,
    _set_rescale_toggle_state,
    _store_wl_and_defaults,
    compute_series_transition_state,
    resolve_window_level_for_series_transition,
)


class _ToggleTarget:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    def set_rescale_toggle_state(self, checked: bool) -> None:
        self.calls.append(checked)


def _make_dataset(study_uid="study1", series_uid="series1", series_number=1, modality="CT"):
    ds = Dataset()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.SeriesNumber = series_number
    ds.Modality = modality
    return ds


def _make_mgr(**overrides):
    view_state_manager = SimpleNamespace(
        save_user_window_level=MagicMock(),
        use_rescaled_values=False,
        main_window=MagicMock(),
        set_current_series_identifier=MagicMock(),
        current_window_center=None,
        current_window_width=None,
        window_level_user_modified=False,
        window_level_presets=None,
        _wl_preset_objects=None,
        current_preset_index=None,
        series_pixel_min=None,
        series_pixel_max=None,
        set_series_pixel_range=MagicMock(),
        clear_series_pixel_range=MagicMock(),
        series_defaults={},
        get_user_window_level=MagicMock(return_value=None),
        current_series_identifier="",
        is_new_study_or_series=MagicMock(return_value=True),
        get_series_identifier=MagicMock(return_value="study1:series1"),
        window_level_controls=SimpleNamespace(unit="HU"),
    )
    dicom_processor = MagicMock()
    dicom_processor.get_window_level_presets_from_dataset.return_value = []
    dicom_processor.get_window_level_from_dataset.return_value = (None, None, False)
    dicom_processor.get_series_pixel_value_range.return_value = (None, None)
    dicom_processor.get_series_pixel_median.return_value = None
    dicom_processor.get_pixel_value_range.return_value = (None, None)
    dicom_processor.get_pixel_array.return_value = None
    dicom_processor.get_rescale_parameters.return_value = (None, None, None)

    config_manager = MagicMock()
    config_manager.get_wl_user_presets.return_value = []

    image_viewer = SimpleNamespace(
        current_zoom=1.0,
        image_inverted=False,
        set_rescale_toggle_state=MagicMock(),
    )

    mgr = SimpleNamespace(
        view_state_manager=view_state_manager,
        dicom_processor=dicom_processor,
        config_manager=config_manager,
        image_viewer=image_viewer,
        measurement_tool=MagicMock(),
    )
    for key, value in overrides.items():
        setattr(mgr, key, value)
    return mgr


class TestSetRescaleToggleState:
    def test_updates_main_window_and_image_viewer_when_present(self):
        main_window = _ToggleTarget()
        image_viewer = _ToggleTarget()
        mgr = _make_mgr()
        mgr.view_state_manager.main_window = main_window
        mgr.image_viewer = image_viewer
        _set_rescale_toggle_state(mgr, True)
        assert main_window.calls == [True]
        assert image_viewer.calls == [True]

    def test_noop_when_targets_missing_method(self):
        mgr = _make_mgr()
        mgr.view_state_manager.main_window = object()
        mgr.image_viewer = object()
        _set_rescale_toggle_state(mgr, True)  # should not raise

    def test_noop_when_main_window_is_none(self):
        mgr = _make_mgr()
        mgr.view_state_manager.main_window = None
        mgr.image_viewer = object()
        _set_rescale_toggle_state(mgr, True)  # should not raise


class TestInitNewSeriesState:
    def test_updates_injected_toggle_targets(self) -> None:
        main_window = _ToggleTarget()
        image_viewer = _ToggleTarget()
        mgr = _make_mgr()
        mgr.view_state_manager.main_window = main_window
        mgr.image_viewer = image_viewer
        mgr.view_state_manager.current_window_center = 5.0
        mgr.view_state_manager.current_window_width = 10.0
        mgr.view_state_manager.window_level_user_modified = True

        _init_new_series_state(
            mgr,
            dataset=object(),
            rescale_slope=2.0,
            rescale_intercept=1.0,
            series_identifier="study:series",
        )

        assert mgr.view_state_manager.use_rescaled_values is True
        assert main_window.calls == [True]
        assert image_viewer.calls == [True]
        mgr.view_state_manager.set_current_series_identifier.assert_called_once_with("study:series")
        assert mgr.view_state_manager.current_window_center is None
        assert mgr.view_state_manager.current_window_width is None
        assert mgr.view_state_manager.window_level_user_modified is False

    def test_use_rescaled_values_false_when_slope_or_intercept_missing(self):
        mgr = _make_mgr()
        _init_new_series_state(mgr, dataset=object(), rescale_slope=None, rescale_intercept=1.0, series_identifier="s")
        assert mgr.view_state_manager.use_rescaled_values is False


class TestBuildPresetsAndExtractWl:
    def test_returns_first_preset_when_available(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (40.0, 400.0, True, "Abdomen"),
            (300.0, 1500.0, True, "Bone"),
        ]
        ds = _make_dataset()
        wc, ww, is_rescaled = _build_presets_and_extract_wl(mgr, ds, 1.0, 0.0, "embedded")
        assert (wc, ww, is_rescaled) == (40.0, 400.0, True)
        assert mgr.view_state_manager.current_preset_index == 0
        assert mgr.view_state_manager.window_level_user_modified is False

    def test_falls_back_to_get_window_level_from_dataset_when_no_presets(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = []
        mgr.dicom_processor.get_window_level_from_dataset.return_value = (50.0, 350.0, False)
        ds = _make_dataset()
        wc, ww, is_rescaled = _build_presets_and_extract_wl(mgr, ds, None, None, "fallback")
        assert (wc, ww, is_rescaled) == (50.0, 350.0, False)

    def test_stores_merged_presets_on_view_state_manager(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (40.0, 400.0, True, "Abdomen"),
        ]
        ds = _make_dataset()
        _build_presets_and_extract_wl(mgr, ds, 1.0, 0.0, "embedded")
        assert mgr.view_state_manager.window_level_presets is not None
        assert mgr.view_state_manager._wl_preset_objects is not None


class TestComputePixelRangeWl:
    def test_returns_series_pixel_range_and_sets_it(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_value_range.return_value = (0.0, 100.0)
        ds = _make_dataset()
        result = _compute_pixel_range_wl(mgr, ds, [ds], use_rescaled_values=False)
        assert result == (None, None, 0.0, 100.0)
        mgr.view_state_manager.set_series_pixel_range.assert_called_once_with(0.0, 100.0)

    def test_clears_range_and_returns_none_on_exception(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_value_range.side_effect = RuntimeError("boom")
        ds = _make_dataset()
        result = _compute_pixel_range_wl(mgr, ds, [ds], use_rescaled_values=False)
        assert result == (None, None, None, None)
        mgr.view_state_manager.clear_series_pixel_range.assert_called_once()


class TestComputeWlFromSeriesPixelRange:
    def test_uses_max_of_median_and_midpoint(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_median.return_value = 80.0
        wc, ww = _compute_wl_from_series_pixel_range(mgr, [_make_dataset()], 0.0, 100.0, False)
        assert wc == 80.0  # median (80) > midpoint (50)
        assert ww == 100.0

    def test_falls_back_to_midpoint_when_median_none(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_median.return_value = None
        wc, ww = _compute_wl_from_series_pixel_range(mgr, [_make_dataset()], 0.0, 100.0, False)
        assert wc == 50.0
        assert ww == 100.0

    def test_falls_back_to_midpoint_when_no_series_datasets(self):
        mgr = _make_mgr()
        wc, ww = _compute_wl_from_series_pixel_range(mgr, [], 0.0, 100.0, False)
        assert wc == 50.0
        assert ww == 100.0

    def test_width_clamped_to_one_when_non_positive(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_median.return_value = None
        wc, ww = _compute_wl_from_series_pixel_range(mgr, [_make_dataset()], 50.0, 50.0, False)
        assert ww == 1.0


class TestComputeWlFromSingleSlice:
    def test_returns_none_when_pixel_range_unavailable(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (None, None)
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert (wc, ww) == (None, None)

    def test_uses_pixel_array_median_when_available(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_pixel_array.return_value = np.array([[0, 0], [80, 90]], dtype=np.float32)
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert wc == 85.0  # median of nonzero [80, 90] = 85, midpoint = 50, max = 85
        assert ww == 100.0

    def test_applies_rescale_to_pixel_array_when_requested(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_pixel_array.return_value = np.array([[10, 20]], dtype=np.float32)
        mgr.dicom_processor.get_rescale_parameters.return_value = (2.0, 5.0, None)
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), True)
        # rescaled array = [25, 45]; midpoint of (0,100)=50; median=35; max(35,50)=50
        assert wc == 50.0

    def test_falls_back_to_midpoint_when_pixel_array_none(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_pixel_array.return_value = None
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert wc == 50.0
        assert ww == 100.0

    def test_width_clamped_to_one_when_non_positive(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (50.0, 50.0)
        mgr.dicom_processor.get_pixel_array.return_value = None
        _, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert ww == 1.0

    def test_returns_none_none_on_exception(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.side_effect = RuntimeError("boom")
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert (wc, ww) == (None, None)

    def test_skips_rescale_conversion_when_rescale_params_unavailable(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_pixel_array.return_value = np.array([[80, 90]], dtype=np.float32)
        mgr.dicom_processor.get_rescale_parameters.return_value = (None, None, None)
        wc, ww = _compute_wl_from_single_slice(mgr, _make_dataset(), True)
        assert wc == 85.0
        assert ww == 100.0

    def test_all_zero_pixel_array_falls_back_to_midpoint(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_pixel_array.return_value = np.zeros((2, 2), dtype=np.float32)
        wc, _ = _compute_wl_from_single_slice(mgr, _make_dataset(), False)
        assert wc == 50.0


class TestApplyRescaleAndStoreDefaults:
    def test_returns_none_none_when_wc_or_ww_none(self):
        mgr = _make_mgr()
        result = _apply_rescale_and_store_defaults(mgr, None, 100.0, True, False, 1.0, 0.0, "")
        assert result == (None, None)

    def test_passes_through_unchanged_when_spaces_match(self):
        mgr = _make_mgr()
        wc, ww = _apply_rescale_and_store_defaults(mgr, 40.0, 400.0, False, False, None, None, "")
        assert (wc, ww) == (40.0, 400.0)

    def test_converts_rescaled_to_raw_when_needed(self):
        mgr = _make_mgr()
        mgr.dicom_processor.convert_window_level_rescaled_to_raw.return_value = (20.0, 400.0)
        wc, ww = _apply_rescale_and_store_defaults(
            mgr, 40.0, 400.0, is_rescaled=True, use_rescaled_values=False,
            rescale_slope=2.0, rescale_intercept=0.0, debug_label="",
        )
        assert (wc, ww) == (20.0, 400.0)


class TestStoreWlAndDefaults:
    def test_stores_current_wl_and_series_defaults(self):
        mgr = _make_mgr()
        _store_wl_and_defaults(mgr, 40.0, 400.0, True, "study:series")
        assert mgr.view_state_manager.current_window_center == 40.0
        assert mgr.view_state_manager.current_window_width == 400.0
        assert mgr.view_state_manager.series_defaults["study:series"]["window_center"] == 40.0
        assert mgr.view_state_manager.series_defaults["study:series"]["use_rescaled_values"] is True
        mgr.view_state_manager.main_window.update_zoom_preset_status.assert_called_once()

    def test_reuses_existing_series_defaults_entry(self):
        mgr = _make_mgr()
        mgr.view_state_manager.series_defaults["study:series"] = {"existing": True}
        _store_wl_and_defaults(mgr, 40.0, 400.0, False, "study:series")
        assert mgr.view_state_manager.series_defaults["study:series"]["existing"] is True
        assert mgr.view_state_manager.series_defaults["study:series"]["window_center"] == 40.0


class TestRestoreUserWlCache:
    def test_returns_none_none_when_no_cache_hit(self):
        mgr = _make_mgr()
        mgr.view_state_manager.get_user_window_level.return_value = None
        assert _restore_user_wl_cache(mgr, "study:series") == (None, None)

    def test_restores_cached_wl_and_marks_user_modified(self):
        mgr = _make_mgr()
        mgr.view_state_manager.get_user_window_level.return_value = {
            "window_center": 60.0, "window_width": 300.0,
        }
        wc, ww = _restore_user_wl_cache(mgr, "study:series")
        assert (wc, ww) == (60.0, 300.0)
        assert mgr.view_state_manager.current_window_center == 60.0
        assert mgr.view_state_manager.window_level_user_modified is True


class TestComputeSeriesTransitionState:
    def test_same_series_detected(self):
        mgr = _make_mgr()
        mgr.view_state_manager.current_series_identifier = "prev-id"
        mgr.view_state_manager.is_new_study_or_series.return_value = False
        mgr.view_state_manager.get_series_identifier.return_value = "study1:series1"
        ds = _make_dataset(series_uid="series1", series_number=1)
        new_uid, is_same, is_new, series_id = compute_series_transition_state(mgr, ds, "series1_1", 0)
        assert is_same is True
        assert is_new is False
        assert series_id == "study1:series1"

    def test_different_series_detected(self):
        mgr = _make_mgr()
        mgr.view_state_manager.is_new_study_or_series.return_value = True
        ds = _make_dataset(series_uid="series2", series_number=1)
        new_uid, is_same, is_new, _ = compute_series_transition_state(mgr, ds, "series1_1", 0)
        assert is_same is False
        assert is_new is True

    def test_empty_current_series_uid_is_not_same_series(self):
        mgr = _make_mgr()
        ds = _make_dataset(series_uid="series1", series_number=1)
        new_uid, is_same, _, _ = compute_series_transition_state(mgr, ds, "", 0)
        assert is_same is False


class TestResolveWindowLevelForSeriesTransition:
    def test_same_series_keeps_existing_window_level(self):
        mgr = _make_mgr()
        mgr.view_state_manager.current_window_center = 40.0
        mgr.view_state_manager.current_window_width = 400.0
        mgr.view_state_manager.use_rescaled_values = True
        ds = _make_dataset()
        wc, ww, use_rescaled = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={}, current_series_uid="series1_1",
            new_series_uid="series1_1", is_same_series=True, is_new_study_series=False,
            series_identifier="study1:series1", rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (40.0, 400.0)
        assert use_rescaled is True

    def test_new_series_uses_embedded_preset_from_series_dict(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (40.0, 400.0, False, "Abdomen"),
        ]
        ds = _make_dataset()
        wc, ww, use_rescaled = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={"study1": {"series1_1": [ds]}},
            current_series_uid="", new_series_uid="series1_1", is_same_series=False,
            is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (40.0, 400.0)
        assert mgr.view_state_manager.series_defaults["study1:series1"]["window_center"] == 40.0

    def test_new_series_falls_back_to_series_pixel_range_when_no_embedded_wl(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_series_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_series_pixel_median.return_value = None
        ds = _make_dataset()
        wc, ww, _ = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={"study1": {"series1_1": [ds]}},
            current_series_uid="", new_series_uid="series1_1", is_same_series=False,
            is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert wc == 50.0
        assert ww == 100.0

    def test_new_series_falls_back_to_single_slice_when_series_not_in_dict(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (60.0, 200.0, False, "Fallback"),
        ]
        ds = _make_dataset()
        wc, ww, _ = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={}, current_series_uid="", new_series_uid="series1_1",
            is_same_series=False, is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (60.0, 200.0)

    def test_new_series_no_embedded_wl_in_fallback_returns_none(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (None, None)
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = []
        mgr.dicom_processor.get_window_level_from_dataset.return_value = (None, None, False)
        ds = _make_dataset()
        wc, ww, _ = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={}, current_series_uid="", new_series_uid="series1_1",
            is_same_series=False, is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (None, None)

    def test_new_series_restores_cached_user_wl(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (40.0, 400.0, False, "Abdomen"),
        ]
        mgr.view_state_manager.get_user_window_level.return_value = {
            "window_center": 99.0, "window_width": 999.0,
        }
        ds = _make_dataset()
        wc, ww, _ = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={"study1": {"series1_1": [ds]}},
            current_series_uid="", new_series_uid="series1_1", is_same_series=False,
            is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (99.0, 999.0)

    def test_new_series_uses_fallback_path_when_series_uid_not_in_study_dict(self):
        # study_uid is present in current_studies but new_series_uid is not one of
        # its series, so the "series in dict" branch is skipped even though the
        # outer "study_uid and new_series_uid and current_studies" check is True.
        mgr = _make_mgr()
        mgr.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (60.0, 200.0, False, "Fallback"),
        ]
        ds = _make_dataset()
        wc, ww, _ = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={"study1": {"other_series": [ds]}},
            current_series_uid="", new_series_uid="series1_1", is_same_series=False,
            is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert (wc, ww) == (60.0, 200.0)
        mgr.view_state_manager.set_series_pixel_range.assert_called_once_with(0.0, 100.0)

    def test_new_series_reuses_existing_series_defaults_entry_in_fallback(self):
        mgr = _make_mgr()
        mgr.view_state_manager.series_defaults["study1:series1"] = {"existing": True}
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = [
            (60.0, 200.0, False, "Fallback"),
        ]
        ds = _make_dataset()
        resolve_window_level_for_series_transition(
            mgr, ds, current_studies={}, current_series_uid="", new_series_uid="series1_1",
            is_same_series=False, is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=None, rescale_intercept=None,
        )
        assert mgr.view_state_manager.series_defaults["study1:series1"]["existing"] is True
        assert mgr.view_state_manager.series_defaults["study1:series1"]["window_center"] == 60.0

    def test_new_series_sets_use_rescaled_values_from_slope_and_intercept(self):
        mgr = _make_mgr()
        mgr.dicom_processor.get_window_level_presets_from_dataset.return_value = []
        mgr.dicom_processor.get_window_level_from_dataset.return_value = (None, None, False)
        ds = _make_dataset()
        _, _, use_rescaled = resolve_window_level_for_series_transition(
            mgr, ds, current_studies={}, current_series_uid="", new_series_uid="series1_1",
            is_same_series=False, is_new_study_series=True, series_identifier="study1:series1",
            rescale_slope=1.0, rescale_intercept=0.0,
        )
        assert use_rescaled is True
