"""
Characterization tests for loading-pipeline helpers and async signal paths.

Covers shared message/path helpers plus the main async organized/finished/
error slots used by ``run_load_pipeline_async`` (Sonar S3776 slice).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.loading_pipeline import (
    LoadPipelineRequest,
    build_post_load_status,
    empty_load_error_message,
    failed_files_warning_message,
    resolve_merge_paths,
    run_load_pipeline,
    run_load_pipeline_async,
    update_loading_progress_dialog,
)
from core.loading_pipeline_async import (
    _AsyncLoadContext,
    _handle_error,
    _handle_finished,
    _handle_organized,
)


def test_resolve_merge_paths_prefers_explicit_list() -> None:
    datasets = [SimpleNamespace(filename="/ignored.dcm")]
    assert resolve_merge_paths(datasets, ["/a.dcm", "/b.dcm"]) == ["/a.dcm", "/b.dcm"]


def test_resolve_merge_paths_folder_mode_from_filenames() -> None:
    datasets = [
        SimpleNamespace(filename="/a.dcm"),
        SimpleNamespace(filename=None),
        SimpleNamespace(filename="/b.dcm"),
    ]
    assert resolve_merge_paths(datasets, None) == ["/a.dcm", "/b.dcm"]


@pytest.mark.parametrize(
    ("failed", "is_folder", "needle"),
    [
        ([], True, "No DICOM files found in folder."),
        ([("/x.dcm", "bad")], True, "1 file(s) could not be loaded"),
        ([], False, "No DICOM files could be loaded."),
        ([("/x.dcm", "bad")], False, "x.dcm: bad"),
    ],
)
def test_empty_load_error_message(failed, is_folder, needle) -> None:
    msg = empty_load_error_message(failed, is_folder_mode=is_folder)
    assert needle in msg


def test_failed_files_warning_message_none_when_empty() -> None:
    assert failed_files_warning_message([], is_folder_mode=True) is None


def test_failed_files_warning_message_folder_and_files() -> None:
    failed = [("/a.dcm", "err"), ("/b.dcm", "err2")]
    folder = failed_files_warning_message(failed, is_folder_mode=True)
    assert folder is not None and "2 file(s)" in folder
    files = failed_files_warning_message(failed, is_folder_mode=False)
    assert files is not None and "a.dcm: err" in files


def test_build_post_load_status_cancelled_and_compression_hint() -> None:
    merge = MagicMock()
    merge.new_series = [("s1", "ser1")]
    merge.appended_series = []
    merge.added_file_count = 2
    merge.skipped_file_count = 0

    loader = MagicMock()
    loader.get_attempted_file_count.return_value = 9
    cancelled = build_post_load_status(
        merge_result=merge,
        loader=loader,
        source_name="study",
        was_cancelled=True,
        check_compression_errors=False,
    )
    assert "Study index update skipped" in cancelled

    loader.get_failed_files.return_value = [
        (
            "/c.dcm",
            "JPEG Extended pixel data cannot be decoded (transfer syntax 1.2.840.10008.1.2.4.51).",
        ),
    ]
    loader.get_extension_skipped_count.return_value = 0
    ok = build_post_load_status(
        merge_result=merge,
        loader=loader,
        source_name="study",
        was_cancelled=False,
        check_compression_errors=True,
    )
    assert "compressed file(s) could not be decoded" in ok
    assert "pylibjpeg" not in ok.lower()


def test_update_loading_progress_dialog_honors_cancel() -> None:
    dlg = MagicMock()
    dlg.maximum.return_value = 1
    loading_manager = MagicMock()
    loading_manager.get_dialog.return_value = dlg
    loading_manager.is_cancelled.return_value = False
    loading_manager.was_dialog_cancelled.return_value = True
    started = [False]
    last = [0.0]
    update_loading_progress_dialog(
        loading_manager, 1, 5, "slice.dcm", started, last, ui_interval=0.0
    )
    assert started[0] is True
    loading_manager.on_cancel_loading.assert_called_once()


def _make_async_ctx(**overrides) -> _AsyncLoadContext:
    request = LoadPipelineRequest(
        loader_fn=lambda _cb: [],
        source_dir="/study",
        source_name="study",
        file_paths_for_merge=None,
        loader=MagicMock(),
        organizer=MagicMock(),
        loading_manager=MagicMock(),
        progress_max=10,
        main_window=MagicMock(),
        file_dialog=MagicMock(),
        load_first_slice_callback=MagicMock(),
        update_status_callback=MagicMock(),
    )
    ctx = _AsyncLoadContext(
        request=request,
        is_folder_mode=True,
        on_pipeline_complete=MagicMock(),
        loading_started=[False],
        last_ui_update=[0.0],
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def test_handle_finished_empty_shows_error() -> None:
    ctx = _make_async_ctx()
    ctx.request.loading_manager.is_cancelled.return_value = False
    ctx.request.loader.get_failed_files.return_value = []
    _handle_finished(ctx, [], [])
    ctx.request.file_dialog.show_error.assert_called_once()
    ctx.on_pipeline_complete.assert_called_once_with(None, None)


def test_handle_organized_success_updates_status() -> None:
    ctx = _make_async_ctx()
    ctx.request.loading_manager.is_cancelled.return_value = False
    ctx.request.loader.get_failed_files.return_value = []
    ctx.request.loader.get_extension_skipped_count.return_value = 0
    ctx.request.organizer.studies = {"s": {}}
    merge = MagicMock()
    merge.new_series = [("s", "ser")]
    merge.appended_series = []
    merge.added_file_count = 1
    merge.skipped_file_count = 0
    datasets = [SimpleNamespace(filename="/a.dcm")]

    with patch("core.loading_pipeline_async.QApplication.processEvents"), patch(
        "core.loading_pipeline_async.QTimer.singleShot"
    ), patch("core.loading_pipeline_async.perf_timer"):
        _handle_organized(ctx, datasets, merge)

    ctx.request.load_first_slice_callback.assert_called_once_with(merge)
    ctx.request.update_status_callback.assert_called_once()
    ctx.on_pipeline_complete.assert_called_once_with(datasets, {"s": {}})


def test_handle_error_redacts_details() -> None:
    ctx = _make_async_ctx()
    _handle_error(ctx, "SecretPath /phi/study.dcm")
    args = ctx.request.file_dialog.show_error.call_args[0]
    assert "SecretPath" not in args[2]
    assert "withheld" in args[2].lower()
    ctx.on_pipeline_complete.assert_called_once_with(None, None)


def test_run_load_pipeline_async_wires_worker_and_starts() -> None:
    request = LoadPipelineRequest(
        loader_fn=lambda _cb: [],
        source_dir="/study",
        source_name="study",
        file_paths_for_merge=["/a.dcm"],
        loader=MagicMock(),
        organizer=MagicMock(),
        loading_manager=MagicMock(),
        progress_max=3,
        main_window=MagicMock(),
        file_dialog=MagicMock(),
        load_first_slice_callback=MagicMock(),
        update_status_callback=MagicMock(),
    )
    dlg = MagicMock()
    request.loading_manager.create_progress_dialog.return_value = dlg

    fake_worker = MagicMock()
    with patch("core.loading_pipeline_async.QApplication.processEvents"), patch(
        "core.loading_pipeline_async.LoaderWorker", return_value=fake_worker
    ) as worker_cls, patch("core.loading_pipeline_async.perf_mark"):
        out = run_load_pipeline_async(request, on_pipeline_complete=MagicMock())

    assert out is fake_worker
    worker_cls.assert_called_once()
    fake_worker.start.assert_called_once()
    assert fake_worker.progress.connect.called
    assert fake_worker.finished.connect.called
    assert fake_worker.organized.connect.called
    assert fake_worker.error.connect.called


def test_run_load_pipeline_still_supports_partial_cancel() -> None:
    """Existing sync cancel contract remains after helper extraction."""
    datasets = [MagicMock(filename="/tmp/a.dcm")]  # NOSONAR - mock path only
    loader = MagicMock()
    loader.get_failed_files.return_value = []
    loader.get_extension_skipped_count.return_value = 0
    loader.get_attempted_file_count.return_value = 10
    loading_manager = MagicMock()
    loading_manager.is_cancelled.return_value = True
    merge_result = MagicMock()
    merge_result.new_series = [("1.2.3", "1.2.3.4")]
    merge_result.appended_series = []
    merge_result.skipped_file_count = 0
    merge_result.added_file_count = 1
    organizer = MagicMock()
    organizer.merge_batch.return_value = merge_result
    organizer.studies = {}
    on_load_success = MagicMock()
    with patch("core.loading_pipeline.QApplication.processEvents"), patch(
        "core.loading_pipeline.QTimer.singleShot"
    ):
        result = run_load_pipeline(
            LoadPipelineRequest(
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
                update_status_callback=MagicMock(),
                on_load_success=on_load_success,
            )
        )
    assert result[0] is datasets
    assert on_load_success.call_args.kwargs.get("was_cancelled") is True
