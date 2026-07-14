"""Unit tests for core.overlay_settings_handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.overlay_settings_handlers as overlay_settings_handlers


def _make_config_manager(**overrides):
    cm = MagicMock()
    cm.get_overlay_font_size.return_value = 12
    cm.get_overlay_font_color.return_value = (10, 20, 30)
    cm.get_overlay_font_family.return_value = "Arial"
    cm.get_overlay_font_variant.return_value = "bold"
    cm.get_scale_markers_color.return_value = (1, 2, 3)
    cm.get_direction_labels_color.return_value = (4, 5, 6)
    cm.get_direction_label_size.return_value = 8
    cm.get_scale_markers_major_tick_interval_mm.return_value = 10.0
    cm.get_scale_markers_minor_tick_interval_mm.return_value = 1.0
    cm.get_theme.return_value = "dark"
    cm.get_metadata_panel_column_widths.return_value = [10, 20, 30, 40]
    cm.get_overlay_mode.return_value = "detailed"
    cm.get_overlay_visibility_state.return_value = 1
    cm.get_roi_default_visible_statistics.return_value = ["mean", "std"]
    cm.get_toolbar_label_style.return_value = "icon"
    cm.get_show_scale_markers.return_value = True
    cm.get_show_direction_labels.return_value = True
    for key, value in overrides.items():
        getattr(cm, key).return_value = value
    return cm


def _make_app(**overrides):
    defaults = {
        "config_manager": _make_config_manager(),
        "overlay_manager": MagicMock(),
        "multi_window_layout": MagicMock(),
        "subwindow_managers": {},
        "subwindow_data": {},
        "main_window": MagicMock(),
        "metadata_panel": MagicMock(),
        "_refresh_slice_sync_group_indicators": MagicMock(),
        "_slice_location_line_coordinator": MagicMock(),
    }
    defaults.update(overrides)
    app = SimpleNamespace(**defaults)
    app.multi_window_layout.get_all_subwindows.return_value = []
    return app


class TestApplyImportedCustomizations:
    def test_sets_overlay_manager_fonts(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        overlay_settings_handlers.apply_imported_customizations(app)
        app.overlay_manager.set_font_size.assert_called_once_with(12)
        app.overlay_manager.set_font_color.assert_called_once_with(10, 20, 30)
        app.overlay_manager.set_font_family.assert_called_once_with("Arial")
        app.overlay_manager.set_font_variant.assert_called_once_with("bold")

    def test_none_subwindow_skipped(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [None]
        overlay_settings_handlers.apply_imported_customizations(app)  # should not raise

    def test_subwindow_without_image_viewer_skips_setters(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        subwindow = SimpleNamespace(image_viewer=None)
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        overlay_settings_handlers.apply_imported_customizations(app)  # should not raise

    def test_subwindow_with_image_viewer_updates_scale_and_direction_state(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        image_viewer = MagicMock()
        subwindow = SimpleNamespace(image_viewer=image_viewer)
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        overlay_settings_handlers.apply_imported_customizations(app)
        image_viewer.set_scale_markers_color_state.assert_called_once_with((1, 2, 3))
        image_viewer.set_direction_labels_color_state.assert_called_once_with((4, 5, 6))
        image_viewer.set_direction_label_size_state.assert_called_once_with(8)
        image_viewer.set_scale_markers_tick_intervals_state.assert_called_once_with(10.0, 1.0)

    def test_per_subwindow_overlay_manager_updated_when_registered(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        om = MagicMock()
        subwindow = SimpleNamespace(image_viewer=MagicMock())
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_manager": om}}
        overlay_settings_handlers.apply_imported_customizations(app)
        om.set_font_size.assert_called_once_with(12)
        om.set_font_color.assert_called_once_with(10, 20, 30)

    def test_subwindow_not_in_managers_skips_per_pane_overlay_manager(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        subwindow = SimpleNamespace(image_viewer=MagicMock())
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {}
        overlay_settings_handlers.apply_imported_customizations(app)  # should not raise

    def test_calls_refresh_and_annotation_helpers(self, monkeypatch):
        refresh_mock = MagicMock()
        annotation_mock = MagicMock()
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", refresh_mock)
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", annotation_mock)
        app = _make_app()
        overlay_settings_handlers.apply_imported_customizations(app)
        refresh_mock.assert_called_once_with(app)
        annotation_mock.assert_called_once_with(app)

    def test_sets_theme(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        overlay_settings_handlers.apply_imported_customizations(app)
        app.main_window._set_theme.assert_called_once_with("dark")

    def test_sets_metadata_column_widths_when_four_present(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        overlay_settings_handlers.apply_imported_customizations(app)
        app.metadata_panel.tree_widget.setColumnWidth.assert_any_call(0, 10)
        app.metadata_panel.tree_widget.setColumnWidth.assert_any_call(3, 40)
        assert app.metadata_panel.tree_widget.setColumnWidth.call_count == 4

    def test_skips_metadata_column_widths_when_not_four(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        monkeypatch.setattr(overlay_settings_handlers, "on_annotation_options_applied", MagicMock())
        app = _make_app()
        app.config_manager.get_metadata_panel_column_widths.return_value = [10, 20]
        overlay_settings_handlers.apply_imported_customizations(app)
        app.metadata_panel.tree_widget.setColumnWidth.assert_not_called()


class TestSyncAllOverlayManagersFromConfig:
    def test_applies_mode_and_visibility_to_all_registered_overlay_managers(self):
        app = _make_app()
        om1, om2 = MagicMock(), MagicMock()
        app.subwindow_managers = {0: {"overlay_manager": om1}, 1: {"overlay_manager": om2}}
        overlay_settings_handlers.sync_all_overlay_managers_from_config(app)
        for om in (om1, om2):
            om.set_mode.assert_called_once_with("detailed")
            om.set_visibility_state.assert_called_once_with(1)

    def test_missing_overlay_manager_skipped(self):
        app = _make_app()
        app.subwindow_managers = {0: {}}
        overlay_settings_handlers.sync_all_overlay_managers_from_config(app)  # should not raise


class TestCycleOverlayDetailMode:
    def test_cycles_minimal_to_detailed(self):
        app = _make_app()
        app.config_manager.get_overlay_mode.return_value = "minimal"
        overlay_settings_handlers.cycle_overlay_detail_mode(app)
        app.config_manager.set_overlay_mode.assert_called_once_with("detailed")
        app.config_manager.set_overlay_visibility_state.assert_called_once_with(0)

    def test_cycles_detailed_to_hidden(self):
        app = _make_app()
        app.config_manager.get_overlay_mode.return_value = "detailed"
        overlay_settings_handlers.cycle_overlay_detail_mode(app)
        app.config_manager.set_overlay_mode.assert_called_once_with("hidden")

    def test_cycles_hidden_to_minimal(self):
        app = _make_app()
        app.config_manager.get_overlay_mode.return_value = "hidden"
        overlay_settings_handlers.cycle_overlay_detail_mode(app)
        app.config_manager.set_overlay_mode.assert_called_once_with("minimal")

    def test_unknown_mode_defaults_to_minimal_then_advances(self):
        app = _make_app()
        app.config_manager.get_overlay_mode.return_value = "unknown"
        overlay_settings_handlers.cycle_overlay_detail_mode(app)
        app.config_manager.set_overlay_mode.assert_called_once_with("detailed")

    def test_updates_managers_and_restores_visibility(self):
        app = _make_app()
        om = MagicMock()
        oc = MagicMock()
        app.subwindow_managers = {0: {"overlay_manager": om, "overlay_coordinator": oc}}
        overlay_settings_handlers.cycle_overlay_detail_mode(app)
        om.set_mode.assert_called_once()
        om.set_visibility_state.assert_called_once_with(0)
        oc.restore_measurement_and_roi_visibility.assert_called_once()

    def test_missing_managers_skipped(self):
        app = _make_app()
        app.subwindow_managers = {0: {}}
        overlay_settings_handlers.cycle_overlay_detail_mode(app)  # should not raise


class TestOnOverlayConfigApplied:
    def test_calls_sync_refresh_and_slice_sync_indicators(self, monkeypatch):
        sync_mock = MagicMock()
        refresh_mock = MagicMock()
        monkeypatch.setattr(overlay_settings_handlers, "sync_all_overlay_managers_from_config", sync_mock)
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", refresh_mock)
        app = _make_app()
        overlay_settings_handlers.on_overlay_config_applied(app)
        sync_mock.assert_called_once_with(app)
        refresh_mock.assert_called_once_with(app)
        app._refresh_slice_sync_group_indicators.assert_called_once()


class TestRefreshOverlayAllSubwindows:
    def test_no_subwindow_skips(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [None]
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)  # should not raise

    def test_subwindow_not_in_managers_skips(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)  # should not raise

    def test_calls_overlay_coordinator_when_present(self):
        app = _make_app()
        oc = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        oc.handle_overlay_config_applied.assert_called_once()

    def test_missing_overlay_coordinator_skipped(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)  # should not raise

    def test_mpr_pane_displays_mpr_slice_and_continues(self):
        app = _make_app()
        mpr_controller = MagicMock()
        mpr_controller.is_mpr.return_value = True
        app._mpr_controller = mpr_controller
        oc = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        app.subwindow_data = {0: {"mpr_slice_index": 5}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        mpr_controller.display_mpr_slice.assert_called_once_with(0, 5)
        oc.handle_overlay_config_applied.assert_not_called()

    def test_mpr_pane_falls_back_to_current_slice_index(self):
        app = _make_app()
        mpr_controller = MagicMock()
        mpr_controller.is_mpr.return_value = True
        app._mpr_controller = mpr_controller
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {}}
        app.subwindow_data = {0: {"current_slice_index": 3}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        mpr_controller.display_mpr_slice.assert_called_once_with(0, 3)

    def test_mpr_pane_defaults_slice_index_to_zero(self):
        app = _make_app()
        mpr_controller = MagicMock()
        mpr_controller.is_mpr.return_value = True
        app._mpr_controller = mpr_controller
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {}}
        app.subwindow_data = {}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        mpr_controller.display_mpr_slice.assert_called_once_with(0, 0)

    def test_mpr_controller_not_mpr_pane_falls_through_to_overlay_coordinator(self):
        app = _make_app()
        mpr_controller = MagicMock()
        mpr_controller.is_mpr.return_value = False
        app._mpr_controller = mpr_controller
        oc = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        mpr_controller.display_mpr_slice.assert_not_called()
        oc.handle_overlay_config_applied.assert_called_once()

    def test_mpr_controller_raising_exception_is_swallowed(self):
        app = _make_app()
        mpr_controller = MagicMock()
        mpr_controller.is_mpr.side_effect = RuntimeError("boom")
        app._mpr_controller = mpr_controller
        oc = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        oc.handle_overlay_config_applied.assert_called_once()

    def test_no_mpr_controller_attribute_falls_through(self):
        app = _make_app()  # no _mpr_controller attribute at all
        oc = MagicMock()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.refresh_overlay_all_subwindows(app)
        oc.handle_overlay_config_applied.assert_called_once()


class TestOnAnnotationOptionsApplied:
    def _roi_manager(self, rois_by_key):
        roi_mgr = MagicMock()
        roi_mgr.rois = rois_by_key
        return roi_mgr

    def test_subwindow_not_in_managers_skipped(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        app.subwindow_managers = {}
        overlay_settings_handlers.on_annotation_options_applied(app)  # should not raise

    def test_updates_roi_visible_statistics_and_styles(self):
        app = _make_app()
        roi = SimpleNamespace(visible_statistics=set())
        roi_mgr = self._roi_manager({"key1": [roi]})
        app.subwindow_managers = {0: {"roi_manager": roi_mgr}}
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        overlay_settings_handlers.on_annotation_options_applied(app)
        assert roi.visible_statistics == {"mean", "std"}
        roi_mgr.update_all_roi_styles.assert_called_once_with(app.config_manager)

    def test_updates_measurement_text_and_arrow_tool_styles(self):
        app = _make_app()
        meas_tool = MagicMock()
        text_tool = MagicMock()
        arrow_tool = MagicMock()
        app.subwindow_managers = {
            0: {
                "measurement_tool": meas_tool,
                "text_annotation_tool": text_tool,
                "arrow_annotation_tool": arrow_tool,
            }
        }
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        overlay_settings_handlers.on_annotation_options_applied(app)
        meas_tool.update_all_measurement_styles.assert_called_once_with(app.config_manager)
        text_tool.update_all_annotation_styles.assert_called_once_with(app.config_manager)
        arrow_tool.update_all_arrow_styles.assert_called_once_with(app.config_manager)

    def test_no_optional_tools_present_is_noop(self):
        app = _make_app()
        app.subwindow_managers = {0: {}}
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        overlay_settings_handlers.on_annotation_options_applied(app)  # should not raise

    def test_redisplays_rois_and_measurements_when_current_dataset_present(self):
        app = _make_app()
        sdm = MagicMock()
        current_ds = SimpleNamespace(name="ds")
        app.subwindow_managers = {0: {"slice_display_manager": sdm}}
        app.subwindow_data = {0: {"current_dataset": current_ds}}
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        overlay_settings_handlers.on_annotation_options_applied(app)
        sdm.display_rois_for_slice.assert_called_once_with(current_ds)
        sdm.display_measurements_for_slice.assert_called_once_with(current_ds)

    def test_no_current_dataset_skips_redisplay(self):
        app = _make_app()
        sdm = MagicMock()
        app.subwindow_managers = {0: {"slice_display_manager": sdm}}
        app.subwindow_data = {0: {}}
        app.multi_window_layout.get_all_subwindows.return_value = [SimpleNamespace()]
        overlay_settings_handlers.on_annotation_options_applied(app)
        sdm.display_rois_for_slice.assert_not_called()


class TestOnSettingsApplied:
    def test_applies_theme(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        overlay_settings_handlers.on_settings_applied(app)
        app.main_window._apply_theme.assert_called_once()

    def test_applies_toolbar_label_style_when_present(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        overlay_settings_handlers.on_settings_applied(app)
        app.main_window.apply_toolbar_label_style.assert_called_once_with("icon")

    def test_skips_toolbar_label_style_when_none(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = None
        overlay_settings_handlers.on_settings_applied(app)  # should not raise

    def test_updates_overlay_manager_fonts(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        overlay_settings_handlers.on_settings_applied(app)
        app.overlay_manager.set_font_size.assert_called_once_with(12)
        app.overlay_manager.set_font_color.assert_called_once_with(10, 20, 30)

    def test_updates_subwindow_overlay_manager_and_image_viewer_state(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        om = MagicMock()
        image_viewer = MagicMock()
        subwindow = SimpleNamespace(image_viewer=image_viewer)
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_manager": om}}
        overlay_settings_handlers.on_settings_applied(app)
        om.set_font_size.assert_called_once_with(12)
        image_viewer.set_scale_markers_state.assert_called_once_with(True)
        image_viewer.set_direction_labels_state.assert_called_once_with(True)

    def test_subwindow_not_in_managers_skipped(self, monkeypatch):
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", MagicMock())
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        subwindow = SimpleNamespace(image_viewer=MagicMock())
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {}
        overlay_settings_handlers.on_settings_applied(app)  # should not raise

    def test_calls_refresh_and_slice_line_and_sync_indicator_helpers(self, monkeypatch):
        refresh_mock = MagicMock()
        monkeypatch.setattr(overlay_settings_handlers, "refresh_overlay_all_subwindows", refresh_mock)
        app = _make_app()
        app.main_window.apply_toolbar_label_style = MagicMock()
        overlay_settings_handlers.on_settings_applied(app)
        refresh_mock.assert_called_once_with(app)
        app._slice_location_line_coordinator.refresh_all.assert_called_once()
        app._refresh_slice_sync_group_indicators.assert_called_once()


class TestOnOverlayFontSizeChanged:
    def test_updates_overlay_manager_and_coordinator(self):
        app = _make_app()
        om = MagicMock()
        oc = MagicMock()
        subwindow = SimpleNamespace()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_manager": om, "overlay_coordinator": oc}}
        overlay_settings_handlers.on_overlay_font_size_changed(app, 18)
        om.set_font_size.assert_called_once_with(18)
        oc.handle_overlay_font_size_changed.assert_called_once_with(18)

    def test_no_overlay_manager_skips_coordinator_call_too(self):
        app = _make_app()
        oc = MagicMock()
        subwindow = SimpleNamespace()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.on_overlay_font_size_changed(app, 18)
        oc.handle_overlay_font_size_changed.assert_not_called()

    def test_no_overlay_coordinator_still_updates_manager(self):
        app = _make_app()
        om = MagicMock()
        subwindow = SimpleNamespace()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_manager": om}}
        overlay_settings_handlers.on_overlay_font_size_changed(app, 18)
        om.set_font_size.assert_called_once_with(18)

    def test_none_subwindow_or_not_in_managers_skipped(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [None]
        app.subwindow_managers = {}
        overlay_settings_handlers.on_overlay_font_size_changed(app, 18)  # should not raise


class TestOnOverlayFontColorChanged:
    def test_updates_overlay_manager_and_coordinator(self):
        app = _make_app()
        om = MagicMock()
        oc = MagicMock()
        subwindow = SimpleNamespace()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_manager": om, "overlay_coordinator": oc}}
        overlay_settings_handlers.on_overlay_font_color_changed(app, 1, 2, 3)
        om.set_font_color.assert_called_once_with(1, 2, 3)
        oc.handle_overlay_font_color_changed.assert_called_once_with(1, 2, 3)

    def test_no_overlay_manager_skips_coordinator_call_too(self):
        app = _make_app()
        oc = MagicMock()
        subwindow = SimpleNamespace()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.subwindow_managers = {0: {"overlay_coordinator": oc}}
        overlay_settings_handlers.on_overlay_font_color_changed(app, 1, 2, 3)
        oc.handle_overlay_font_color_changed.assert_not_called()

    def test_none_subwindow_or_not_in_managers_skipped(self):
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [None]
        app.subwindow_managers = {}
        overlay_settings_handlers.on_overlay_font_color_changed(app, 1, 2, 3)  # should not raise
