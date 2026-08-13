"""Focused delegation and missing-state coverage for dialog action handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QMessageBox

from gui.actions import dialog_actions


def _app(**overrides):
    """Build a minimal synthetic application double for action handlers."""
    app = SimpleNamespace(
        main_window=SimpleNamespace(),
        dialog_coordinator=SimpleNamespace(),
        config_manager=SimpleNamespace(),
    )
    for key, value in overrides.items():
        setattr(app, key, value)
    return app


@pytest.mark.qt
def test_about_this_file_handles_missing_and_loaded_subwindows(qapp):
    coordinator = SimpleNamespace(open_about_this_file=MagicMock())
    app = _app(
        focused_subwindow_index=3,
        subwindow_data={},
        dialog_coordinator=coordinator,
        _get_file_path_for_dataset=MagicMock(),
    )

    dialog_actions.open_about_this_file(app)
    coordinator.open_about_this_file.assert_called_once_with(None, None)
    app._get_file_path_for_dataset.assert_not_called()

    ds = Dataset()
    ds.PatientName = "Synthetic^Patient"
    app.subwindow_data[3] = {
        "current_dataset": ds,
        "current_study_uid": "study",
        "current_series_uid": "series",
        "current_slice_index": 2,
    }
    app._get_file_path_for_dataset.return_value = "synthetic.dcm"
    dialog_actions.open_about_this_file(app)
    assert coordinator.open_about_this_file.call_args.args == (ds, "synthetic.dcm")


@pytest.mark.qt
@pytest.mark.parametrize("modality, expected", [(" CT ", "CT"), ("bogus", None), (None, None)])
def test_overlay_modality_selection_is_normalized(qapp, modality, expected):
    ds = SimpleNamespace(Modality=modality) if modality is not None else None
    coordinator = SimpleNamespace(open_overlay_config=MagicMock())
    app = _app(current_dataset=ds, dialog_coordinator=coordinator)

    dialog_actions.open_overlay_config(app)

    coordinator.open_overlay_config.assert_called_once_with(current_modality=expected)


@pytest.mark.qt
def test_wl_preset_manager_persists_signal_and_rebuilds(qapp, monkeypatch):
    saved_callback = {}
    dialog = MagicMock()
    dialog.presets_saved.connect.side_effect = lambda callback: saved_callback.setdefault(
        "callback", callback
    )
    monkeypatch.setattr(dialog_actions, "WLPresetManagerDialog", MagicMock(return_value=dialog))
    config = SimpleNamespace(
        get_wl_user_presets=MagicMock(return_value=[{"name": "old"}]),
        set_wl_user_presets=MagicMock(),
    )
    rebuild = MagicMock()
    app = _app(
        config_manager=config,
        slice_display_manager=SimpleNamespace(
            rebuild_window_level_presets_for_current_series=rebuild
        ),
    )

    dialog_actions.open_wl_preset_manager(app)
    new_presets = [{"name": "new"}]
    saved_callback["callback"](new_presets)

    config.set_wl_user_presets.assert_called_once_with(new_presets)
    rebuild.assert_called_once_with()
    dialog.exec.assert_called_once_with()


@pytest.mark.qt
def test_quick_window_level_builds_callback_and_preset_context(qapp, monkeypatch):
    dialog = MagicMock()
    monkeypatch.setattr(dialog_actions, "QuickWindowLevelDialog", MagicMock(return_value=dialog))
    preset_signal = MagicMock()
    main_window = SimpleNamespace(
        _apply_wl_preset_requested=preset_signal,
        _get_wl_preset_menu_context=MagicMock(return_value="context"),
        _get_active_wl_presets=MagicMock(return_value=[]),
    )
    apply_callback = MagicMock()
    app = _app(
        main_window=main_window,
        view_state_manager=SimpleNamespace(
            current_window_center=12.0,
            current_window_width=120.0,
            rescale_type="HU",
            handle_window_changed=apply_callback,
        ),
        window_level_controls=SimpleNamespace(
            center_range=(-10.0, 100.0), width_range=(1.0, 1000.0)
        ),
        _open_wl_preset_manager=MagicMock(),
    )

    dialog_actions.open_quick_window_level(app)

    kwargs = dialog_actions.QuickWindowLevelDialog.call_args.kwargs
    assert kwargs["initial_center"] == 12.0
    assert kwargs["initial_width"] == 120.0
    assert kwargs["center_range"] == (-10.0, 100.0)
    assert kwargs["unit"] == "HU"
    kwargs["on_preset_select"](4)
    preset_signal.emit.assert_called_once_with(4)
    dialog.exec.assert_called_once_with()


def test_quick_window_level_returns_without_view_state_manager():
    app = _app(view_state_manager=None)
    dialog_actions.open_quick_window_level(app)


def test_open_export_constructs_sorted_annotation_payload():
    managers = {
        2: {"roi_manager": "roi2", "measurement_tool": "measure2"},
        0: {"roi_manager": "roi0", "measurement_tool": "measure0"},
    }
    coordinator = SimpleNamespace(open_export=MagicMock())
    app = _app(
        window_level_controls=SimpleNamespace(get_window_level=lambda: (40, 400)),
        view_state_manager=SimpleNamespace(use_rescaled_values=True),
        slice_display_manager=SimpleNamespace(
            projection_enabled=True, projection_type="mip", projection_slice_count=5
        ),
        get_focused_subwindow_index=lambda: 2,
        subwindow_managers=managers,
        roi_manager="focused-roi",
        overlay_manager="overlay",
        measurement_tool="focused-measurement",
        dialog_coordinator=coordinator,
    )

    dialog_actions.open_export(app)

    kwargs = coordinator.open_export.call_args.kwargs
    assert kwargs["current_window_center"] == 40
    assert kwargs["focused_subwindow_index"] == 2
    assert [entry["roi_manager"] for entry in kwargs["subwindow_annotation_managers"]] == [
        "roi0",
        "roi2",
    ]
    assert kwargs["text_annotation_tool"] is None
    assert kwargs["projection_type"] == "mip"


@pytest.mark.parametrize(
    ("action", "method", "args"),
    [
        (dialog_actions.open_files, "open_files", ()),
        (dialog_actions.open_folder, "open_folder", ()),
        (dialog_actions.open_recent_file, "open_recent_file", ("recent.dcm",)),
        (dialog_actions.open_files_from_paths, "open_files_from_paths", (["a.dcm"],)),
        (dialog_actions.open_settings, "open_settings", ()),
        (dialog_actions.open_overlay_settings, "open_overlay_settings", ()),
        (dialog_actions.open_tag_viewer, "open_tag_viewer", ()),
        (dialog_actions.open_annotation_options, "open_annotation_options", ()),
        (dialog_actions.open_quick_start_guide, "open_quick_start_guide", ()),
        (dialog_actions.open_user_documentation_in_browser, "open_user_documentation_in_browser", ()),
        (dialog_actions.open_fusion_technical_doc, "open_fusion_technical_doc", ()),
        (dialog_actions.open_tag_export, "open_tag_export", ()),
    ],
)
def test_simple_dialog_and_file_actions_delegate(action, method, args):
    target = MagicMock()
    if method == "open_files":
        app = _app(_file_series_coordinator=SimpleNamespace(open_files=target))
    elif method == "open_folder":
        app = _app(_file_series_coordinator=SimpleNamespace(open_folder=target))
    elif method == "open_recent_file":
        app = _app(_file_series_coordinator=SimpleNamespace(open_recent_file=target))
    elif method == "open_files_from_paths":
        app = _app(_file_series_coordinator=SimpleNamespace(open_files_from_paths=target))
    else:
        app = _app(dialog_coordinator=SimpleNamespace(**{method: target}))
        if method == "open_tag_viewer":
            app.current_dataset = "dataset"
            app.privacy_view_enabled = True

    action(app, *args)

    target.assert_called_once()


@pytest.mark.qt
def test_study_index_warning_and_open_paths_callback(qapp, monkeypatch):
    warning = MagicMock()
    warning.dismissed_permanently = True
    search = MagicMock()
    monkeypatch.setattr(dialog_actions, "StudyIndexPassphraseWarningDialog", MagicMock(return_value=warning))
    monkeypatch.setattr(dialog_actions, "StudyIndexSearchDialog", MagicMock(return_value=search))
    config = SimpleNamespace(
        get_study_index_passphrase_warning_dismissed=MagicMock(return_value=False),
        set_study_index_passphrase_warning_dismissed=MagicMock(),
    )
    signal = MagicMock()
    app = _app(
        config_manager=config,
        study_index_service=MagicMock(),
        main_window=SimpleNamespace(open_files_from_paths_requested=signal),
    )

    dialog_actions.open_study_index_search(app)

    warning.exec.assert_called_once_with()
    config.set_study_index_passphrase_warning_dismissed.assert_called_once_with(True)
    search.exec.assert_called_once_with()
    callback = dialog_actions.StudyIndexSearchDialog.call_args.kwargs["open_paths_callback"]
    callback(["synthetic/path"])
    signal.emit.assert_called_once_with(["synthetic/path"])


@pytest.mark.qt
def test_structured_report_browser_rejects_missing_invalid_and_mpr(monkeypatch, qapp):
    info = MagicMock()
    monkeypatch.setattr(QMessageBox, "information", info)
    app = _app(
        main_window=object(),
        get_focused_subwindow_index=MagicMock(return_value=0),
        subwindow_data={0: {"is_mpr": True}},
        _get_subwindow_dataset=MagicMock(return_value=None),
    )

    dialog_actions.open_structured_report_browser(app)
    assert "MPR" in info.call_args.args[2]
    app.subwindow_data[0] = {}
    dialog_actions.open_structured_report_browser(app)
    assert "No DICOM" in info.call_args.args[2]
    app._get_subwindow_dataset.return_value = Dataset()
    dialog_actions.open_structured_report_browser(app)
    assert "not a Structured Report" in info.call_args.args[2]


@pytest.mark.qt
def test_structured_report_browser_delegates_sr_dataset_and_privacy_callback(qapp):
    coordinator = SimpleNamespace(
        open_structured_report_browser=MagicMock(), open_tag_viewer=MagicMock()
    )
    config = SimpleNamespace(get_privacy_view=MagicMock(return_value=True))
    ds = Dataset()
    ds.Modality = "SR"
    app = _app(
        dialog_coordinator=coordinator,
        config_manager=config,
        get_focused_subwindow_index=MagicMock(return_value=1),
        subwindow_data={1: {}},
        _get_subwindow_dataset=MagicMock(return_value=ds),
    )

    dialog_actions.open_structured_report_browser(app)

    kwargs = coordinator.open_structured_report_browser.call_args.kwargs
    assert coordinator.open_structured_report_browser.call_args.args == (ds,)
    assert kwargs["get_privacy_enabled"] is config.get_privacy_view
    kwargs["open_tag_viewer_callback"](ds)
    coordinator.open_tag_viewer.assert_called_once_with(ds, privacy_mode=True)
