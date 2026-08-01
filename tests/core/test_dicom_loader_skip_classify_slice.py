"""Tests for DICOMLoader path-skip and pixel-data error classification helpers."""

from __future__ import annotations

from pathlib import Path

from pydicom.dataset import Dataset

from core.dicom_loader import (
    _classify_pixel_data_error,
    should_skip_path_for_dicom,
)


def test_should_skip_known_non_dicom_extensions(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("hi")
    assert should_skip_path_for_dicom(txt) is True


def test_should_not_skip_dcm_extension(tmp_path: Path) -> None:
    dcm = tmp_path / "slice.dcm"
    dcm.write_bytes(b"")
    assert should_skip_path_for_dicom(dcm) is False


def test_classify_sr_missing_pixel_data() -> None:
    ds = Dataset()
    ds.Modality = "SR"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.22"
    is_comp, msg = _classify_pixel_data_error(
        ds,
        "One of Pixel Data, Float Pixel Data or Double Float Pixel Data must be present",
    )
    assert is_comp is False
    assert "Structured Report" in msg


def test_classify_compression_decoder_error() -> None:
    ds = Dataset()
    ds.Modality = "CT"
    is_comp, msg = _classify_pixel_data_error(ds, "Unable to decode compressed transfer syntax")
    assert is_comp is True
    assert msg  # user-facing decode message
