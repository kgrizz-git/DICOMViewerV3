"""Tests for the 3D render Secondary Capture writer."""

from __future__ import annotations

from typing import Any

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset
from pydicom.uid import SecondaryCaptureImageStorage

from core import volume_sc_dicom_export as sc

SRC_STUDY = "1.2.840.99.1"
SRC_SERIES = "1.2.840.99.2"
SRC_SOP = "1.2.840.99.3"


def _template() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "PID-12345"
    ds.PatientBirthDate = "19700101"
    ds.PatientSex = "F"
    ds.StudyInstanceUID = SRC_STUDY
    ds.SeriesInstanceUID = SRC_SERIES
    ds.SOPInstanceUID = SRC_SOP
    ds.StudyDate = "20200101"
    ds.StudyDescription = "Chest CT"
    ds.AccessionNumber = "ACC987"
    ds.Modality = "CT"
    ds.SeriesNumber = 4
    ds.SeriesDescription = "Chest"
    ds.Manufacturer = "ACME"
    ds.InstitutionName = "General Hospital"
    ds.ImagePositionPatient = [1.0, 2.0, 3.0]
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.PixelSpacing = [0.5, 0.5]
    ds.FrameOfReferenceUID = "1.2.840.99.4"
    ds.RescaleSlope = 1
    return ds


def _rgb(rows: int = 6, cols: int = 9) -> np.ndarray:
    rng = np.random.default_rng(1)
    return rng.integers(0, 256, (rows, cols, 3), dtype=np.uint8)


def _walk(ds: Dataset) -> Any:
    for elem in ds:
        yield elem
        if elem.VR == "SQ":
            for item in elem.value:
                yield from _walk(item)


def _all_text(ds: Dataset) -> str:
    parts = [str(e.value) for e in _walk(ds) if e.tag != 0x7FE00010]
    meta = getattr(ds, "file_meta", None)
    if meta is not None:
        parts += [str(e.value) for e in meta]
    return "\n".join(parts)


def test_round_trip_identified(tmp_path: Any) -> None:
    rgb = _rgb()
    path = str(tmp_path / "a.dcm")
    sc.write_volume_sc(
        rgb, _template(), path, preset_name="CT Bone", blend_mode="Composite",
        deidentify=False, source_refs=_REFS,
    )
    ds = pydicom.dcmread(path)
    assert ds.pixel_array.shape == (6, 9, 3)
    assert np.array_equal(ds.pixel_array, rgb)
    assert ds.SOPClassUID == SecondaryCaptureImageStorage
    assert ds.file_meta.MediaStorageSOPClassUID == SecondaryCaptureImageStorage
    assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
    assert ds.PhotometricInterpretation == "RGB"
    assert ds.SamplesPerPixel == 3
    assert ds.PlanarConfiguration == 0
    assert (ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation) == (8, 8, 7, 0)
    assert list(ds.ImageType) == ["DERIVED", "SECONDARY"]
    assert ds.ConversionType == "WSD"
    assert ds.Modality == "CT"
    assert ds.SeriesNumber == 704
    assert ds.InstanceNumber == 1
    assert ds.SeriesDescription == "Chest - 3D"
    assert ds.SOPInstanceUID != SRC_SOP
    assert ds.SeriesInstanceUID != SRC_SERIES
    assert ds.ReferencedSeriesSequence[0].SeriesInstanceUID == SRC_SERIES
    assert "CT Bone" in ds.DerivationDescription
    assert "Composite" in ds.DerivationDescription
    assert "Doe" not in ds.DerivationDescription
    # Identified output keeps patient, study, and equipment fields.
    assert ds.PatientName == "Doe^Jane"
    assert ds.PatientID == "PID-12345"
    assert ds.StudyInstanceUID == SRC_STUDY
    assert ds.Manufacturer == "ACME"
    assert ds.InstitutionName == "General Hospital"


def test_geometry_and_pixel_tags_not_copied() -> None:
    ds = sc.build_volume_sc_dataset(_rgb(), _template())
    for keyword in (
        "ImagePositionPatient", "ImageOrientationPatient", "PixelSpacing",
        "FrameOfReferenceUID", "RescaleSlope",
    ):
        assert keyword not in ds


def test_fallbacks_and_description_cap() -> None:
    bare = Dataset()
    ds = sc.build_volume_sc_dataset(_rgb(), bare)
    assert ds.Modality == "OT"
    assert ds.SeriesNumber == 701
    assert ds.SeriesDescription == "3D"
    assert "ReferencedSeriesSequence" not in ds
    long = _template()
    long.SeriesDescription = "x" * 100
    out = sc.build_volume_sc_dataset(_rgb(), long)
    assert len(out.SeriesDescription) == 64
    assert out.SeriesDescription.endswith(" - 3D")


def test_odd_size_pixel_data_padded_and_readable(tmp_path: Any) -> None:
    rgb = _rgb(3, 5)  # 45 bytes: odd length needs even padding
    path = str(tmp_path / "odd.dcm")
    sc.write_volume_sc(rgb, _template(), path, deidentify=False)
    assert np.array_equal(pydicom.dcmread(path).pixel_array, rgb)


def test_rejects_bad_array() -> None:
    flat = np.zeros((4, 4), dtype=np.uint8)
    template = _template()
    with pytest.raises(ValueError):
        sc.build_volume_sc_dataset(flat, template)


def test_deidentified_output_has_no_source_identity(tmp_path: Any) -> None:
    path = str(tmp_path / "d.dcm")
    sc.write_volume_sc(
        _rgb(), _template(), path, preset_name="CT Bone", blend_mode="Composite",
        deidentify=True, source_refs=_REFS,
    )
    ds = pydicom.dcmread(path)
    text = _all_text(ds)
    for secret in (
        "Doe", "PID-12345", "19700101", "ACC987", "General Hospital",
        SRC_STUDY, SRC_SERIES, SRC_SOP,
    ):
        assert secret not in text
    assert ds.file_meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
    assert ds.pixel_array.shape == (6, 9, 3)
    assert "CT Bone" in ds.DerivationDescription
    # The reference stays internally consistent (re-minted, not dropped).
    assert len(ds.ReferencedSeriesSequence) == 1


def test_deidentified_empty_template_round_trips(tmp_path: Any) -> None:
    rgb = np.zeros((2, 3, 3), dtype=np.uint8)
    rgb[0, 0] = (255, 0, 0)
    path = str(tmp_path / "empty.dcm")
    written = sc.write_volume_sc(rgb, Dataset(), path, deidentify=True)
    back = pydicom.dcmread(path)
    assert back.SOPClassUID == SecondaryCaptureImageStorage
    assert back.Modality == "OT"
    assert back.file_meta.MediaStorageSOPInstanceUID == back.SOPInstanceUID
    assert back.SOPInstanceUID == written.SOPInstanceUID
    assert np.array_equal(back.pixel_array, rgb)


_TYPE2 = (
    "PatientName", "PatientID", "PatientBirthDate", "PatientSex", "StudyDate",
    "StudyTime", "ReferringPhysicianName", "StudyID", "AccessionNumber",
    "Manufacturer", "PatientOrientation",
)
_REFS = [
    ("1.2.840.10008.5.1.4.1.1.2", "1.2.840.99.31"),
    ("1.2.840.10008.5.1.4.1.1.2", "1.2.840.99.32"),
]


@pytest.mark.parametrize("deidentify", [False, True])
@pytest.mark.parametrize("full", [True, False])
def test_type2_attributes_always_present(tmp_path: Any, deidentify: bool, full: bool) -> None:
    path = str(tmp_path / "t.dcm")
    sc.write_volume_sc(
        _rgb(), _template() if full else Dataset(), path, deidentify=deidentify
    )
    ds = pydicom.dcmread(path)
    for keyword in _TYPE2:
        assert keyword in ds, keyword
    assert ds.StudyInstanceUID
    assert ds.PatientOrientation in ("", None)


@pytest.mark.parametrize("deidentify", [False, True])
def test_referenced_instance_sequence(tmp_path: Any, deidentify: bool) -> None:
    path = str(tmp_path / "r.dcm")
    sc.write_volume_sc(
        _rgb(), _template(), path, deidentify=deidentify, source_refs=_REFS
    )
    ds = pydicom.dcmread(path)
    items = ds.ReferencedSeriesSequence[0].ReferencedInstanceSequence
    assert len(items) == 2
    got = [(str(i.ReferencedSOPClassUID), str(i.ReferencedSOPInstanceUID)) for i in items]
    if deidentify:
        assert [u for _c, u in got] != [u for _c, u in _REFS]
        assert len({u for _c, u in got}) == 2
    else:
        assert got == _REFS


def test_no_refs_means_no_referenced_series_sequence() -> None:
    ds = sc.build_volume_sc_dataset(_rgb(), _template(), source_refs=[])
    assert "ReferencedSeriesSequence" not in ds
    # The template has no SOPClassUID, so a derived ref is also impossible.
    assert "ReferencedSeriesSequence" not in sc.build_volume_sc_dataset(_rgb(), _template())


def test_template_derived_reference() -> None:
    t = _template()
    t.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds = sc.build_volume_sc_dataset(_rgb(), t)
    items = ds.ReferencedSeriesSequence[0].ReferencedInstanceSequence
    assert [str(i.ReferencedSOPInstanceUID) for i in items] == [SRC_SOP]


def test_refs_with_empty_class_are_skipped() -> None:
    refs = [("", "1.2.840.99.41"), ("1.2.840.10008.5.1.4.1.1.2", "1.2.840.99.42")]
    ds = sc.build_volume_sc_dataset(_rgb(), _template(), source_refs=refs)
    items = ds.ReferencedSeriesSequence[0].ReferencedInstanceSequence
    assert [str(i.ReferencedSOPInstanceUID) for i in items] == ["1.2.840.99.42"]
    only_bad = sc.build_volume_sc_dataset(_rgb(), _template(), source_refs=refs[:1])
    assert "ReferencedSeriesSequence" not in only_bad
