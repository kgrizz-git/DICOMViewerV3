"""
Facade / action delegation regression tests for DICOMViewerApp (Phase 2).

Asserts that thin ``main.py`` methods forward to ``ExportAppFacade``,
``QAAppFacade``, and ``MprController`` with the expected arguments.

Phase 2: only one real ``DICOMViewerApp()`` smoke anchor; remaining tests
invoke the actual mixin method (the defining code path) on a narrow mock
harness carrying only the facade attribute the method touches.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import with_test_config_manager
from pydicom.dataset import Dataset

import main as main_module
from main_app_subwindow_management import MPRNavigationMixin
from main_app_ui_and_files import FileOperationsMixin, UIHandlersMixin
from qa.analysis_types import QAResult

# ── Smoke anchor: one real DICOMViewerApp() ────────────────────────────────


@pytest.mark.qt
def test_smoke_config_and_export_delegation(tmp_path, monkeypatch):
    """One real DICOMViewerApp: config isolation + export delegation wired."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        assert app.config_manager is not None
        mock_facade = MagicMock()
        monkeypatch.setattr(app, "_export_app_facade", mock_facade)
        app._open_export()
        mock_facade.open_export.assert_called_once_with()
    finally:
        restore()


# ── Thin delegation harnesses (no real DICOMViewerApp) ─────────────────────
# Each test imports the *actual* unbound mixin method and calls it on a
# minimal MagicMock carrying only the facade attribute the method touches.


def test_open_export_delegates_to_export_facade():
    mock_app = MagicMock(spec=FileOperationsMixin)
    mock_facade = MagicMock()
    mock_app._export_app_facade = mock_facade
    FileOperationsMixin._open_export(mock_app)
    mock_facade.open_export.assert_called_once_with()


def test_open_export_screenshots_delegates_to_export_facade():
    mock_app = MagicMock(spec=FileOperationsMixin)
    mock_facade = MagicMock()
    mock_app._export_app_facade = mock_facade
    FileOperationsMixin._open_export_screenshots(mock_app)
    mock_facade.open_export_screenshots.assert_called_once_with()


def test_resolve_focused_series_ordered_paths_delegates():
    expected = ("study", "series", "CT", ["/a.dcm"], [Dataset()])
    mock_app = MagicMock(spec=FileOperationsMixin)
    mock_facade = MagicMock()
    mock_facade.resolve_focused_series_ordered_paths.return_value = expected
    mock_app._export_app_facade = mock_facade
    assert FileOperationsMixin._resolve_focused_series_ordered_paths(mock_app) == expected
    mock_facade.resolve_focused_series_ordered_paths.assert_called_once_with()


def test_prompt_save_path_forwards_arguments():
    mock_app = MagicMock(spec=FileOperationsMixin)
    mock_facade = MagicMock()
    mock_facade.prompt_save_path.return_value = "/out/file.json"
    mock_app._export_app_facade = mock_facade
    result = FileOperationsMixin._prompt_save_path(
        mock_app,
        "Save",
        "default.json",
        "JSON (*.json)",
        remember_pylinac_output_dir=True,
    )
    assert result == "/out/file.json"
    mock_facade.prompt_save_path.assert_called_once_with(
        "Save",
        "default.json",
        "JSON (*.json)",
        remember_pylinac_output_dir=True,
    )


def test_on_save_mpr_as_dicom_delegates_to_mpr_controller():
    mock_app = MagicMock(spec=MPRNavigationMixin)
    mock_controller = MagicMock()
    mock_app._mpr_controller = mock_controller
    MPRNavigationMixin._on_save_mpr_as_dicom(mock_app)
    mock_controller.prompt_save_mpr_as_dicom.assert_called_once_with()


def test_qa_build_preflight_warnings_delegates():
    datasets = [Dataset()]
    mock_app = MagicMock(spec=UIHandlersMixin)
    mock_facade = MagicMock()
    mock_facade.build_preflight_warnings.return_value = ["warn"]
    mock_app._qa_app_facade = mock_facade
    result = UIHandlersMixin._qa_build_preflight_warnings(
        mock_app,
        "CT",
        True,
        "/folder",
        datasets,
        "CT",
    )
    assert result == ["warn"]
    mock_facade.build_preflight_warnings.assert_called_once_with(
        "CT",
        True,
        "/folder",
        datasets,
        "CT",
    )


def test_qa_user_confirms_preflight_delegates():
    mock_app = MagicMock(spec=UIHandlersMixin)
    mock_facade = MagicMock()
    mock_facade.user_confirms_preflight.return_value = True
    mock_app._qa_app_facade = mock_facade
    assert UIHandlersMixin._qa_user_confirms_preflight(mock_app, ["a", "b"]) is True
    mock_facade.user_confirms_preflight.assert_called_once_with(["a", "b"])


def test_show_qa_result_dialog_delegates():
    result = QAResult(success=True, analysis_type="test")
    mock_app = MagicMock(spec=UIHandlersMixin)
    mock_facade = MagicMock()
    mock_app._qa_app_facade = mock_facade
    UIHandlersMixin._show_qa_result_dialog(mock_app, "Title", result)
    mock_facade.show_qa_result_dialog.assert_called_once_with("Title", result)
