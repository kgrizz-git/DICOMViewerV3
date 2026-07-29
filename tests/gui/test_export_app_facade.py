"""Unit tests for ExportAppFacade prompt_save_path extension fallback behavior."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QFileDialog

from gui.export_app_facade import ExportAppFacade


class TestPromptSavePathExtensionFallback:
    """Tests for prompt_save_path file extension fallback logic."""

    @pytest.mark.parametrize(
        ("input_path", "filter_text", "expected_path"),
        [
            ("/path/to/report", "Excel Files (*.xlsx)", "/path/to/report.xlsx"),
            ("/path/to/report", "JSON Files (*.json)", "/path/to/report.json"),
            ("/path/to/report", "CSV Files (*.csv)", "/path/to/report.csv"),
            ("/path/to/report", "PNG Files (*.png)", "/path/to/report.png"),
            ("/path/to/report", "PDF Files (*.pdf)", "/path/to/report.pdf"),
            ("/path/to/report.", "JSON Files (*.json)", "/path/to/report.json"),
            ("/path/to/report.json", "Excel Files (*.xlsx)", "/path/to/report.json"),
            ("/path/to/report.xlsx", "JSON Files (*.json)", "/path/to/report.xlsx"),
        ],
    )
    def test_extension_fallback(self, qapp, input_path: str, filter_text: str, expected_path: str):
        mock_app = MagicMock()
        mock_app.main_window = None
        facade = ExportAppFacade(mock_app)

        with patch.object(QFileDialog, "exec", return_value=1), \
             patch.object(QFileDialog, "selectedFiles", return_value=[input_path]), \
             patch.object(QFileDialog, "selectedNameFilter", return_value=filter_text):
            result = facade.prompt_save_path("Save Title", "default_file", filter_text)
            assert result == expected_path

    def test_dialog_canceled(self, qapp):
        mock_app = MagicMock()
        mock_app.main_window = None
        facade = ExportAppFacade(mock_app)

        with patch.object(QFileDialog, "exec", return_value=0):
            result = facade.prompt_save_path("Save Title", "default_file", "JSON Files (*.json)")
            assert result == ""
