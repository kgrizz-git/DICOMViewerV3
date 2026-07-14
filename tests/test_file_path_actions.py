"""
Unit tests for core.file_path_actions (module-level file/path helpers extracted
from FileSeriesLoadingCoordinator). ``app`` is stubbed with SimpleNamespace/Mock
since these functions only touch a handful of attributes on it.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.file_path_actions import (
    get_current_slice_file_path,
    get_file_path_for_dataset,
    on_about_this_file_from_series,
    on_show_file_from_series,
    open_files,
    open_files_from_paths,
    open_folder,
    open_recent_file,
    update_about_this_file_dialog,
)


class FakeDataset:
    def __init__(self, filename=None, instance_number=None):
        if filename is not None:
            self.filename = filename
        if instance_number is not None:
            self.InstanceNumber = instance_number


def _make_app(file_paths=None):
    return SimpleNamespace(
        file_operations_handler=MagicMock(),
        dicom_organizer=SimpleNamespace(file_paths=file_paths or {}),
        dialog_coordinator=MagicMock(),
    )


# -- open helpers -------------------------------------------------------------

def test_open_files_delegates_to_handler():
    app = _make_app()
    open_files(app)
    app.file_operations_handler.open_files.assert_called_once_with()


def test_open_folder_delegates_to_handler():
    app = _make_app()
    open_folder(app)
    app.file_operations_handler.open_folder.assert_called_once_with()


def test_open_recent_file_delegates_with_path():
    app = _make_app()
    open_recent_file(app, "/tmp/study.dcm")
    app.file_operations_handler.open_recent_file.assert_called_once_with("/tmp/study.dcm")


def test_open_files_from_paths_delegates_with_list():
    app = _make_app()
    paths = ["/tmp/a.dcm", "/tmp/b.dcm"]
    open_files_from_paths(app, paths)
    app.file_operations_handler.open_paths.assert_called_once_with(paths)


# -- get_file_path_for_dataset -------------------------------------------------

def test_returns_none_for_missing_required_args():
    app = _make_app()
    assert get_file_path_for_dataset(app, None, "study", "series", 0) is None
    assert get_file_path_for_dataset(app, FakeDataset(), "", "series", 0) is None
    assert get_file_path_for_dataset(app, FakeDataset(), "study", "", 0) is None


def test_uses_dataset_filename_when_present():
    app = _make_app()
    ds = FakeDataset(filename="/abs/path/file.dcm")
    assert get_file_path_for_dataset(app, ds, "study", "series", 0) == "/abs/path/file.dcm"


def test_falls_back_to_instance_number_lookup():
    app = _make_app(file_paths={("study", "series", 3): "/data/inst3.dcm"})
    ds = FakeDataset(instance_number=3)
    assert get_file_path_for_dataset(app, ds, "study", "series", 0) == "/data/inst3.dcm"


def test_falls_back_to_slice_index_lookup_when_no_instance_number():
    app = _make_app(file_paths={("study", "series", 5): "/data/slice5.dcm"})
    ds = FakeDataset()
    assert get_file_path_for_dataset(app, ds, "study", "series", 5) == "/data/slice5.dcm"


def test_falls_back_to_scanning_matching_series_for_instance_number():
    app = _make_app(
        file_paths={("study", "series", 7): "/data/inst7.dcm"}
    )
    ds = FakeDataset(instance_number=7)
    # slice_index 0 doesn't match key directly, and (study, series, 0) isn't present,
    # so the scan over matching (study, series) keys should find instance_number 7.
    assert get_file_path_for_dataset(app, ds, "study", "series", 0) == "/data/inst7.dcm"


def test_returns_none_when_nothing_matches():
    app = _make_app(file_paths={("other_study", "other_series", 0): "/data/x.dcm"})
    ds = FakeDataset()
    assert get_file_path_for_dataset(app, ds, "study", "series", 0) is None


# -- series-context file actions -----------------------------------------------

def test_on_show_file_from_series_reveals_existing_file(monkeypatch, tmp_path):
    real_file = tmp_path / "slice0.dcm"
    real_file.write_bytes(b"\x00")
    ds = FakeDataset(filename=str(real_file))
    app = _make_app()
    app.current_studies = {"study": {"series": [ds]}}

    called = {}

    def fake_reveal(path):
        called["path"] = path
        return True

    monkeypatch.setattr("utils.file_explorer.reveal_file_in_explorer", fake_reveal)
    on_show_file_from_series(app, "study", "series")
    assert called["path"] == str(real_file)


def test_on_show_file_from_series_noop_when_study_missing():
    app = _make_app()
    app.current_studies = {}
    # Should not raise even though series/study are absent.
    on_show_file_from_series(app, "study", "series")


def test_on_show_file_from_series_noop_when_series_empty():
    app = _make_app()
    app.current_studies = {"study": {"series": []}}
    on_show_file_from_series(app, "study", "series")


def test_on_about_this_file_from_series_opens_dialog():
    ds = FakeDataset(filename="/data/first.dcm")
    app = _make_app()
    app.current_studies = {"study": {"series": [ds]}}

    on_about_this_file_from_series(app, "study", "series")

    app.dialog_coordinator.open_about_this_file.assert_called_once_with(ds, "/data/first.dcm")


def test_on_about_this_file_from_series_noop_when_study_missing():
    app = _make_app()
    app.current_studies = {}
    on_about_this_file_from_series(app, "study", "series")
    app.dialog_coordinator.open_about_this_file.assert_not_called()


# -- current-slice helpers -----------------------------------------------------

def test_get_current_slice_file_path_uses_focused_subwindow_when_index_none():
    ds = FakeDataset(filename="/data/current.dcm")
    app = _make_app()
    app.focused_subwindow_index = 2
    app._get_subwindow_dataset = MagicMock(return_value=ds)
    app._get_subwindow_study_uid = MagicMock(return_value="study")
    app._get_subwindow_series_uid = MagicMock(return_value="series")
    app._get_subwindow_slice_index = MagicMock(return_value=0)

    result = get_current_slice_file_path(app)

    app._get_subwindow_dataset.assert_called_once_with(2)
    assert result == "/data/current.dcm"


def test_get_current_slice_file_path_returns_none_without_dataset():
    app = _make_app()
    app._get_subwindow_dataset = MagicMock(return_value=None)
    app._get_subwindow_study_uid = MagicMock(return_value="study")
    app._get_subwindow_series_uid = MagicMock(return_value="series")
    app._get_subwindow_slice_index = MagicMock(return_value=0)

    assert get_current_slice_file_path(app, subwindow_idx=0) is None


def test_update_about_this_file_dialog_with_current_dataset():
    ds = FakeDataset(filename="/data/focused.dcm")
    app = _make_app()
    app.focused_subwindow_index = 1
    app.subwindow_data = {
        1: {
            "current_dataset": ds,
            "current_study_uid": "study",
            "current_series_uid": "series",
            "current_slice_index": 0,
        }
    }

    update_about_this_file_dialog(app)

    app.dialog_coordinator.update_about_this_file.assert_called_once_with(ds, "/data/focused.dcm")


def test_update_about_this_file_dialog_with_no_dataset():
    app = _make_app()
    app.focused_subwindow_index = 0
    app.subwindow_data = {}

    update_about_this_file_dialog(app)

    app.dialog_coordinator.update_about_this_file.assert_called_once_with(None, None)
