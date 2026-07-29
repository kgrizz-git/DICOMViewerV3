"""Unit tests for gui.dialogs.ct_batch_select_dialog."""

from __future__ import annotations

from unittest.mock import patch

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidget, QMessageBox

import gui.dialogs.ct_batch_select_dialog as ct_dialog_mod
from gui.dialogs.ct_batch_select_dialog import (
    build_ct_series_entries,
    prompt_batch_series_selection,
)


class MockOrganizer:
    def __init__(self, studies_dict: dict):
        self.studies = studies_dict

    def get_series_list(self) -> list[tuple[str, str]]:
        res = []
        for study_uid, series_map in self.studies.items():
            for series_key in series_map:
                res.append((study_uid, series_key))
        return res


class _AcceptAllDialog(QDialog):
    def exec(self):
        lw = self.findChild(QListWidget)
        if lw:
            for i in range(lw.count()):
                lw.item(i).setCheckState(Qt.CheckState.Checked)
        return int(QDialog.DialogCode.Accepted)


def test_build_ct_series_entries(qapp):
    ds_ct = Dataset()
    ds_ct.Modality = "CT"
    ds_ct.SeriesDescription = "Head CT"
    ds_ct.SeriesNumber = 2

    ds_mr = Dataset()
    ds_mr.Modality = "MR"
    ds_mr.SeriesDescription = "Brain MR"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_ct],
                "series_2": [ds_mr],
            }
        }
    )

    entries = build_ct_series_entries(organizer)
    assert len(entries) == 1
    assert entries[0] == ("study_1", "series_1", "Head CT #2")


def test_prompt_batch_series_selection_with_skipped_warning(qapp):
    ds_ct1 = Dataset()
    ds_ct1.Modality = "CT"
    ds_ct1.SeriesDescription = "Series 1"

    ds_ct2 = Dataset()
    ds_ct2.Modality = "CT"
    ds_ct2.SeriesDescription = "Series 2"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_ct1],
                "series_2": [ds_ct2],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        if series_key == "series_1":
            return f"/path/to/{series_key}_{slice_index}.dcm"
        return None  # series_2 has no resolvable path

    with patch.object(ct_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is not None
        requests, labels = res
        assert len(requests) == 1
        assert labels == ["Series 1"]
        assert requests[0].dicom_paths == ["/path/to/series_1_0.dcm"]

        mock_info.assert_not_called()
        mock_warning.assert_called_once()
        args, _ = mock_warning.call_args
        assert args[1] == "ACR CT Batch Analysis"
        assert "The following series had no resolvable files and were skipped:" in args[2]
        assert "Series 2" in args[2]


def test_prompt_batch_series_selection_all_skipped(qapp):
    ds_ct = Dataset()
    ds_ct.Modality = "CT"
    ds_ct.SeriesDescription = "Unresolvable Series"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_ct],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        return None

    with patch.object(ct_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is None
        mock_warning.assert_not_called()
        mock_info.assert_called_once()
        args, _ = mock_info.call_args
        assert args[1] == "ACR CT Batch Analysis"
        assert "No series were selected (or resolvable to files)." in args[2]


def test_prompt_batch_series_selection_all_valid(qapp):
    ds_ct = Dataset()
    ds_ct.Modality = "CT"
    ds_ct.SeriesDescription = "Valid Series"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_ct],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        return f"/path/to/{series_key}_{slice_index}.dcm"

    with patch.object(ct_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is not None
        requests, labels = res
        assert len(requests) == 1
        assert labels == ["Valid Series"]
        mock_warning.assert_not_called()
        mock_info.assert_not_called()
