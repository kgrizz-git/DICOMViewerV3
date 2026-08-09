"""
Unit tests for ``gui.study_index_info`` UI-agnostic copy helpers.

These describe where the local study index lives and how to format its metadata.
``open_study_index_location`` is exercised with ``QDesktopServices.openUrl``
monkeypatched so no folder is actually opened.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gui import study_index_info as sii

pytestmark = pytest.mark.qt


def _config(stub_path: str = "/tmp/idx/study_index.sqlite") -> MagicMock:
    cfg = MagicMock()
    cfg.get_study_index_db_path.return_value = stub_path
    return cfg


class TestPathsAndCopy:
    def test_study_index_db_path_delegates(self):
        cfg = _config("/x/y.sqlite")
        assert sii.study_index_db_path(cfg) == "/x/y.sqlite"
        cfg.get_study_index_db_path.assert_called_once()

    def test_about_lines_include_path(self):
        cfg = _config("/x/y.sqlite")
        lines = sii.study_index_about_lines(cfg)
        assert lines[0] == "Saved on this device at:"
        assert "/x/y.sqlite" in lines
        assert any("encrypted at rest" in ln for ln in lines)

    def test_credential_store_label_darwin(self, monkeypatch):
        monkeypatch.setattr(sii.sys, "platform", "darwin")
        assert sii.credential_store_label() == "macOS Keychain"

    def test_credential_store_label_windows(self, monkeypatch):
        monkeypatch.setattr(sii.sys, "platform", "win32")
        assert sii.credential_store_label() == "Windows Credential Manager"

    def test_credential_store_label_linux(self, monkeypatch):
        monkeypatch.setattr(sii.sys, "platform", "linux")
        assert "Secret Service" in sii.credential_store_label()

    def test_credential_store_note_includes_label(self):
        note = sii.credential_store_note()
        assert "DICOMViewerV3" in note


class TestFormatSize:
    def test_none_placeholder(self):
        assert sii.format_size_on_disk(None) == "Not created yet"

    def test_bytes(self):
        assert sii.format_size_on_disk(512) == "512 bytes"

    def test_kilobytes(self):
        assert sii.format_size_on_disk(1536) == "1.5 KB"

    def test_megabytes(self):
        assert sii.format_size_on_disk(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert sii.format_size_on_disk(3 * 1024**3) == "3.0 GB"

    def test_gigabytes_overflow_clamped(self):
        assert sii.format_size_on_disk(10 * 1024**4) == "10240.0 GB"


class TestFormatLastModified:
    def test_none_placeholder(self):
        assert sii.format_last_modified(None) == "Not created yet"

    def test_valid_mtime(self):
        import re

        out = sii.format_last_modified(0.0)
        # Format is YYYY-MM-DD HH:MM regardless of local timezone offset.
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", out) is not None

    def test_invalid_mtime_returns_empty(self):
        assert sii.format_last_modified(float("nan")) == ""

    def test_overflow_returns_empty(self):
        assert sii.format_last_modified(1e999) == ""


class TestOpenLocation:
    def test_opens_resolved_folder(self, qapp, tmp_path):
        db_dir = tmp_path / "idx" / "sub"
        db_dir.mkdir(parents=True)
        cfg = _config(str(db_dir / "study_index.sqlite"))
        with patch("PySide6.QtGui.QDesktopServices.openUrl", return_value=True) as opener:
            result = sii.open_study_index_location(cfg)
        assert result is True
        opener.assert_called_once()
        opened = opener.call_args.args[0].toLocalFile()
        assert opened == str(db_dir)

    def test_walks_up_to_existing_ancestor(self, qapp, tmp_path):
        cfg = _config(str(tmp_path / "a" / "b" / "study_index.sqlite"))
        with patch("PySide6.QtGui.QDesktopServices.openUrl", return_value=True) as opener:
            result = sii.open_study_index_location(cfg)
        assert result is True
        opened = opener.call_args.args[0].toLocalFile()
        assert opened == str(tmp_path)
