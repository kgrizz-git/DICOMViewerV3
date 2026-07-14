"""
Tests for large-file confirmation before DICOM load starts.

Verifies collection logic, threshold boundary, and that open paths abort when
the user cancels the confirmation dialog.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gui.file_operations_handler import (
    LARGE_FILE_WARNING_THRESHOLD_MB,
    FileOperationsHandler,
)


def _write_bytes(path: str, size: int) -> None:
    with open(path, "wb") as handle:
        if size > 0:
            handle.seek(size - 1)
            handle.write(b"\0")


def _make_handler(
    file_dialog: MagicMock | None = None,
    *,
    confirm_large_files: bool = True,
) -> FileOperationsHandler:
    dialog = file_dialog or MagicMock()
    dialog.confirm_large_files = MagicMock(return_value=confirm_large_files)
    return FileOperationsHandler(
        dicom_loader=MagicMock(),
        dicom_organizer=MagicMock(),
        file_dialog=dialog,
        config_manager=MagicMock(),
        main_window=MagicMock(),
        clear_data_callback=MagicMock(),
        load_first_slice_callback=MagicMock(),
        update_status_callback=MagicMock(),
    )


@pytest.mark.qt
def test_collect_large_files_empty_list(qapp):
    handler = _make_handler()
    assert handler._collect_large_files([]) == []


@pytest.mark.qt
def test_collect_large_files_respects_threshold(qapp, tmp_path):
    small = tmp_path / "small.dcm"
    large = tmp_path / "large.dcm"
    threshold_bytes = int(LARGE_FILE_WARNING_THRESHOLD_MB * 1024 * 1024)
    _write_bytes(str(small), threshold_bytes)
    _write_bytes(str(large), threshold_bytes + 1)

    handler = _make_handler()
    found = handler._collect_large_files([str(small), str(large)])

    assert len(found) == 1
    assert found[0][0] == "large.dcm"
    assert found[0][1] > LARGE_FILE_WARNING_THRESHOLD_MB


@pytest.mark.qt
def test_check_large_files_skips_dialog_when_none(qapp, tmp_path):
    small = tmp_path / "small.dcm"
    _write_bytes(str(small), 1024)
    dialog = MagicMock()
    handler = _make_handler(dialog)

    assert handler._check_large_files([str(small)]) is True
    dialog.confirm_large_files.assert_not_called()


@pytest.mark.qt
def test_check_large_files_cancel_returns_false(qapp, tmp_path):
    large = tmp_path / "big.dcm"
    threshold_bytes = int(LARGE_FILE_WARNING_THRESHOLD_MB * 1024 * 1024)
    _write_bytes(str(large), threshold_bytes + 1)
    handler = _make_handler(confirm_large_files=False)

    assert handler._check_large_files([str(large)]) is False
    handler.file_dialog.confirm_large_files.assert_called_once()
    _args, kwargs = handler.file_dialog.confirm_large_files.call_args
    listed = kwargs["large_files"]
    assert listed[0][0] == "big.dcm"


@pytest.mark.qt
def test_check_large_files_continue_returns_true(qapp, tmp_path):
    large = tmp_path / "big.dcm"
    threshold_bytes = int(LARGE_FILE_WARNING_THRESHOLD_MB * 1024 * 1024)
    _write_bytes(str(large), threshold_bytes + 1)
    handler = _make_handler(confirm_large_files=True)

    assert handler._check_large_files([str(large)]) is True


@pytest.mark.qt
def test_open_paths_aborts_before_pipeline_on_cancel(qapp, tmp_path):
    large = tmp_path / "drop.dcm"
    threshold_bytes = int(LARGE_FILE_WARNING_THRESHOLD_MB * 1024 * 1024)
    _write_bytes(str(large), threshold_bytes + 1)
    handler = _make_handler(confirm_large_files=False)

    with patch("gui.file_operations_handler.run_load_pipeline_async") as pipeline:
        handler.open_paths([str(large)])
        pipeline.assert_not_called()


@pytest.mark.qt
def test_open_paths_starts_pipeline_when_continue(qapp, tmp_path):
    large = tmp_path / "drop.dcm"
    threshold_bytes = int(LARGE_FILE_WARNING_THRESHOLD_MB * 1024 * 1024)
    _write_bytes(str(large), threshold_bytes + 1)
    handler = _make_handler(confirm_large_files=True)
    handler.config_manager.add_recent_file = MagicMock()
    handler.main_window.update_recent_menu = MagicMock()

    with patch("gui.file_operations_handler.run_load_pipeline_async") as pipeline:
        handler.open_paths([str(large)])
        pipeline.assert_called_once()
