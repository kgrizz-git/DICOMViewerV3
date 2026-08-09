# ruff: noqa: SIM117
"""Tests for FileSeriesLoadingCoordinator."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset

from gui.file_series_loading_coordinator import (
    FileSeriesLoadingCoordinator,
    _get_first_new_series_by_dicom,
    _show_duplicate_skip_toast,
    show_cancelled_index_skip_toast,
)


@pytest.fixture
def mock_app():
    """Create a mock app with all required attributes."""
    app = MagicMock()
    app.file_operations_handler = MagicMock()
    app.dicom_organizer = MagicMock()
    app.multi_window_layout = MagicMock()
    app.subwindow_managers = {}
    app.subwindow_data = {}
    app.slice_navigator = MagicMock()
    app.series_navigator = MagicMock()
    app.metadata_panel = MagicMock()
    app.dialog_coordinator = MagicMock()
    app.tag_edit_history = MagicMock()
    app.annotation_manager = MagicMock()
    app.intensity_projection_controls_widget = MagicMock()
    app.main_window = MagicMock()
    app.image_viewer = MagicMock()
    app.view_state_manager = MagicMock()
    app.slice_display_manager = MagicMock()
    app.roi_coordinator = MagicMock()
    app.current_dataset = None
    app.current_studies = {}
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.current_slice_index = 0
    app.current_datasets = []
    app.focused_subwindow_index = 0
    app.study_cache = None
    return app


@pytest.fixture
def coordinator(mock_app):
    """Create a FileSeriesLoadingCoordinator instance."""
    return FileSeriesLoadingCoordinator(mock_app)


class TestCoordinatorInit:
    """Test coordinator initialization."""

    def test_init_stores_app_reference(self, mock_app):
        coordinator = FileSeriesLoadingCoordinator(mock_app)
        assert coordinator.app is mock_app


class TestShowDuplicateSkipToast:
    """Test duplicate skip toast helper."""

    def test_shows_toast_with_skipped_count(self, mock_app):
        _show_duplicate_skip_toast(mock_app, 5)
        mock_app.main_window.show_toast_message.assert_called_once()
        args = mock_app.main_window.show_toast_message.call_args.args
        assert "5" in args[0]

    def test_no_toast_when_zero_skipped(self, mock_app):
        _show_duplicate_skip_toast(mock_app, 0)
        mock_app.main_window.show_toast_message.assert_not_called()


class TestShowCancelledIndexSkipToast:
    """Test cancelled index skip toast."""

    def test_shows_warning_toast(self, mock_app):
        show_cancelled_index_skip_toast(mock_app)
        mock_app.main_window.show_toast_message.assert_called_once()
        call_args = mock_app.main_window.show_toast_message.call_args
        assert call_args.kwargs["position"] == "center"
        assert call_args.kwargs["bg_alpha"] == 0.85
        assert call_args.kwargs["severity"] == "warning"
        assert "canceled" in call_args.args[0].lower()


class TestGetFirstNewSeriesByDicom:
    """Test _get_first_new_series_by_dicom helper."""

    def test_returns_none_when_new_series_empty(self):
        result = _get_first_new_series_by_dicom([], {})
        assert result is None

    def test_returns_none_when_current_studies_empty(self):
        result = _get_first_new_series_by_dicom([("study1", "series1")], {})
        assert result is None

    def test_returns_first_series_by_study_order(self):
        datasets = [Dataset()]
        datasets[0].SeriesNumber = 1
        studies = {
            "study1": {"series1": datasets},
            "study2": {"series2": datasets},
        }
        new_series = [("study1", "series1"), ("study2", "series2")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study1", "series1")

    def test_returns_lowest_series_number_in_study(self):
        ds1 = Dataset()
        ds1.SeriesNumber = 5
        ds2 = Dataset()
        ds2.SeriesNumber = 2
        studies = {
            "study1": {
                "series1": [ds1],
                "series2": [ds2],
            }
        }
        new_series = [("study1", "series1"), ("study1", "series2")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study1", "series2")

    def test_handles_missing_series_number(self):
        ds = Dataset()
        studies = {"study1": {"series1": [ds]}}
        new_series = [("study1", "series1")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study1", "series1")

    def test_handles_series_number_as_none(self):
        """Test handling when SeriesNumber is None (covers lines 164-165)."""
        ds = Dataset()
        # Don't set SeriesNumber at all, so it's None
        studies = {"study1": {"series1": [ds]}}
        new_series = [("study1", "series1")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        # When SeriesNumber is None, it defaults to 0, so it should still return the series
        assert result == ("study1", "series1")

    def test_handles_invalid_series_number_value_error(self):
        """Test handling when SeriesNumber raises ValueError."""
        ds = SimpleNamespace(SeriesNumber="invalid_string")
        studies = {"study1": {"series1": [ds]}}
        new_series = [("study1", "series1")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study1", "series1")

    def test_handles_invalid_series_number_type_error(self):
        """Test handling when SeriesNumber raises TypeError."""
        ds = SimpleNamespace(SeriesNumber=[])  # List cannot be converted to int
        studies = {"study1": {"series1": [ds]}}
        new_series = [("study1", "series1")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study1", "series1")

    def test_skips_studies_not_in_new_series(self):
        """Test that studies not in new_series are skipped (covers line 155)."""
        ds = Dataset()
        ds.SeriesNumber = 1
        # Put study2 first in the dict iteration order to ensure it's encountered
        studies = {
            "study2": {
                "series2": [ds]
            },  # This study is not in new_series and comes first
            "study1": {"series1": [ds]},
        }
        new_series = [("study1", "series1")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        # Should return the series from study1, skipping study2
        assert result == ("study1", "series1")

    def test_skips_empty_datasets(self):
        studies = {
            "study1": {"series1": []},
            "study2": {"series2": [Dataset()]},
        }
        new_series = [("study1", "series1"), ("study2", "series2")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result == ("study2", "series2")

    def test_returns_none_if_all_datasets_empty(self):
        studies = {
            "study1": {"series1": []},
            "study2": {"series2": []},
        }
        new_series = [("study1", "series1"), ("study2", "series2")]
        result = _get_first_new_series_by_dicom(new_series, studies)
        assert result is None


class TestHandleLoadFirstSlice:
    """Test handle_load_first_slice method."""

    def test_calls_pre_reset_and_load_first_slice(self, coordinator, mock_app):
        studies = {"study1": {"series1": [Dataset()]}}
        mock_app.file_operations_handler.load_first_slice.return_value = {
            "dataset": Dataset(),
            "study_uid": "study1",
            "series_uid": "series1",
            "slice_index": 0,
        }

        with (
            patch(
                "gui.file_series_loading_coordinator.pre_first_slice_reset"
            ) as mock_reset,
            patch(
                "gui.file_series_loading_coordinator.apply_first_slice_load"
            ) as mock_apply,
        ):
            coordinator.handle_load_first_slice(studies)
            mock_reset.assert_called_once_with(mock_app)
            mock_apply.assert_called_once()

    def test_skips_apply_when_no_first_slice_info(self, coordinator, mock_app):
        studies = {"study1": {"series1": [Dataset()]}}
        mock_app.file_operations_handler.load_first_slice.return_value = None

        with (
            patch("gui.file_series_loading_coordinator.pre_first_slice_reset"),
            patch(
                "gui.file_series_loading_coordinator.apply_first_slice_load"
            ) as mock_apply,
        ):
            coordinator.handle_load_first_slice(studies)
            mock_apply.assert_not_called()


class TestHandleAdditiveLoad:
    """Test handle_additive_load method (non-eviction paths)."""

    def test_syncs_current_studies(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=0,
        )
        mock_app.dicom_organizer.studies = {"study1": {"series1": []}}

        with (
            patch(
                "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
                return_value=True,
            ),
            patch("gui.file_series_loading_coordinator.handle_additive_noop_refresh"),
        ):
            coordinator.handle_additive_load(merge_result)
            assert mock_app.current_studies is mock_app.dicom_organizer.studies

    def test_returns_early_when_eviction_returns_false(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1")],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=1,
        )

        with (
            patch(
                "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
                return_value=False,
            ),
            patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ) as mock_load,
        ):
            coordinator.handle_additive_load(merge_result)
            # Should not call downstream functions when eviction returns False
            mock_load.assert_not_called()

    def test_handles_noop_refresh_when_no_new_or_appended(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[],
            appended_series=[],
            skipped_file_count=2,
            added_file_count=0,
        )

        with (
            patch(
                "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
                return_value=True,
            ),
            patch(
                "gui.file_series_loading_coordinator.handle_additive_noop_refresh"
            ) as mock_noop,
        ):
            coordinator.handle_additive_load(merge_result)
            # Noop refresh is called when both new_series and appended_series are empty
            mock_noop.assert_called_once_with(mock_app, merge_result)

    def test_loads_ps_ko_for_new_studies(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1"), ("study2", "series2")],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=2,
        )
        mock_app.current_studies = {"study1": {}, "study2": {}}

        # Mock all the downstream functions to avoid side effects
        with (
            patch(
                "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
                return_value=True,
            ),
            patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ) as mock_load,
            patch(
                "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
            ),
            patch(
                "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
                return_value=None,
            ),
            patch(
                "gui.file_series_loading_coordinator.refresh_navigator_after_additive"
            ),
            patch(
                "gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"
            ),
            patch(
                "gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"
            ),
            patch("gui.file_series_loading_coordinator.show_additive_load_status"),
            patch(
                "gui.file_series_loading_coordinator.finish_additive_load_side_effects"
            ),
        ):
            coordinator.handle_additive_load(merge_result)
            # Verify load_ps_ko_for_new_studies was called
            assert mock_load.called
            study_uids = mock_load.call_args.args[1]
            assert "study1" in study_uids
            assert "study2" in study_uids

    def test_refreshes_appended_series_subwindows(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[],
            appended_series=[("study1", "series1")],
            skipped_file_count=0,
            added_file_count=1,
        )

        with patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ):
            with patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ):
                with patch(
                    "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
                ) as mock_refresh:
                    with patch(
                        "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
                        return_value=None,
                    ):
                        with patch(
                            "gui.file_series_loading_coordinator.refresh_navigator_after_additive"
                        ):
                            with patch(
                                "gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"
                            ):
                                with patch(
                                    "gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"
                                ):
                                    with patch(
                                        "gui.file_series_loading_coordinator.show_additive_load_status"
                                    ):
                                        with patch(
                                            "gui.file_series_loading_coordinator.finish_additive_load_side_effects"
                                        ):
                                            coordinator.handle_additive_load(
                                                merge_result
                                            )
                                            # Verify refresh_appended_series_subwindows was called
                                            assert mock_refresh.called
                                            assert (
                                                mock_refresh.call_args.args[1]
                                                == merge_result.appended_series
                                            )

    def test_auto_assigns_first_new_series_when_empty_subwindow(
        self, coordinator, mock_app
    ):
        """Test auto-assign when both conditions are met: empty subwindow and valid first_pair."""
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1")],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=1,
        )
        mock_app.current_studies = {"study1": {"series1": [Dataset()]}}

        with patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ):
            with patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ):
                with patch(
                    "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
                ):
                    with patch(
                        "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
                        return_value=0,
                    ):
                        with patch(
                            "gui.file_series_loading_coordinator._get_first_new_series_by_dicom",
                            return_value=("study1", "series1"),
                        ):
                            with patch(
                                "gui.file_series_loading_coordinator.auto_assign_first_new_series"
                            ) as mock_assign:
                                with patch(
                                    "gui.file_series_loading_coordinator.refresh_navigator_after_additive"
                                ):
                                    with patch(
                                        "gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"
                                    ):
                                        with patch(
                                            "gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"
                                        ):
                                            with patch(
                                                "gui.file_series_loading_coordinator.show_additive_load_status"
                                            ):
                                                with patch(
                                                    "gui.file_series_loading_coordinator.finish_additive_load_side_effects"
                                                ):
                                                    coordinator.handle_additive_load(
                                                        merge_result
                                                    )
                                                    # Verify that auto_assign was called (covers line 254-255)
                                                    assert mock_assign.called
                                                    assert (
                                                        mock_assign.call_args.args[1]
                                                        == 0
                                                    )
                                                    assert mock_assign.call_args.args[
                                                        2
                                                    ] == ("study1", "series1")

    def test_skips_auto_assign_when_no_empty_subwindow(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1")],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=1,
        )
        mock_app.current_studies = {"study1": {"series1": [Dataset()]}}

        with patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ):
            with patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ):
                with patch(
                    "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
                ):
                    with patch(
                        "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
                        return_value=None,
                    ):
                        with patch(
                            "gui.file_series_loading_coordinator.auto_assign_first_new_series"
                        ) as mock_assign:
                            with patch(
                                "gui.file_series_loading_coordinator.refresh_navigator_after_additive"
                            ):
                                with patch(
                                    "gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"
                                ):
                                    with patch(
                                        "gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"
                                    ):
                                        with patch(
                                            "gui.file_series_loading_coordinator.show_additive_load_status"
                                        ):
                                            with patch(
                                                "gui.file_series_loading_coordinator.finish_additive_load_side_effects"
                                            ):
                                                coordinator.handle_additive_load(
                                                    merge_result
                                                )
                                                mock_assign.assert_not_called()

    def test_skips_auto_assign_when_first_pair_is_none(self, coordinator, mock_app):
        """Test that auto-assign is skipped when _get_first_new_series_by_dicom returns None."""
        merge_result = SimpleNamespace(
            new_series=[("study1", "series1")],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=1,
        )
        # Empty datasets will cause _get_first_new_series_by_dicom to return None
        mock_app.current_studies = {"study1": {"series1": []}}

        with patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ):
            with patch(
                "gui.file_series_loading_coordinator.load_ps_ko_for_new_studies"
            ):
                with patch(
                    "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
                ):
                    with patch(
                        "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
                        return_value=0,
                    ):
                        with patch(
                            "gui.file_series_loading_coordinator.auto_assign_first_new_series"
                        ) as mock_assign:
                            with patch(
                                "gui.file_series_loading_coordinator.refresh_navigator_after_additive"
                            ):
                                with patch(
                                    "gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"
                                ):
                                    with patch(
                                        "gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"
                                    ):
                                        with patch(
                                            "gui.file_series_loading_coordinator.show_additive_load_status"
                                        ):
                                            with patch(
                                                "gui.file_series_loading_coordinator.finish_additive_load_side_effects"
                                            ):
                                                coordinator.handle_additive_load(
                                                    merge_result
                                                )
                                                # Should not call auto_assign when first_pair is None
                                                mock_assign.assert_not_called()

    def test_calls_all_refresh_functions(self, coordinator, mock_app):
        merge_result = SimpleNamespace(
            new_series=[],
            appended_series=[],
            skipped_file_count=0,
            added_file_count=0,
        )

        with patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ), patch(
            "gui.file_series_loading_coordinator.handle_additive_noop_refresh"
        ) as mock_noop:
            coordinator.handle_additive_load(merge_result)
            # Verify the noop refresh was called
            assert mock_noop.called


class TestOnLoadComplete:
    """Test _on_load_complete callback."""

    def test_updates_app_state_when_datasets_not_none(self, coordinator, mock_app):
        datasets = [Dataset()]
        studies = {"study1": {"series1": datasets}}

        coordinator._on_load_complete(datasets, studies)

        assert mock_app.current_datasets is datasets
        assert mock_app.current_studies is studies

    def test_marks_studies_accessed_in_cache(self, coordinator, mock_app):
        datasets = [Dataset()]
        studies = {"study1": {"series1": datasets}}
        mock_cache = MagicMock()
        mock_app.study_cache = mock_cache

        coordinator._on_load_complete(datasets, studies)

        mock_cache.mark_accessed.assert_called_once_with("study1")

    def test_schedules_tag_export_rebuild(self, coordinator, mock_app):
        datasets = [Dataset()]
        studies = {"study1": {"series1": datasets}}

        coordinator._on_load_complete(datasets, studies)

        mock_app._schedule_tag_export_union_rebuild.assert_called_once()

    def test_handles_none_datasets_gracefully(self, coordinator, mock_app):
        coordinator._on_load_complete(None, {"study1": {}})
        assert not mock_app.current_datasets

    def test_handles_none_studies_gracefully(self, coordinator, mock_app):
        coordinator._on_load_complete([Dataset()], None)
        assert not mock_app.current_studies

    def test_handles_missing_study_cache(self, coordinator, mock_app):
        mock_app.study_cache = None
        datasets = [Dataset()]
        studies = {"study1": {"series1": datasets}}

        coordinator._on_load_complete(datasets, studies)

        # Should not raise, just skip cache marking
        assert mock_app.current_datasets is datasets


class TestDelegationMethods:
    """Test methods that delegate to other modules."""

    def test_open_files_delegates(self, coordinator, mock_app):
        with patch("gui.file_series_loading_coordinator._fpa_open_files") as mock_open:
            coordinator.open_files()
            mock_open.assert_called_once_with(mock_app)

    def test_open_folder_delegates(self, coordinator, mock_app):
        with patch("gui.file_series_loading_coordinator._fpa_open_folder") as mock_open:
            coordinator.open_folder()
            mock_open.assert_called_once_with(mock_app)

    def test_open_recent_file_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_open_recent_file"
        ) as mock_open:
            coordinator.open_recent_file("/path/to/file.dcm")
            mock_open.assert_called_once_with(mock_app, "/path/to/file.dcm")

    def test_open_files_from_paths_delegates(self, coordinator, mock_app):
        paths = ["/path1", "/path2"]
        with patch(
            "gui.file_series_loading_coordinator._fpa_open_files_from_paths"
        ) as mock_open:
            coordinator.open_files_from_paths(paths)
            mock_open.assert_called_once_with(mock_app, paths)

    def test_build_flat_series_list_delegates(self, coordinator):
        studies = {"study1": {"series1": [Dataset()]}}
        with patch(
            "gui.file_series_loading_coordinator._snc_build_flat_series_list"
        ) as mock_build:
            mock_build.return_value = []
            coordinator.build_flat_series_list(studies)
            mock_build.assert_called_once_with(studies)

    def test_assign_series_to_subwindow_delegates(self, coordinator, mock_app):
        subwindow = MagicMock()
        with patch(
            "gui.file_series_loading_coordinator._snc_assign_series_to_subwindow"
        ) as mock_assign:
            coordinator.assign_series_to_subwindow(
                subwindow, "series_uid", 0, "study_uid"
            )
            mock_assign.assert_called_once_with(
                mock_app, subwindow, "series_uid", 0, "study_uid"
            )

    def test_on_series_navigator_selected_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._snc_on_series_navigator_selected"
        ) as mock_nav:
            coordinator.on_series_navigator_selected("series_uid")
            mock_nav.assert_called_once_with(mock_app, "series_uid")

    def test_on_series_navigator_instance_selected_delegates(
        self, coordinator, mock_app
    ):
        with patch(
            "gui.file_series_loading_coordinator._snc_on_series_navigator_instance_selected"
        ) as mock_nav:
            coordinator.on_series_navigator_instance_selected(
                "study_uid", "series_uid", 5
            )
            mock_nav.assert_called_once_with(mock_app, "study_uid", "series_uid", 5)

    def test_on_assign_series_from_context_menu_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._snc_on_assign_series_from_context_menu"
        ) as mock_assign:
            coordinator.on_assign_series_from_context_menu("series_uid")
            mock_assign.assert_called_once_with(mock_app, "series_uid")

    def test_on_series_navigation_requested_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._snc_on_series_navigation_requested"
        ) as mock_nav:
            coordinator.on_series_navigation_requested(1)
            mock_nav.assert_called_once_with(mock_app, 1)

    def test_get_file_path_for_dataset_delegates(self, coordinator, mock_app):
        dataset = Dataset()
        with patch(
            "gui.file_series_loading_coordinator._fpa_get_file_path_for_dataset"
        ) as mock_get:
            mock_get.return_value = "/path"
            result = coordinator.get_file_path_for_dataset(
                dataset, "study_uid", "series_uid", 0
            )
            mock_get.assert_called_once_with(
                mock_app, dataset, "study_uid", "series_uid", 0
            )
            assert result == "/path"

    def test_on_show_file_from_series_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_on_show_file_from_series"
        ) as mock_show:
            coordinator.on_show_file_from_series("study_uid", "series_uid")
            mock_show.assert_called_once_with(mock_app, "study_uid", "series_uid")

    def test_on_about_this_file_from_series_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_on_about_this_file_from_series"
        ) as mock_about:
            coordinator.on_about_this_file_from_series("study_uid", "series_uid")
            mock_about.assert_called_once_with(mock_app, "study_uid", "series_uid")

    def test_get_current_slice_file_path_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_get_current_slice_file_path"
        ) as mock_get:
            mock_get.return_value = "/path"
            result = coordinator.get_current_slice_file_path(0)
            mock_get.assert_called_once_with(mock_app, 0)
            assert result == "/path"

    def test_get_current_slice_file_path_default_subwindow(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_get_current_slice_file_path"
        ) as mock_get:
            mock_get.return_value = "/path"
            result = coordinator.get_current_slice_file_path()
            mock_get.assert_called_once_with(mock_app, None)
            assert result == "/path"

    def test_update_about_this_file_dialog_delegates(self, coordinator, mock_app):
        with patch(
            "gui.file_series_loading_coordinator._fpa_update_about_this_file_dialog"
        ) as mock_update:
            coordinator.update_about_this_file_dialog()
            mock_update.assert_called_once_with(mock_app)
