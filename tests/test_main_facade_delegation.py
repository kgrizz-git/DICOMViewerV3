"""
Facade / action delegation regression tests for DICOMViewerApp (Phase 0).

Asserts that thin ``main.py`` methods forward to ``ExportAppFacade``,
``QAAppFacade``, and ``MprController`` with the expected arguments.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import with_test_config_manager
from pydicom.dataset import Dataset

import main as main_module
from qa.analysis_types import QAResult


@pytest.mark.qt
def test_open_export_delegates_to_export_facade(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        monkeypatch.setattr(app, "_export_app_facade", mock_facade)
        app._open_export()
        mock_facade.open_export.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_open_export_screenshots_delegates_to_export_facade(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        monkeypatch.setattr(app, "_export_app_facade", mock_facade)
        app._open_export_screenshots()
        mock_facade.open_export_screenshots.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_resolve_focused_series_ordered_paths_delegates(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    expected = ("study", "series", "CT", ["/a.dcm"], [Dataset()])
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        mock_facade.resolve_focused_series_ordered_paths.return_value = expected
        monkeypatch.setattr(app, "_export_app_facade", mock_facade)
        assert app._resolve_focused_series_ordered_paths() == expected
        mock_facade.resolve_focused_series_ordered_paths.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_prompt_save_path_forwards_arguments(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        mock_facade.prompt_save_path.return_value = "/out/file.json"
        monkeypatch.setattr(app, "_export_app_facade", mock_facade)
        result = app._prompt_save_path(
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
    finally:
        restore()


@pytest.mark.qt
def test_on_save_mpr_as_dicom_delegates_to_mpr_controller(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        mock_save = MagicMock()
        monkeypatch.setattr(app._mpr_controller, "prompt_save_mpr_as_dicom", mock_save)
        app._on_save_mpr_as_dicom()
        mock_save.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_qa_build_preflight_warnings_delegates(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    datasets = [Dataset()]
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        mock_facade.build_preflight_warnings.return_value = ["warn"]
        monkeypatch.setattr(app, "_qa_app_facade", mock_facade)
        result = app._qa_build_preflight_warnings(
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
    finally:
        restore()


@pytest.mark.qt
def test_qa_user_confirms_preflight_delegates(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        mock_facade.user_confirms_preflight.return_value = True
        monkeypatch.setattr(app, "_qa_app_facade", mock_facade)
        assert app._qa_user_confirms_preflight(["a", "b"]) is True
        mock_facade.user_confirms_preflight.assert_called_once_with(["a", "b"])
    finally:
        restore()


@pytest.mark.qt
def test_show_qa_result_dialog_delegates(tmp_path, monkeypatch):
    restore, _ = with_test_config_manager(tmp_path)
    result = QAResult(success=True, analysis_type="test")
    try:
        app = main_module.DICOMViewerApp()
        mock_facade = MagicMock()
        monkeypatch.setattr(app, "_qa_app_facade", mock_facade)
        app._show_qa_result_dialog("Title", result)
        mock_facade.show_qa_result_dialog.assert_called_once_with("Title", result)
    finally:
        restore()
