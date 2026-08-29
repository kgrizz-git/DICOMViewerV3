"""Unit tests for gui.dialogs.acr_mri_series_selection_dialog."""

from __future__ import annotations

from unittest.mock import patch

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QListWidget, QMessageBox, QPushButton

import gui.dialogs.acr_mri_series_selection_dialog as mri_dialog_mod
from gui.dialogs.acr_mri_series_selection_dialog import (
    build_mri_series_entries,
    prompt_mri_batch_series_selection,
    stamp_mri_batch_options,
)
from qa.analysis_types import QARequest


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


def test_build_mri_series_entries_excludes_ct(qapp):
    ds_ct = Dataset()
    ds_ct.Modality = "CT"
    ds_ct.SeriesDescription = "Head CT"
    ds_ct.SeriesNumber = 2

    ds_mr = Dataset()
    ds_mr.Modality = "MR"
    ds_mr.SeriesDescription = "Brain MR"
    ds_mr.SeriesNumber = 3

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_ct],
                "series_2": [ds_mr],
            }
        }
    )

    entries = build_mri_series_entries(organizer)
    assert len(entries) == 1
    assert entries[0] == ("study_1", "series_2", "Brain MR #3")


def test_prompt_mri_batch_series_selection_with_skipped_warning(qapp):
    ds_mr1 = Dataset()
    ds_mr1.Modality = "MR"
    ds_mr1.SeriesDescription = "Series 1"

    ds_mr2 = Dataset()
    ds_mr2.Modality = "MR"
    ds_mr2.SeriesDescription = "Series 2"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_mr1],
                "series_2": [ds_mr2],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        if series_key == "series_1":
            return f"/path/to/{series_key}_{slice_index}.dcm"
        return None  # series_2 has no resolvable path

    with patch.object(mri_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_mri_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is not None
        requests, labels = res
        assert len(requests) == 1
        assert labels == ["Series 1"]
        assert requests[0].dicom_paths == ["/path/to/series_1_0.dcm"]
        assert requests[0].analysis_type == "acr_mri_large"
        assert requests[0].modality == "MR"

        mock_info.assert_not_called()
        mock_warning.assert_called_once()
        args, _ = mock_warning.call_args
        assert args[1] == "ACR MRI Batch Analysis"
        assert "The following series had no resolvable files and were skipped:" in args[2]
        assert "Series 2" in args[2]


def test_prompt_mri_batch_series_selection_all_skipped(qapp):
    ds_mr = Dataset()
    ds_mr.Modality = "MR"
    ds_mr.SeriesDescription = "Unresolvable Series"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_mr],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        return None

    with patch.object(mri_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_mri_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is None
        mock_warning.assert_not_called()
        mock_info.assert_called_once()
        args, _ = mock_info.call_args
        assert args[1] == "ACR MRI Batch Analysis"
        assert "No series were selected (or resolvable to files)." in args[2]


def test_prompt_mri_batch_series_selection_all_valid(qapp):
    ds_mr = Dataset()
    ds_mr.Modality = "MR"
    ds_mr.SeriesDescription = "Valid Series"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_mr],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        return f"/path/to/{series_key}_{slice_index}.dcm"

    with patch.object(mri_dialog_mod, "QDialog", _AcceptAllDialog), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_mri_batch_series_selection(
            None,
            organizer,
            get_file_path,
        )

        assert res is not None
        requests, labels = res
        assert len(requests) == 1
        assert labels == ["Valid Series"]
        assert requests[0].analysis_type == "acr_mri_large"
        assert requests[0].modality == "MR"
        mock_warning.assert_not_called()
        mock_info.assert_not_called()


def test_prompt_mri_batch_series_selection_add_folder(qapp):
    """Add folder button adds a checked folder row that becomes a folder request."""
    ds_mr = Dataset()
    ds_mr.Modality = "MR"
    ds_mr.SeriesDescription = "Loaded MR"

    organizer = MockOrganizer(
        {
            "study_1": {
                "series_1": [ds_mr],
            }
        }
    )

    def get_file_path(ds, study_uid, series_key, slice_index):
        return f"/path/to/{series_key}_{slice_index}.dcm"

    picked_folders: list[str] = []

    def fake_open_folder():
        picked_folders.append("/data/mr_folder")
        return "/data/mr_folder"

    # Subclass to wire the Add folder button click before exec.
    class _DialogWithFolder(_AcceptAllDialog):
        def exec(self):
            # Find the Add folder button and click it.
            for btn in self.findChildren(QPushButton):
                if "Add folder" in btn.text():
                    btn.click()
                    break
            return super().exec()

    with patch.object(mri_dialog_mod, "QDialog", _DialogWithFolder), \
         patch.object(QMessageBox, "warning") as mock_warning, \
         patch.object(QMessageBox, "information") as mock_info:

        res = prompt_mri_batch_series_selection(
            None,
            organizer,
            get_file_path,
            open_folder=fake_open_folder,
        )

        assert res is not None
        requests, labels = res
        assert len(requests) == 2
        # Series row first, folder row second.
        assert requests[0].analysis_type == "acr_mri_large"
        assert requests[0].modality == "MR"
        assert requests[0].dicom_paths == ["/path/to/series_1_0.dcm"]
        assert requests[1].folder_path == "/data/mr_folder"
        assert requests[1].analysis_type == "acr_mri_large"
        assert requests[1].modality == "MR"
        assert labels[1] == "[Folder] mr_folder"
        mock_warning.assert_not_called()
        mock_info.assert_not_called()


def test_stamp_mri_batch_options_stamps_fields():
    """Helper stamps shared MRI options; does not attach compare configs."""
    requests = [
        QARequest(analysis_type="acr_mri_large", modality="MR", dicom_paths=["/a.dcm"]),
        QARequest(analysis_type="acr_mri_large", modality="MR", folder_path="/f"),
    ]

    stamped = stamp_mri_batch_options(
        requests,
        echo_number=2,
        check_uid=False,
        origin_slice=5,
        scan_extent_tolerance_mm=3.0,
        vanilla_pylinac=True,
        embed_module_images_in_xlsx=False,
        low_contrast_method="rose",
        low_contrast_visibility_threshold=0.05,
        low_contrast_visibility_sanity_multiplier=1.2,
    )

    assert len(stamped) == 2
    for req in stamped:
        assert req.echo_number == 2
        assert req.check_uid is False
        assert req.origin_slice == 5
        assert req.scan_extent_tolerance_mm == 3.0
        assert req.vanilla_pylinac is True
        assert req.embed_module_images_in_xlsx is False
        assert req.low_contrast_method == "rose"
        assert req.low_contrast_visibility_threshold == 0.05
        assert req.low_contrast_visibility_sanity_multiplier == 1.2
        assert req.analysis_type == "acr_mri_large"
        assert req.modality == "MR"
        # No compare-mode field attached.
        assert not hasattr(req, "compare_request")

    # Original list is not mutated.
    assert requests[0].echo_number is None
    assert requests[0].vanilla_pylinac is False
