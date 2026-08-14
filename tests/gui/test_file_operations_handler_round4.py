"""Tests for src/gui/file_operations_handler.py — round 4 coverage.

Focuses on path selection, cancellation, guard/error paths, and delegated
calls using mocks.  No production code is modified.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gui.file_operations_handler import (
    FileOperationsHandler,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_handler(**overrides):
    """Build a FileOperationsHandler with all dependencies mocked."""
    loader = MagicMock()
    organizer = MagicMock()
    dialog = MagicMock()
    config = MagicMock()
    window = MagicMock()

    defaults = dict(  # noqa: C408
        dicom_loader=loader,
        dicom_organizer=organizer,
        file_dialog=dialog,
        config_manager=config,
        main_window=window,
        clear_data_callback=MagicMock(),
        load_first_slice_callback=MagicMock(),
        update_status_callback=MagicMock(),
        on_load_success_callback=None,
        pipeline_complete_callback=None,
    )
    defaults.update(overrides)
    handler = FileOperationsHandler(**defaults)
    return handler, loader, dialog, config, window


def _tiny_file(tmp_path: Path, name: str = "a.dcm", size: int = 100) -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * size)
    return p


def _large_file(tmp_path: Path, name: str = "big.dcm", size_mb: float = 30.0) -> Path:
    p = tmp_path / name
    p.write_bytes(b"\x00" * int(size_mb * 1024 * 1024))
    return p


# ---------------------------------------------------------------------------
# _collect_large_files
# ---------------------------------------------------------------------------

class TestCollectLargeFiles:
    """Unit tests for _collect_large_files."""

    def test_empty_list(self):
        handler, *_ = _make_handler()
        assert handler._collect_large_files([]) == []

    def test_small_file_below_threshold(self, tmp_path):
        handler, *_ = _make_handler()
        f = _tiny_file(tmp_path, "small.dcm", 100)
        assert handler._collect_large_files([str(f)]) == []

    def test_large_file_above_threshold(self, tmp_path):
        handler, *_ = _make_handler()
        f = _large_file(tmp_path, "big.dcm", 30.0)
        result = handler._collect_large_files([str(f)])
        assert len(result) == 1
        assert result[0][0] == "big.dcm"
        assert result[0][1] == pytest.approx(30.0, abs=0.1)

    def test_nonexistent_path_skipped(self, tmp_path):
        handler, *_ = _make_handler()
        assert handler._collect_large_files(["/no/such/file.dcm"]) == []

    def test_directory_skipped(self, tmp_path):
        handler, *_ = _make_handler()
        d = tmp_path / "subdir"
        d.mkdir()
        assert handler._collect_large_files([str(d)]) == []

    def test_oserror_on_getsize_skipped(self, tmp_path, monkeypatch):
        handler, *_ = _make_handler()
        f = _tiny_file(tmp_path, "x.dcm")
        monkeypatch.setattr(os.path, "getsize", _raises_oserror)
        assert handler._collect_large_files([str(f)]) == []

    def test_sorted_descending_by_size(self, tmp_path):
        handler, *_ = _make_handler()
        small = _tiny_file(tmp_path, "s.dcm", 100)
        big = _large_file(tmp_path, "b.dcm", 40.0)
        mid = _large_file(tmp_path, "m.dcm", 30.0)
        result = handler._collect_large_files(
            [str(small), str(big), str(mid)], threshold_mb=1.0
        )
        names = [r[0] for r in result]
        assert names == ["b.dcm", "m.dcm"]

    def test_custom_threshold(self, tmp_path):
        handler, *_ = _make_handler()
        f = _tiny_file(tmp_path, "t.dcm", 200)
        # threshold 0.0001 MB = ~100 bytes; 200 bytes > threshold
        result = handler._collect_large_files([str(f)], threshold_mb=0.0001)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _check_large_files
# ---------------------------------------------------------------------------

class TestCheckLargeFiles:
    """Tests for _check_large_files — guard before starting a load."""

    def test_returns_true_when_no_large_files(self, tmp_path, qapp):
        handler, *_ = _make_handler()
        f = _tiny_file(tmp_path)
        assert handler._check_large_files([str(f)]) is True

    def test_returns_false_when_user_cancels(self, tmp_path, qapp):
        handler, _, dialog, _, _ = _make_handler()
        f = _large_file(tmp_path)
        dialog.confirm_large_files.return_value = False
        assert handler._check_large_files([str(f)]) is False
        dialog.confirm_large_files.assert_called_once()

    def test_returns_true_when_user_confirms(self, tmp_path, qapp):
        handler, _, dialog, _, _ = _make_handler()
        f = _large_file(tmp_path)
        dialog.confirm_large_files.return_value = True
        assert handler._check_large_files([str(f)]) is True

    def test_empty_list_returns_true(self, qapp):
        handler, *_ = _make_handler()
        assert handler._check_large_files([]) is True


# ---------------------------------------------------------------------------
# _on_pipeline_complete
# ---------------------------------------------------------------------------

class TestOnPipelineComplete:
    def test_calls_callback_when_set(self):
        cb = MagicMock()
        handler, *_ = _make_handler(pipeline_complete_callback=cb)
        handler._on_pipeline_complete([1], {"a": 1})
        cb.assert_called_once_with([1], {"a": 1})

    def test_noop_when_no_callback(self):
        handler, *_ = _make_handler(pipeline_complete_callback=None)
        handler._on_pipeline_complete([1], {"a": 1})  # no error


# ---------------------------------------------------------------------------
# open_files
# ---------------------------------------------------------------------------

class TestOpenFiles:
    """Tests for the open_files method."""

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_empty_dialog_returns_early(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, _, _ = _make_handler()
        dialog.open_files.return_value = []
        handler.open_files()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=True)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_all_files_skipped_shows_warning(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, _, window = _make_handler()
        dialog.open_files.return_value = ["/a.txt", "/b.txt"]
        handler.open_files()
        dialog.show_warning.assert_called_once()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_mixed_skip_filters_correctly(self, mock_pipeline, mock_skip, qapp):
        handler, loader, dialog, config, window = _make_handler()
        dialog.open_files.return_value = ["/a.txt", "/b.dcm"]

        def _skip(p):
            return p.endswith(".txt")

        mock_skip.side_effect = _skip
        handler.open_files()
        loader.set_extension_skipped_count.assert_called_once_with(1)
        mock_pipeline.assert_called_once()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_cancels_on_large_file_reject(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, config, _ = _make_handler()
        f = _large_file(tmp_path, "big.dcm")
        dialog.open_files.return_value = [str(f)]
        dialog.confirm_large_files.return_value = False
        handler.open_files()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_adds_first_path_to_recent(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, config, window = _make_handler()
        dialog.open_files.return_value = ["/x/y/f.dcm"]
        config.add_recent_file.return_value = None
        handler.open_files()
        config.add_recent_file.assert_called_with("/x/y/f.dcm")
        window.update_recent_menu.assert_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_calls_pipeline_with_correct_request(self, mock_pipeline, mock_skip, qapp):
        handler, loader, dialog, config, window = _make_handler()
        dialog.open_files.return_value = ["/x/y/f.dcm"]
        handler.open_files()
        assert mock_pipeline.call_count == 1
        request = mock_pipeline.call_args[0][0]
        assert request.loader_fn is not None
        assert request.check_compression_errors is True
        assert request.file_paths_for_merge == ["/x/y/f.dcm"]

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_stores_worker_reference(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, _, _ = _make_handler()
        dialog.open_files.return_value = ["/x/y/f.dcm"]
        mock_pipeline.return_value = "worker_obj"
        handler.open_files()
        assert handler._active_worker == "worker_obj"


# ---------------------------------------------------------------------------
# open_folder
# ---------------------------------------------------------------------------

class TestOpenFolder:
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_empty_dialog_returns_early(self, mock_pipeline, qapp):
        handler, _, dialog, _, _ = _make_handler()
        dialog.open_folder.return_value = None
        handler.open_folder()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_adds_folder_to_recent(self, mock_pipeline, qapp, tmp_path):
        handler, _, dialog, config, window = _make_handler()
        dialog.open_folder.return_value = str(tmp_path)
        handler.open_folder()
        config.add_recent_file.assert_called_with(str(tmp_path))
        window.update_recent_menu.assert_called()

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_folder_rglob_exception_continues(self, mock_pipeline, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        dialog.open_folder.return_value = str(tmp_path)
        # Folder exists but rglob will just find nothing; pipeline fires
        handler.open_folder()
        mock_pipeline.assert_called_once()

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_pipeline_uses_load_directory(self, mock_pipeline, qapp, tmp_path):
        handler, loader, dialog, _, _ = _make_handler()
        dialog.open_folder.return_value = str(tmp_path)
        handler.open_folder()
        request = mock_pipeline.call_args[0][0]
        assert request.file_paths_for_merge is None
        assert request.check_compression_errors is False
        assert request.source_dir == str(tmp_path)
        assert request.source_name == tmp_path.name


# ---------------------------------------------------------------------------
# open_recent_file
# ---------------------------------------------------------------------------

class TestOpenRecentFile:
    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_not_found_shows_error_and_removes_from_recent(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, config, window = _make_handler()
        config.get_recent_files.return_value = ["/missing.dcm"]
        handler.open_recent_file("/missing.dcm")
        dialog.show_error.assert_called_once()
        config.save_config.assert_called_once()
        window.update_recent_menu.assert_called()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=True)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_not_found_not_in_recent_skips_removal(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, config, window = _make_handler()
        config.get_recent_files.return_value = ["/other.dcm"]
        handler.open_recent_file("/missing.dcm")
        dialog.show_error.assert_called_once()
        config.save_config.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=True)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_file_skipped_by_extension(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        f = _tiny_file(tmp_path, "readme.txt")
        handler.open_recent_file(str(f))
        dialog.show_warning.assert_called_once()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_file_cancels_on_large_file_reject(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        f = _large_file(tmp_path, "big.dcm")
        dialog.confirm_large_files.return_value = False
        handler.open_recent_file(str(f))
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_file_loads_via_pipeline(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, loader, dialog, _, _ = _make_handler()
        f = _tiny_file(tmp_path, "scan.dcm")
        handler.open_recent_file(str(f))
        mock_pipeline.assert_called_once()
        request = mock_pipeline.call_args[0][0]
        assert request.file_paths_for_merge == [str(f)]
        assert request.check_compression_errors is True
        loader.set_extension_skipped_count.assert_called_with(0)

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_folder_loads_via_pipeline(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, loader, dialog, _, _ = _make_handler()
        handler.open_recent_file(str(tmp_path))
        mock_pipeline.assert_called_once()
        request = mock_pipeline.call_args[0][0]
        assert request.file_paths_for_merge is None
        assert request.check_compression_errors is False


# ---------------------------------------------------------------------------
# open_paths
# ---------------------------------------------------------------------------

class TestOpenPaths:
    def test_empty_list_noop(self, qapp):
        handler, *_ = _make_handler()
        handler.open_paths([])  # no error

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_nonexistent_paths_skipped(self, mock_pipeline, qapp):
        handler, _, dialog, _, _ = _make_handler()
        handler.open_paths(["/no/such/file.dcm"])
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_all_skipped_shows_warning(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        f = _tiny_file(tmp_path, "notes.txt")
        mock_skip.return_value = True
        handler.open_paths([str(f)])
        dialog.show_warning.assert_called_once()
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_files_triggers_pipeline(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, config, window = _make_handler()
        f = _tiny_file(tmp_path, "scan.dcm")
        handler.open_paths([str(f)])
        mock_pipeline.assert_called_once()
        config.add_recent_file.assert_called_with(str(f))
        window.update_recent_menu.assert_called()

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_folder_triggers_pipeline(self, mock_pipeline, qapp, tmp_path):
        handler, _, dialog, config, window = _make_handler()
        handler.open_paths([str(tmp_path)])
        mock_pipeline.assert_called_once()
        request = mock_pipeline.call_args[0][0]
        assert request.file_paths_for_merge is None
        config.add_recent_file.assert_called_with(str(tmp_path))

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_folders_take_priority_over_files(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        f = _tiny_file(tmp_path, "scan.dcm")
        # Pass both folder and file — folder branch should win
        handler.open_paths([str(tmp_path), str(f)])
        mock_pipeline.assert_called_once()
        request = mock_pipeline.call_args[0][0]
        assert request.file_paths_for_merge is None

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_mixed_skip_partial_files(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, loader, dialog, _, _ = _make_handler()
        good = _tiny_file(tmp_path, "good.dcm")
        bad = _tiny_file(tmp_path, "bad.txt")

        def _skip(p):
            return p.endswith(".txt")

        mock_skip.side_effect = _skip
        handler.open_paths([str(good), str(bad)])
        loader.set_extension_skipped_count.assert_called_with(1)
        mock_pipeline.assert_called_once()

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_large_file_cancel_in_files(self, mock_pipeline, mock_skip, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        f = _large_file(tmp_path, "big.dcm")
        dialog.confirm_large_files.return_value = False
        handler.open_paths([str(f)])
        mock_pipeline.assert_not_called()

    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_large_file_cancel_in_folder(self, mock_pipeline, qapp, tmp_path):
        handler, _, dialog, _, _ = _make_handler()
        # Create a folder with a large file inside
        _large_file(tmp_path, "big.dcm", 30.0)
        dialog.confirm_large_files.return_value = False
        handler.open_paths([str(tmp_path)])
        mock_pipeline.assert_not_called()


# ---------------------------------------------------------------------------
# _get_first_study_series_by_dicom
# ---------------------------------------------------------------------------

class TestGetFirstStudySeriesByDicom:
    def test_empty_studies(self):
        handler, *_ = _make_handler()
        assert handler._get_first_study_series_by_dicom({}) is None

    def test_study_with_empty_series_dict(self):
        handler, *_ = _make_handler()
        assert handler._get_first_study_series_by_dicom({"s1": {}}) is None

    def test_study_with_empty_datasets(self):
        handler, *_ = _make_handler()
        assert handler._get_first_study_series_by_dicom({"s1": {"se1": []}}) is None

    def test_returns_first_study_first_series(self):
        handler, *_ = _make_handler()
        ds = SimpleNamespace(SeriesNumber=2)
        studies = {"s1": {"se1": [ds]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result == ("s1", "se1")

    def test_sorts_by_series_number(self):
        handler, *_ = _make_handler()
        ds_high = SimpleNamespace(SeriesNumber=10)
        ds_low = SimpleNamespace(SeriesNumber=1)
        studies = {"s1": {"se_high": [ds_high], "se_low": [ds_low]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result == ("s1", "se_low")

    def test_series_number_none_treated_as_zero(self):
        handler, *_ = _make_handler()
        ds = SimpleNamespace(SeriesNumber=None)
        studies = {"s1": {"se1": [ds]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result == ("s1", "se1")

    def test_series_number_non_numeric_treated_as_zero(self):
        handler, *_ = _make_handler()
        ds = SimpleNamespace(SeriesNumber="abc")
        studies = {"s1": {"se1": [ds]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result == ("s1", "se1")

    def test_skips_empty_series_in_first_study(self):
        handler, *_ = _make_handler()
        ds = SimpleNamespace(SeriesNumber=1)
        studies = {"s1": {"se_empty": [], "se_ok": [ds]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result == ("s1", "se_ok")

    def test_multiple_studies_picks_first(self):
        handler, *_ = _make_handler()
        ds1 = SimpleNamespace(SeriesNumber=1)
        ds2 = SimpleNamespace(SeriesNumber=1)
        studies = {"s_first": {"se1": [ds1]}, "s_second": {"se2": [ds2]}}
        result = handler._get_first_study_series_by_dicom(studies)
        assert result[0] == "s_first"


# ---------------------------------------------------------------------------
# load_first_slice
# ---------------------------------------------------------------------------

class TestLoadFirstSlice:
    def test_empty_studies_returns_none(self):
        handler, *_ = _make_handler()
        assert handler.load_first_slice({}) is None

    def test_no_valid_pair_returns_none(self):
        handler, *_ = _make_handler()
        assert handler.load_first_slice({"s1": {}}) is None

    def test_returns_slice_info(self):
        handler, *_ = _make_handler()
        ds = SimpleNamespace(SeriesNumber=1)
        studies = {"s1": {"se1": [ds, ds]}}
        result = handler.load_first_slice(studies)
        assert result is not None
        assert result["study_uid"] == "s1"
        assert result["series_uid"] == "se1"
        assert result["slice_index"] == 0
        assert result["total_slices"] == 2
        assert result["dataset"] is ds


# ---------------------------------------------------------------------------
# _should_skip_path_for_dicom (integration with real function)
# ---------------------------------------------------------------------------

class TestShouldSkipPathForDicom:
    """Direct tests of the real skip logic exercised by the handler."""

    def test_txt_file_skipped(self):
        from core.dicom_loader import should_skip_path_for_dicom
        assert should_skip_path_for_dicom("/x/readme.txt") is True

    def test_dcm_file_not_skipped(self):
        from core.dicom_loader import should_skip_path_for_dicom
        assert should_skip_path_for_dicom("/x/scan.dcm") is False

    def test_no_extension_not_skipped(self):
        from core.dicom_loader import should_skip_path_for_dicom
        assert should_skip_path_for_dicom("/x/noext") is False

    def test_hidden_file_not_skipped(self):
        from core.dicom_loader import should_skip_path_for_dicom
        assert should_skip_path_for_dicom("/x/.hidden") is False

    def test_office_temp_file_skipped(self):
        from core.dicom_loader import should_skip_path_for_dicom
        assert should_skip_path_for_dicom("/x/~$doc.docx") is True


# ---------------------------------------------------------------------------
# __init__ wiring
# ---------------------------------------------------------------------------

class TestInit:
    def test_stores_dependencies(self, qapp):
        handler, loader, dialog, config, window = _make_handler()
        assert handler.dicom_loader is loader
        assert handler.file_dialog is dialog
        assert handler.config_manager is config
        assert handler.main_window is window
        assert handler._active_worker is None

    def test_default_optional_callbacks_none(self, qapp):
        handler, *_ = _make_handler()
        assert handler._on_load_success_callback is None
        assert handler._pipeline_complete_callback is None

    def test_loading_manager_created(self, qapp):
        handler, *_ = _make_handler()
        assert handler._loading_manager is not None


# ---------------------------------------------------------------------------
# _active_worker GC-prevention attribute
# ---------------------------------------------------------------------------

class TestActiveWorker:
    def test_initially_none(self):
        handler, *_ = _make_handler()
        assert handler._active_worker is None

    @patch("gui.file_operations_handler.should_skip_path_for_dicom", return_value=False)
    @patch("gui.file_operations_handler.run_load_pipeline_async")
    def test_set_on_open_files(self, mock_pipeline, mock_skip, qapp):
        handler, _, dialog, _, _ = _make_handler()
        dialog.open_files.return_value = ["/a.dcm"]
        mock_pipeline.return_value = "worker_ref"
        handler.open_files()
        assert handler._active_worker == "worker_ref"


# ---------------------------------------------------------------------------
# PerfMark calls in _check_large_files
# ---------------------------------------------------------------------------

class TestCheckLargeFilesPerfMarks:
    @patch("gui.file_operations_handler.perf_mark")
    def test_perf_marks_emitted(self, mock_perf, qapp, tmp_path):
        handler, *_ = _make_handler()
        f = _tiny_file(tmp_path)
        handler._check_large_files([str(f)])
        assert mock_perf.call_count >= 1


# ---------------------------------------------------------------------------
# Error helper (for monkeypatch)
# ---------------------------------------------------------------------------

def _raises_oserror(*a, **kw):
    raise OSError("simulated")


# Ensure _raises_oserror is importable at module level for monkeypatch
# (used above in TestCollectLargeFiles.test_oserror_on_getsize_skipped)
