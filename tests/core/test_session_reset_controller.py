"""Unit tests for core.session_reset_controller."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.session_reset_controller as session_reset_controller


def _make_subwindow(*, scene: object | None = None) -> SimpleNamespace:
    image_viewer = None
    if scene is not None:
        image_viewer = SimpleNamespace(
            scene=scene,
            image_item=object(),
            viewport=lambda: SimpleNamespace(update=MagicMock()),
        )
    return SimpleNamespace(image_viewer=image_viewer)


def _make_app(**overrides) -> SimpleNamespace:
    roi_scene = object()
    app = SimpleNamespace(
        subwindow_managers={},
        multi_window_layout=SimpleNamespace(get_all_subwindows=MagicMock(return_value=[]), reset_slot_to_view_default=MagicMock()),
        roi_list_panel=SimpleNamespace(update_roi_list=MagicMock()),
        roi_statistics_panel=SimpleNamespace(clear_statistics=MagicMock()),
        subwindow_data={},
        _mpr_controller=SimpleNamespace(clear_mpr=MagicMock()),
        _reset_fusion_for_all_subwindows=MagicMock(),
        metadata_panel=SimpleNamespace(set_dataset=MagicMock()),
        intensity_projection_controls_widget=SimpleNamespace(
            set_enabled=MagicMock(),
            set_projection_type=MagicMock(),
            set_slice_count=MagicMock(),
        ),
        current_studies={},
        dicom_organizer=SimpleNamespace(clear=MagicMock()),
        annotation_manager=SimpleNamespace(clear_all_ps_ko=MagicMock()),
        study_cache=SimpleNamespace(clear=MagicMock()),
        _schedule_tag_export_union_rebuild=MagicMock(),
        config_manager=SimpleNamespace(set_slice_sync_groups=MagicMock()),
        _slice_sync_coordinator=SimpleNamespace(set_groups=MagicMock(), invalidate_cache=MagicMock()),
        _slice_location_line_coordinator=SimpleNamespace(refresh_all=MagicMock()),
        slice_navigator=SimpleNamespace(set_total_slices=MagicMock(), set_current_slice=MagicMock()),
        series_navigator=SimpleNamespace(update_series_list=MagicMock(), set_subwindow_assignments=MagicMock()),
        _refresh_series_navigator_state=MagicMock(),
        metadata_controller=SimpleNamespace(clear_tag_history=MagicMock()),
        _update_undo_redo_state=MagicMock(),
        cine_player=SimpleNamespace(stop_playback=MagicMock()),
        dialog_coordinator=SimpleNamespace(clear_tag_viewer_filter=MagicMock()),
        main_window=SimpleNamespace(update_status=MagicMock()),
        _refresh_window_slot_map_widgets=MagicMock(),
        current_dataset="dataset",
        current_study_uid="study",
        current_series_uid="series",
        current_slice_index=5,
        _volume_render_facade=SimpleNamespace(close_all_dialogs=MagicMock()),
        _drain_tag_export_union_worker=MagicMock(),
    )
    app._default_scene = roi_scene
    for key, value in overrides.items():
        setattr(app, key, value)
    return app


class TestClearData:
    def test_clears_display_state_annotations_and_shared_panels(self) -> None:
        scene = object()
        roi_manager = MagicMock()
        measurement_tool = MagicMock()
        text_annotation_tool = MagicMock()
        arrow_annotation_tool = MagicMock()
        display_manager = MagicMock()
        app = _make_app(
            subwindow_managers={
                0: {
                    "slice_display_manager": display_manager,
                    "roi_manager": roi_manager,
                    "measurement_tool": measurement_tool,
                    "text_annotation_tool": text_annotation_tool,
                    "arrow_annotation_tool": arrow_annotation_tool,
                }
            },
            multi_window_layout=SimpleNamespace(
                get_all_subwindows=MagicMock(return_value=[_make_subwindow(scene=scene)])
            ),
        )

        session_reset_controller.clear_data(app)

        display_manager.clear_display_state.assert_called_once_with()
        roi_manager.clear_all_rois.assert_called_once_with(scene)
        measurement_tool.clear_measurements.assert_called_once_with(scene)
        text_annotation_tool.clear_annotations.assert_called_once_with(scene)
        arrow_annotation_tool.clear_arrows.assert_called_once_with(scene)
        app.roi_list_panel.update_roi_list.assert_called_once_with("", "", 0)
        app.roi_statistics_panel.clear_statistics.assert_called_once_with()

    def test_skips_missing_subwindows_and_tools(self) -> None:
        app = _make_app(
            subwindow_managers={0: {"slice_display_manager": object()}},
            multi_window_layout=SimpleNamespace(
                get_all_subwindows=MagicMock(
                    return_value=[None, SimpleNamespace(image_viewer=None)]
                )
            ),
        )

        session_reset_controller.clear_data(app)

        app.roi_list_panel.update_roi_list.assert_called_once()


class TestCloseAllFiles:
    def test_resets_mpr_viewers_scenes_overlays_studies_and_shared_state(self, monkeypatch) -> None:
        monkeypatch.setattr(session_reset_controller, "clear_data", MagicMock())
        monkeypatch.setattr(session_reset_controller, "clear_cached_pixel_array", MagicMock())

        scene0 = MagicMock()
        scene1 = MagicMock()
        viewport0 = SimpleNamespace(update=MagicMock())
        viewport1 = SimpleNamespace(update=MagicMock())
        subwindows = [
            SimpleNamespace(
                image_viewer=SimpleNamespace(scene=scene0, image_item=object(), viewport=lambda: viewport0)
            ),
            SimpleNamespace(
                image_viewer=SimpleNamespace(scene=scene1, image_item=object(), viewport=lambda: viewport1)
            ),
        ]
        overlay_manager0 = SimpleNamespace(clear_overlay_items=MagicMock(), overlay_items=["x"])
        overlay_manager1 = SimpleNamespace(clear_overlay_items=MagicMock(), overlay_items=["y"])
        view_state_manager = SimpleNamespace(
            reset_window_level_state=MagicMock(),
            reset_series_tracking=MagicMock(),
        )
        slice_display_manager = SimpleNamespace(clear_display_state=MagicMock())
        ds1 = SimpleNamespace()
        ds2 = SimpleNamespace()
        app = _make_app(
            subwindow_managers={
                0: {
                    "overlay_manager": overlay_manager0,
                    "view_state_manager": view_state_manager,
                    "slice_display_manager": slice_display_manager,
                },
                1: {"overlay_manager": overlay_manager1},
            },
            multi_window_layout=SimpleNamespace(
                get_all_subwindows=MagicMock(return_value=subwindows),
                reset_slot_to_view_default=MagicMock(),
            ),
            subwindow_data={0: {"is_mpr": True}, 1: {"is_mpr": False}},
            current_studies={"study": {"series": [ds1, ds2]}},
        )

        session_reset_controller.close_all_files(app)

        app._mpr_controller.clear_mpr.assert_called_once_with(0)
        session_reset_controller.clear_data.assert_called_once_with(app)
        scene0.clear.assert_called_once_with()
        scene1.clear.assert_called_once_with()
        viewport0.update.assert_called_once_with()
        viewport1.update.assert_called_once_with()
        overlay_manager0.clear_overlay_items.assert_called_once_with(scene0)
        overlay_manager1.clear_overlay_items.assert_called_once_with(scene1)
        app._reset_fusion_for_all_subwindows.assert_called_once_with()
        app.metadata_panel.set_dataset.assert_called_once_with(None)
        view_state_manager.reset_window_level_state.assert_called_once_with()
        view_state_manager.reset_series_tracking.assert_called_once_with()
        slice_display_manager.clear_display_state.assert_called_once_with()
        app.intensity_projection_controls_widget.set_enabled.assert_called_once_with(False)
        app.intensity_projection_controls_widget.set_projection_type.assert_called_once_with("aip")
        app.intensity_projection_controls_widget.set_slice_count.assert_called_once_with(4)
        assert app.subwindow_data == {}
        assert session_reset_controller.clear_cached_pixel_array.call_count == 2
        app.dicom_organizer.clear.assert_called_once_with()
        app.annotation_manager.clear_all_ps_ko.assert_called_once_with()
        app.study_cache.clear.assert_called_once_with()
        assert app.current_dataset is None
        assert app.current_studies == {}
        assert app.current_study_uid == ""
        assert app.current_series_uid == ""
        assert app.current_slice_index == 0
        app._schedule_tag_export_union_rebuild.assert_called_once_with()
        app.config_manager.set_slice_sync_groups.assert_called_once_with([])
        app._slice_sync_coordinator.set_groups.assert_called_once_with([])
        app._slice_sync_coordinator.invalidate_cache.assert_called_once_with()
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()
        app.slice_navigator.set_total_slices.assert_called_once_with(0)
        app.slice_navigator.set_current_slice.assert_called_once_with(0)
        app.series_navigator.update_series_list.assert_called_once_with({}, "", "")
        app._refresh_series_navigator_state.assert_called_once_with()
        app.series_navigator.set_subwindow_assignments.assert_called_once_with({})
        app.metadata_controller.clear_tag_history.assert_called_once_with()
        app._update_undo_redo_state.assert_called_once_with()
        app.cine_player.stop_playback.assert_called_once_with()
        app.dialog_coordinator.clear_tag_viewer_filter.assert_called_once_with()
        app.main_window.update_status.assert_called_once_with("Open a DICOM file or folder to begin")
        app.multi_window_layout.reset_slot_to_view_default.assert_called_once_with()
        app._refresh_window_slot_map_widgets.assert_called_once_with()

    def test_falls_back_when_overlay_scene_is_missing_and_optional_collaborators_are_absent(self, monkeypatch) -> None:
        monkeypatch.setattr(session_reset_controller, "clear_data", MagicMock())
        monkeypatch.setattr(session_reset_controller, "clear_cached_pixel_array", MagicMock())

        overlay_manager = SimpleNamespace(clear_overlay_items=MagicMock(), overlay_items=["a", "b"])
        app = _make_app(
            subwindow_managers={0: {"overlay_manager": overlay_manager}},
            multi_window_layout=SimpleNamespace(
                get_all_subwindows=MagicMock(return_value=[SimpleNamespace(image_viewer=None)]),
                reset_slot_to_view_default=MagicMock(),
            ),
            study_cache=None,
            metadata_controller=None,
            cine_player=None,
            dialog_coordinator=None,
            current_studies={},
        )
        delattr(app, "_mpr_controller")

        session_reset_controller.close_all_files(app)

        assert overlay_manager.overlay_items == []


class TestFinalizeForApplicationQuit:
    def test_closes_volume_dialogs_and_resets_sync_groups(self) -> None:
        app = _make_app()

        session_reset_controller.finalize_for_application_quit(app)

        app._volume_render_facade.close_all_dialogs.assert_called_once_with()
        app._drain_tag_export_union_worker.assert_called_once_with(timeout_sec=30.0)
        app.multi_window_layout.reset_slot_to_view_default.assert_called_once_with()
        app.config_manager.set_slice_sync_groups.assert_called_once_with([])
        app._slice_sync_coordinator.set_groups.assert_called_once_with([])
        app._slice_sync_coordinator.invalidate_cache.assert_called_once_with()

    def test_skips_missing_volume_facade(self) -> None:
        app = _make_app(_volume_render_facade=None)

        session_reset_controller.finalize_for_application_quit(app)

        app._drain_tag_export_union_worker.assert_called_once_with(timeout_sec=30.0)
