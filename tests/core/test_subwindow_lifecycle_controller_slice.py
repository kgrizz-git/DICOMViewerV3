"""Focused tests for SubwindowLifecycleController getters with a fake app."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from pydicom.dataset import Dataset
from PySide6.QtCore import QCoreApplication

from core import slice_display_pixels
from core.subwindow_lifecycle_controller import SubwindowLifecycleController


def _fake_app(*, focused: int = 0, datasets: list | None = None) -> SimpleNamespace:
    ds_list = datasets if datasets is not None else []
    subwindow_data = {
        focused: {
            "current_datasets": ds_list,
            "current_dataset": ds_list[0] if ds_list else None,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_slice_index": 0,
            "is_mpr": False,
        }
    }
    return SimpleNamespace(
        focused_subwindow_index=focused,
        subwindow_data=subwindow_data,
        subwindow_managers={},
        multi_window_layout=MagicMock(),
        config_manager=MagicMock(),
        current_studies={},
    )


def test_get_subwindow_dataset_and_uids() -> None:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3"
    app = _fake_app(datasets=[ds])
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_dataset(0) is ds
    assert ctrl.get_subwindow_study_uid(0) == "st"
    assert ctrl.get_subwindow_series_uid(0) == "se"
    assert ctrl.get_subwindow_slice_index(0) == 0


def test_get_subwindow_dataset_missing_returns_none() -> None:
    app = _fake_app()
    app.subwindow_data = {}
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_dataset(0) is None


def test_get_focused_subwindow_index() -> None:
    app = _fake_app(focused=2)
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_focused_subwindow_index() == 2

    # Controller returns the app field even when no subwindow_data entry exists.
    app.subwindow_data = {}
    app.focused_subwindow_index = 3
    assert ctrl.get_focused_subwindow_index() == 3


def test_get_subwindow_slice_index_mpr() -> None:
    app = _fake_app(focused=0)
    ctrl = SubwindowLifecycleController(app)
    app.subwindow_data[0]["is_mpr"] = True
    app.subwindow_data[0]["mpr_slice_index"] = 5
    assert ctrl.get_subwindow_slice_index(0) == 5

    # Check when is_mpr is False
    app.subwindow_data[0]["is_mpr"] = False
    app.subwindow_data[0]["current_slice_index"] = 2
    assert ctrl.get_subwindow_slice_index(0) == 2

    # Check missing subwindow_data
    assert ctrl.get_subwindow_slice_index(9) == 0


def test_get_subwindow_slice_display_manager() -> None:
    app = _fake_app()
    app.subwindow_managers[0] = {"slice_display_manager": "dummy_sdm"}
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_slice_display_manager(0) == "dummy_sdm"
    assert ctrl.get_subwindow_slice_display_manager(9) is None


def test_get_subwindow_datasets() -> None:
    app = _fake_app()
    app.subwindow_data[0]["current_datasets"] = ["d1", "d2"]
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_datasets(0) == ["d1", "d2"]
    assert ctrl.get_subwindow_datasets(9) is None


def test_get_histogram_callbacks_for_subwindow() -> None:
    app = _fake_app()

    # Missing manager
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_histogram_callbacks_for_subwindow(0) == {}

    # View state manager present
    vsm = MagicMock()
    vsm.current_window_center = 100
    vsm.current_window_width = 200
    vsm.use_rescaled_values = True
    vsm.rescale_slope = 1.0
    vsm.rescale_intercept = 0.0
    vsm.rescale_type = "HU"

    app.subwindow_managers[0] = {
        "view_state_manager": vsm,
        "slice_display_manager": MagicMock(),
    }
    app.config_manager.get_histogram_use_projection_pixels = lambda: True
    app.config_manager.set_histogram_use_projection_pixels = lambda x: None

    callbacks = ctrl.get_histogram_callbacks_for_subwindow(0)
    assert callbacks["get_window_center"]() == 100
    assert callbacks["get_window_width"]() == 200
    assert callbacks["get_use_rescaled"]()
    assert callbacks["get_rescale_params"]() == (1.0, 0.0, "HU")
    assert callbacks["get_histogram_use_projection_pixels"]() is True


def test_get_histogram_projection_enabled() -> None:
    app = _fake_app()
    ctrl = SubwindowLifecycleController(app)

    # Non-MPR with slice display manager
    sdm = MagicMock()
    sdm.projection_enabled = True
    app.subwindow_managers[0] = {"slice_display_manager": sdm}
    assert ctrl._get_histogram_projection_enabled(0) is True

    # MPR panes must use their combine flag, not the native display manager.
    app.subwindow_data[0]["is_mpr"] = True
    sdm.projection_enabled = False
    app.subwindow_data[0]["mpr_combine_enabled"] = True
    assert ctrl._get_histogram_projection_enabled(0) is True
    app.subwindow_data[0]["mpr_combine_enabled"] = False
    assert ctrl._get_histogram_projection_enabled(0) is False


def test_get_focused_subwindow() -> None:
    app = _fake_app()
    app.multi_window_layout.get_focused_subwindow.return_value = "dummy_container"
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_focused_subwindow() == "dummy_container"


def test_update_focused_subwindow_references_none() -> None:
    app = _fake_app()
    app.multi_window_layout.get_focused_subwindow.return_value = None
    ctrl = SubwindowLifecycleController(app)

    # Should return early
    ctrl.update_focused_subwindow_references()
    assert app.focused_subwindow_index == 0  # untouched


def test_update_focused_subwindow_references_success() -> None:
    app = MagicMock()

    # Mock containers and viewer
    viewer = MagicMock()
    container = MagicMock()
    container.image_viewer = viewer

    app.multi_window_layout.get_focused_subwindow.return_value = container
    app.multi_window_layout.get_all_subwindows.return_value = [container]

    # Setup managers
    vsm = MagicMock()
    vsm.use_rescaled_values = False
    vsm.current_window_center = 100
    vsm.current_window_width = 200
    app.subwindow_managers = {
        0: {
            "view_state_manager": vsm,
            "slice_display_manager": MagicMock(),
            "roi_coordinator": MagicMock(),
            "measurement_coordinator": MagicMock(),
            "overlay_coordinator": MagicMock(),
            "roi_manager": MagicMock(),
            "measurement_tool": MagicMock(),
            "overlay_manager": MagicMock(),
        }
    }
    app.subwindow_data = {
        0: {
            "current_datasets": [],
            "current_dataset": None,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_slice_index": 0,
            "is_mpr": False,
        }
    }
    app.image_viewer = MagicMock()
    app.main_window = MagicMock()
    app.window_level_controls = MagicMock()
    app.slice_navigator = MagicMock()
    app.current_dataset = None
    app.keyboard_event_handler = None
    app.mouse_mode_handler = None
    app.current_studies = {}

    ctrl = SubwindowLifecycleController(app)
    ctrl.update_focused_subwindow_references()

    assert app.focused_subwindow_index == 0
    assert app.view_state_manager == vsm
    assert app.image_viewer == viewer


def test_get_histogram_current_pixel_array() -> None:
    app = _fake_app()
    ctrl = SubwindowLifecycleController(app)

    # Non-MPR returns None
    app.subwindow_data[0]["is_mpr"] = False
    assert ctrl._get_histogram_current_pixel_array(0) is None

    # MPR combine AIP mode
    app.subwindow_data[0]["is_mpr"] = True
    app.subwindow_data[0]["mpr_combine_mode"] = "aip"

    # Mock result
    result = MagicMock()
    result.n_slices = 10
    result.slices = [np.ones((10, 10)) for _ in range(10)]
    app.subwindow_data[0]["mpr_result"] = result
    app.subwindow_data[0]["mpr_slice_index"] = 2

    arr = ctrl._get_histogram_current_pixel_array(0)
    assert arr is not None
    assert arr.shape == (10, 10)


def test_get_histogram_projection_pixel_array_mpr_combine() -> None:
    app = _fake_app()
    ctrl = SubwindowLifecycleController(app)

    # MPR combine disabled returns None
    app.subwindow_data[0]["is_mpr"] = True
    app.subwindow_data[0]["mpr_combine_enabled"] = False
    assert ctrl._get_histogram_projection_pixel_array(0) is None

    # MPR combine enabled returns array
    app.subwindow_data[0]["mpr_combine_enabled"] = True
    app.subwindow_data[0]["mpr_combine_mode"] = "mip"
    result = MagicMock()
    result.n_slices = 10
    result.slices = [np.ones((10, 10)) for _ in range(10)]
    app.subwindow_data[0]["mpr_result"] = result
    app.subwindow_data[0]["mpr_slice_index"] = 2

    arr = ctrl._get_histogram_projection_pixel_array(0)
    assert arr is not None
    assert arr.shape == (10, 10)


def test_get_histogram_projection_pixel_array_non_mpr(monkeypatch) -> None:
    app = _fake_app()
    app.dicom_processor = MagicMock()
    ctrl = SubwindowLifecycleController(app)

    # Setup slice display manager with projection enabled
    sdm = MagicMock()
    sdm.projection_enabled = True
    sdm.projection_type = "aip"
    sdm.projection_slice_count = 3
    app.subwindow_managers[0] = {"slice_display_manager": sdm}
    app.subwindow_data[0]["current_datasets"] = ["d1", "d2", "d3"]
    app.subwindow_data[0]["current_slice_index"] = 1

    # Mock compute_intensity_projection_raw_array
    mock_proj = MagicMock(return_value=np.ones((10, 10)))
    monkeypatch.setattr(
        slice_display_pixels, "compute_intensity_projection_raw_array", mock_proj
    )

    arr = ctrl._get_histogram_projection_pixel_array(0)
    assert arr is not None
    assert arr.shape == (10, 10)
    mock_proj.assert_called_once_with(
        app.dicom_processor, "aip", 3, ["d1", "d2", "d3"], 1
    )


def test_display_rois_for_subwindow() -> None:
    app = _fake_app()
    ctrl = SubwindowLifecycleController(app)

    # No manager
    ctrl.display_rois_for_subwindow(9)

    # Manager present
    app.subwindow_managers[0] = {}
    ctrl.display_rois_for_subwindow(0)


def test_ensure_all_subwindows_have_managers() -> None:
    app = MagicMock()
    container = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = [container]
    app.subwindow_managers = {}

    ctrl = SubwindowLifecycleController(app)
    ctrl.ensure_all_subwindows_have_managers()

    # Verify managers creation was triggered
    assert app._create_managers_for_subwindow.call_count == 1
    app._create_managers_for_subwindow.assert_called_with(0, container)


def test_on_layout_changed() -> None:
    app = MagicMock()
    container = MagicMock()
    container.isVisible.return_value = True
    container.image_viewer.cursor.return_value = "dummy_cursor"
    app.multi_window_layout.get_all_subwindows.return_value = [container]

    ctrl = SubwindowLifecycleController(app)
    ctrl.on_layout_changed("2x2")

    app.config_manager.set_multi_window_layout.assert_called_with("2x2")
    app.main_window.set_layout_mode.assert_called_with("2x2")
    assert container.image_viewer.set_mouse_mode.call_count == 1


def test_on_main_window_layout_changed(qapp) -> None:
    # Depends on the session qapp fixture for QTimer.singleShot support. Do not
    # construct a QCoreApplication here: it is non-GUI, and owning the process
    # would make every later widget test in this worker abort. See
    # dev-docs/plans/completed/TEST_SUITE_PARALLELIZATION_PLAN.md.
    app = MagicMock()
    ctrl = SubwindowLifecycleController(app)
    ctrl.on_main_window_layout_changed("1x2")

    # Wait for the single shot timer to execute
    QCoreApplication.processEvents()

    app.multi_window_layout.set_layout.assert_called_with("1x2")
