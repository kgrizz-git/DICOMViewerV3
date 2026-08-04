"""Tests for AboutThisFileDialog update_file_info with synthetic datasets."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset, FileMetaDataset

from gui.dialogs.about_this_file_dialog import AboutThisFileDialog


def _synthetic_dataset() -> Dataset:
    ds = Dataset()
    ds.StudyDescription = "Synthetic Study"
    ds.StudyInstanceUID = "1.2.840.10008.10.20.0.1"
    ds.SeriesDescription = "Synthetic Series"
    ds.SeriesNumber = 4
    ds.SeriesInstanceUID = "1.2.840.10008.10.20.0.2"
    ds.Modality = "CT"
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.SamplesPerPixel = 1
    ds.Rows = 64
    ds.Columns = 64
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = "1.2.840.10008.1.2.1"
    ds.file_meta = meta
    return ds


@pytest.mark.qt
def test_update_clears_labels_when_dataset_none(qapp) -> None:
    dlg = AboutThisFileDialog()
    dlg.update_file_info(None, None)
    assert dlg.labels["modality"].text() == "—"
    assert dlg.labels["folder_path"].text() == "—"
    assert dlg.labels["filename"].text() == "—"


@pytest.mark.qt
def test_update_populates_path_and_tags(qapp, tmp_path) -> None:
    dlg = AboutThisFileDialog()
    path = tmp_path / "slice.dcm"
    path.write_bytes(b"")  # path only; dialog does not read file bytes
    ds = _synthetic_dataset()
    dlg.update_file_info(ds, str(path))
    assert dlg.labels["folder_path"].text() == str(tmp_path)
    assert dlg.labels["filename"].text() == "slice.dcm"
    assert dlg.labels["modality"].text() == "CT"
    assert dlg.labels["study_description"].text() == "Synthetic Study"
    assert dlg.labels["series_number"].text() == "4"
    assert dlg.labels["rows"].text() == "64"
    assert dlg.labels["columns"].text() == "64"
    assert dlg.labels["number_of_frames"].text() == "1"
    assert "Explicit VR Little Endian" in dlg.labels["transfer_syntax"].text()


@pytest.mark.qt
def test_number_of_frames_uses_tag_when_present(qapp) -> None:
    dlg = AboutThisFileDialog()
    ds = _synthetic_dataset()
    ds.NumberOfFrames = 12
    dlg.update_file_info(ds, None)
    assert dlg.labels["number_of_frames"].text() == "12"
