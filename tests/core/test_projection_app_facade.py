"""Unit tests for core.projection_app_facade."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock

import core.projection_app_facade as projection_app_facade
from core.projection_app_facade import ProjectionAppFacade


def _make_controls() -> SimpleNamespace:
    enable_checkbox = SimpleNamespace(blockSignals=MagicMock(), isChecked=MagicMock(return_value=False))
    projection_combo = SimpleNamespace(blockSignals=MagicMock())
    slice_count_combo = SimpleNamespace(blockSignals=MagicMock())
    return SimpleNamespace(
        enable_checkbox=enable_checkbox,
        projection_combo=projection_combo,
        slice_count_combo=slice_count_combo,
        set_enabled=MagicMock(),
        set_projection_type=MagicMock(),
        set_slice_count=MagicMock(),
        get_enabled=MagicMock(return_value=False),
        get_projection_type=MagicMock(return_value="mip"),
        get_slice_count=MagicMock(return_value=6),
    )


def _make_app(**overrides) -> SimpleNamespace:
    defaults = {
        "intensity_projection_controls_widget": _make_controls(),
        "_resetting_projection_state": False,
        "slice_display_manager": SimpleNamespace(
            projection_enabled=False,
            set_projection_enabled=MagicMock(),
            set_projection_type=MagicMock(),
            set_projection_slice_count=MagicMock(),
        ),
        "roi_coordinator": None,
        "dialog_coordinator": SimpleNamespace(update_histogram_for_subwindow=MagicMock()),
        "focused_subwindow_index": 0,
        "_mpr_controller": SimpleNamespace(is_mpr=MagicMock(return_value=False), display_mpr_slice=MagicMock()),
        "subwindow_data": {},
        "_slice_location_line_coordinator": SimpleNamespace(refresh_all=MagicMock()),
        "roi_manager": SimpleNamespace(get_selected_roi=MagicMock(return_value=None)),
        "current_dataset": None,
        "_display_slice": MagicMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestSyncIntensityProjectionWidgetFromMprData:
    def test_syncs_widget_values_while_blocking_signals(self) -> None:
        app = _make_app()
        facade = ProjectionAppFacade(app)

        facade.sync_intensity_projection_widget_from_mpr_data(
            {
                "mpr_combine_enabled": True,
                "mpr_combine_mode": "minip",
                "mpr_combine_slice_count": 8,
            }
        )

        controls = app.intensity_projection_controls_widget
        controls.enable_checkbox.blockSignals.assert_any_call(True)
        controls.enable_checkbox.blockSignals.assert_any_call(False)
        controls.projection_combo.blockSignals.assert_any_call(True)
        controls.projection_combo.blockSignals.assert_any_call(False)
        controls.slice_count_combo.blockSignals.assert_any_call(True)
        controls.slice_count_combo.blockSignals.assert_any_call(False)
        controls.set_enabled.assert_called_once_with(True, keep_signals_blocked=True)
        controls.set_projection_type.assert_called_once_with("minip")
        controls.set_slice_count.assert_called_once_with(8)

    def test_uses_defaults_when_mpr_data_is_missing(self) -> None:
        app = _make_app()
        facade = ProjectionAppFacade(app)

        facade.sync_intensity_projection_widget_from_mpr_data({})

        controls = app.intensity_projection_controls_widget
        controls.set_enabled.assert_called_once_with(False, keep_signals_blocked=True)
        controls.set_projection_type.assert_called_once_with("aip")
        controls.set_slice_count.assert_called_once_with(4)


class TestOnProjectionEnabledChanged:
    def test_reset_in_progress_resyncs_widget_without_updating_manager(self) -> None:
        app = _make_app(_resetting_projection_state=True)
        app.intensity_projection_controls_widget.get_enabled.return_value = False
        app.slice_display_manager.projection_enabled = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(False)

        app.intensity_projection_controls_widget.set_enabled.assert_called_once_with(True)
        app.slice_display_manager.set_projection_enabled.assert_not_called()

    def test_normal_non_mpr_path_updates_manager_widget_and_display(self) -> None:
        app = _make_app(current_dataset="dataset")
        app.intensity_projection_controls_widget.get_enabled.return_value = False
        app.slice_display_manager.projection_enabled = False
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        app.slice_display_manager.set_projection_enabled.assert_called_once_with(True)
        app.intensity_projection_controls_widget.set_enabled.assert_called_once_with(True)
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)
        app._display_slice.assert_called_once_with("dataset")
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()

    def test_mpr_path_updates_subwindow_state_and_refreshes_mpr_slice(self) -> None:
        app = _make_app(
            focused_subwindow_index=2,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={2: {"mpr_slice_index": 9}},
        )
        app.intensity_projection_controls_widget.get_enabled.return_value = True
        app.intensity_projection_controls_widget.get_projection_type.return_value = "mip"
        app.intensity_projection_controls_widget.get_slice_count.return_value = 3
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        assert app.subwindow_data[2]["mpr_combine_enabled"] is True
        assert app.subwindow_data[2]["mpr_combine_mode"] == "mip"
        assert app.subwindow_data[2]["mpr_combine_slice_count"] == 3
        app._mpr_controller.display_mpr_slice.assert_called_once_with(2, 9)
        app._display_slice.assert_not_called()
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()

    def test_mpr_path_without_subwindow_data_returns_after_histogram_only(self) -> None:
        app = _make_app(
            focused_subwindow_index=2,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={},
        )
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(2)
        app._mpr_controller.display_mpr_slice.assert_not_called()
        app._slice_location_line_coordinator.refresh_all.assert_not_called()

    def test_no_current_dataset_non_mpr_only_updates_histogram(self) -> None:
        app = _make_app(current_dataset=None)
        app.intensity_projection_controls_widget.get_enabled.return_value = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        app.slice_display_manager.set_projection_enabled.assert_called_once_with(True)
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)
        app._display_slice.assert_not_called()

    def test_roi_projection_callback_mismatch_is_tolerated(self) -> None:
        app = _make_app(current_dataset="dataset")
        app.slice_display_manager.projection_enabled = False
        app.roi_coordinator = SimpleNamespace(get_projection_enabled=MagicMock(return_value=True))
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        app._display_slice.assert_called_once_with("dataset")

    def test_debug_mode_covers_closure_inspection_and_selected_roi_messages(self, monkeypatch) -> None:
        monkeypatch.setattr(projection_app_facade, "DEBUG_PROJECTION", True)
        print_mock = MagicMock()
        monkeypatch.setattr("builtins.print", print_mock)

        app = _make_app(
            current_dataset="dataset",
            focused_subwindow_index=1,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={1: {"mpr_slice_index": 3}},
            roi_manager=SimpleNamespace(get_selected_roi=MagicMock(return_value="roi-1")),
        )
        app.intensity_projection_controls_widget.get_enabled.return_value = True
        app.intensity_projection_controls_widget.get_projection_type.return_value = "mip"
        app.intensity_projection_controls_widget.get_slice_count.return_value = 4

        closure_managers = {"slice_display_manager": SimpleNamespace(projection_enabled=True)}

        def callback():
            return False

        _ = callback.__closure__  # touch for pyright happiness

        def make_callback():
            managers = closure_managers

            def _inner():
                return not managers

            return _inner

        app.roi_coordinator = SimpleNamespace(get_projection_enabled=make_callback())
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        app._mpr_controller.display_mpr_slice.assert_called_once_with(1, 3)
        assert print_mock.call_count > 0

    def test_debug_mode_logs_callback_introspection_exception(self, monkeypatch) -> None:
        monkeypatch.setattr(projection_app_facade, "DEBUG_PROJECTION", True)
        print_mock = MagicMock()
        debug_mock = MagicMock()
        monkeypatch.setattr("builtins.print", print_mock)
        monkeypatch.setattr(projection_app_facade._log, "debug", debug_mock)

        class BadCallback:
            __closure__: ClassVar[list[Any]] = [SimpleNamespace(cell_contents=object())]

            def __call__(self):
                raise RuntimeError("boom")

        app = _make_app(current_dataset=None, roi_coordinator=SimpleNamespace(get_projection_enabled=BadCallback()))
        facade = ProjectionAppFacade(app)

        facade.on_projection_enabled_changed(True)

        assert print_mock.call_count > 0
        debug_mock.assert_called_once()


class TestOnProjectionTypeChanged:
    def test_updates_managers_widget_and_non_mpr_display(self) -> None:
        app = _make_app(current_dataset="dataset")
        app.slice_display_manager.projection_enabled = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_type_changed("minip")

        app.slice_display_manager.set_projection_type.assert_called_once_with("minip")
        app.intensity_projection_controls_widget.set_projection_type.assert_called_once_with("minip")
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)
        app._display_slice.assert_called_once_with("dataset")
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()

    def test_mpr_projection_type_updates_subwindow_data_only(self) -> None:
        app = _make_app(
            focused_subwindow_index=1,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={1: {"mpr_slice_index": 4}},
        )
        facade = ProjectionAppFacade(app)

        facade.on_projection_type_changed("mip")

        assert app.subwindow_data[1]["mpr_combine_mode"] == "mip"
        app._mpr_controller.display_mpr_slice.assert_called_once_with(1, 4)
        app._display_slice.assert_not_called()

    def test_non_mpr_without_current_dataset_skips_display(self) -> None:
        app = _make_app(current_dataset=None)
        app.slice_display_manager.projection_enabled = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_type_changed("mip")

        app._display_slice.assert_not_called()

    def test_mpr_without_subwindow_data_returns_after_histogram(self) -> None:
        app = _make_app(
            focused_subwindow_index=7,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={},
        )
        facade = ProjectionAppFacade(app)

        facade.on_projection_type_changed("aip")

        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(7)
        app._mpr_controller.display_mpr_slice.assert_not_called()


class TestOnProjectionSliceCountChanged:
    def test_updates_managers_widget_and_non_mpr_display(self) -> None:
        app = _make_app(current_dataset="dataset")
        app.slice_display_manager.projection_enabled = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_slice_count_changed(8)

        app.slice_display_manager.set_projection_slice_count.assert_called_once_with(8)
        app.intensity_projection_controls_widget.set_slice_count.assert_called_once_with(8)
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)
        app._display_slice.assert_called_once_with("dataset")
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()

    def test_mpr_slice_count_updates_subwindow_data_only(self) -> None:
        app = _make_app(
            focused_subwindow_index=5,
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={5: {"mpr_slice_index": 2}},
        )
        facade = ProjectionAppFacade(app)

        facade.on_projection_slice_count_changed(2)

        assert app.subwindow_data[5]["mpr_combine_slice_count"] == 2
        app._mpr_controller.display_mpr_slice.assert_called_once_with(5, 2)
        app._display_slice.assert_not_called()

    def test_non_mpr_without_projection_enabled_skips_display(self) -> None:
        app = _make_app(current_dataset="dataset")
        app.slice_display_manager.projection_enabled = False
        facade = ProjectionAppFacade(app)

        facade.on_projection_slice_count_changed(4)

        app._display_slice.assert_not_called()

    def test_debug_slice_count_logs_and_redisplays(self, monkeypatch) -> None:
        monkeypatch.setattr(projection_app_facade, "DEBUG_PROJECTION", True)
        print_mock = MagicMock()
        monkeypatch.setattr("builtins.print", print_mock)
        app = _make_app(current_dataset="dataset")
        app.slice_display_manager.projection_enabled = True
        facade = ProjectionAppFacade(app)

        facade.on_projection_slice_count_changed(6)

        app._display_slice.assert_called_once_with("dataset")
        assert print_mock.call_count >= 1
