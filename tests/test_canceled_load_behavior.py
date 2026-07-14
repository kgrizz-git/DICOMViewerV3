"""
Regression tests for canceled folder/file load behavior and study-index auto-add.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.loading_pipeline import format_cancelled_partial_status, run_load_pipeline
from core.study_index.index_service import LocalStudyIndexService


def test_format_cancelled_partial_status_includes_total_when_known() -> None:
    msg = format_cancelled_partial_status(3, 10)
    assert "3 of 10" in msg
    assert "Study index update skipped" in msg


def test_format_cancelled_partial_status_without_total() -> None:
    msg = format_cancelled_partial_status(5, 5)
    assert "5 file(s) loaded" in msg
    assert "Study index update skipped" in msg


def test_run_load_pipeline_cancelled_skips_index_callback_flag() -> None:
    """Partial cancel still displays data but passes was_cancelled to on_load_success."""
    datasets = [MagicMock(filename="/tmp/a.dcm")]  # NOSONAR - fake filename on a mock, never touches the filesystem
    loader = MagicMock()
    loader.get_failed_files.return_value = []
    loader.get_extension_skipped_count.return_value = 0
    loader.get_attempted_file_count.return_value = 10

    loading_manager = MagicMock()
    loading_manager.is_cancelled.return_value = True
    loading_manager.was_dialog_cancelled.return_value = False

    merge_result = MagicMock()
    merge_result.new_series = [("1.2.3", "1.2.3.4")]
    merge_result.appended_series = []
    merge_result.skipped_file_count = 0
    merge_result.added_file_count = 1

    organizer = MagicMock()
    organizer.merge_batch.return_value = merge_result
    organizer.studies = {}

    status_messages: list[str] = []
    on_load_success = MagicMock()

    with patch("core.loading_pipeline.QApplication.processEvents"), patch(
        "core.loading_pipeline.QTimer.singleShot"
    ):
        result = run_load_pipeline(
            loader_fn=lambda _cb: datasets,
            source_dir="/study",
            source_name="study",
            file_paths_for_merge=None,
            loader=loader,
            organizer=organizer,
            loading_manager=loading_manager,
            progress_max=10,
            main_window=MagicMock(),
            file_dialog=MagicMock(),
            load_first_slice_callback=MagicMock(),
            update_status_callback=status_messages.append,
            on_load_success=on_load_success,
        )

    assert result[0] is datasets
    on_load_success.assert_called_once()
    _args, kwargs = on_load_success.call_args
    assert kwargs.get("was_cancelled") is True
    assert status_messages
    assert "Study index update skipped" in status_messages[-1]


def test_schedule_index_after_load_skips_when_cancelled() -> None:
    config = MagicMock()
    config.get_study_index_auto_add_on_open.return_value = True
    service = LocalStudyIndexService(config)
    with patch(
        "core.study_index.index_service.StudyIndexWriteThread"
    ) as write_thread_cls:
        service.schedule_index_after_load(
            [MagicMock()],
            ["/tmp/a.dcm"],  # NOSONAR - fake path, StudyIndexWriteThread is patched so no filesystem write occurs
            "/study",
            MagicMock(),
            was_cancelled=True,
        )
        write_thread_cls.assert_not_called()
