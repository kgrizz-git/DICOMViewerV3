"""
Unit tests for ``core.mpr_dicom_export`` (synthetic MPR / template only, no PHI).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.uid import CTImageStorage, SecondaryCaptureImageStorage, generate_uid

from core.mpr_builder import MprResult
from core.mpr_volume import MprVolume
from core.mpr_dicom_export import (
    MprDicomExportError,
    MprDicomExportOptions,
    write_mpr_series,
)
from core.slice_geometry import SlicePlane, SliceStack


def _synthetic_ct_template() -> Dataset:
    """Minimal CT-like header for export metadata (no pixel data)."""
    ds = Dataset()
    ds.PatientName = "Synthetic^Test"
    ds.PatientID = "SYN001"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.StudyDate = "20200101"
    ds.StudyDescription = "SyntheticStudy"
    ds.SeriesDescription = "AxialSource"
    ds.SeriesNumber = 1
    ds.Modality = "CT"
    ds.FrameOfReferenceUID = generate_uid()
    ds.SOPClassUID = CTImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.Rows = 4
    ds.Columns = 4
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.PixelRepresentation = 1
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    ds.ImagePositionPatient = [0, 0, 0]
    ds.PixelSpacing = [0.7, 0.7]
    ds.SliceThickness = 1.0
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = 0.0
    return ds


def _synthetic_mpr_result(template: Dataset) -> MprResult:
    planes: list[SlicePlane] = []
    for i in range(3):
        origin = np.array([0.0, 0.0, float(i) * 2.0], dtype=float)
        row = np.array([1.0, 0.0, 0.0], dtype=float)
        col = np.array([0.0, 1.0, 0.0], dtype=float)
        planes.append(SlicePlane(origin, row, col, 0.5, 0.5))
    positions = [float(np.dot(p.origin, np.array([0.0, 0.0, 1.0]))) for p in planes]
    stack = SliceStack(
        planes=planes,
        original_indices=list(range(3)),
        stack_normal=np.array([0.0, 0.0, 1.0], dtype=float),
        positions=positions,
        slice_thickness=2.0,
    )
    slices = [
        (np.ones((4, 4), dtype=np.float32) * (100.0 + 50.0 * i)) for i in range(3)
    ]
    vol = cast(MprVolume, cast(object, SimpleNamespace(source_datasets=[template])))
    return MprResult(
        slices=slices,
        slice_stack=stack,
        output_spacing_mm=(0.5, 0.5),
        output_thickness_mm=2.0,
        source_volume=vol,
        interpolation="linear",
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )


def test_write_mpr_series_round_trip_ct(tmp_path) -> None:
    template = _synthetic_ct_template()
    mpr = _synthetic_mpr_result(template)
    opts = MprDicomExportOptions(
        orientation_label="Axial",
        series_description_suffix="test",
        anonymize=False,
        use_rescaled_pixel_values=True,
    )
    paths = write_mpr_series(tmp_path, mpr, template, opts)
    assert len(paths) == 3
    series_uids: set[str] = set()
    for i, p in enumerate(paths):
        ds = pydicom.dcmread(str(p), force=True)
        assert ds.InstanceNumber == i + 1
        series_uids.add(str(ds.SeriesInstanceUID))
        assert ds.SOPInstanceUID != template.SOPInstanceUID
        assert list(ds.ImagePositionPatient) == list(
            mpr.slice_stack.planes[i].origin.ravel()[:3]
        )
        assert ds.Rows == 4 and ds.Columns == 4
        assert ds.PixelData is not None
        assert ds["PixelData"].VR == "OW"
        arr = ds.pixel_array
        assert arr.shape == (4, 4)
        assert hasattr(ds, "RescaleSlope") and hasattr(ds, "RescaleIntercept")
        assert ds.RescaleType == "HU"
    assert len(series_uids) == 1
    assert paths[0].parent == paths[1].parent == paths[2].parent


def test_write_mpr_series_raw_ct_omits_rescale_type(tmp_path) -> None:
    template = _synthetic_ct_template()
    mpr = _synthetic_mpr_result(template)
    paths = write_mpr_series(
        tmp_path,
        mpr,
        template,
        MprDicomExportOptions(
            orientation_label="Axial",
            use_rescaled_pixel_values=False,
        ),
    )
    ds0 = pydicom.dcmread(str(paths[0]), force=True)
    assert "RescaleType" not in ds0


def test_write_mpr_series_empty_raises(tmp_path) -> None:
    template = _synthetic_ct_template()
    mpr = _synthetic_mpr_result(template)
    mpr_empty = MprResult(
        slices=[],
        slice_stack=mpr.slice_stack,
        output_spacing_mm=mpr.output_spacing_mm,
        output_thickness_mm=mpr.output_thickness_mm,
        source_volume=mpr.source_volume,
        interpolation="linear",
    )
    try:
        write_mpr_series(tmp_path, mpr_empty, template, None)
    except MprDicomExportError as e:
        assert "no slices" in str(e).lower()
    else:
        raise AssertionError("expected MprDicomExportError")


def test_write_mpr_series_secondary_capture_nm(tmp_path) -> None:
    template = _synthetic_ct_template()
    template.Modality = "NM"
    mpr = _synthetic_mpr_result(template)
    paths = write_mpr_series(
        tmp_path,
        mpr,
        template,
        MprDicomExportOptions(orientation_label="Oblique"),
    )
    ds0 = pydicom.dcmread(str(paths[0]), force=True)
    assert str(ds0.SOPClassUID) == str(SecondaryCaptureImageStorage)
    assert ds0.Modality == "OT"
    assert "RescaleType" not in ds0


def test_write_mpr_series_cancel_mid_run(tmp_path) -> None:
    template = _synthetic_ct_template()
    mpr = _synthetic_mpr_result(template)
    calls = {"n": 0}

    def cb(cur: int, total: int, msg: str) -> bool:
        calls["n"] += 1
        return cur < 2

    try:
        write_mpr_series(tmp_path, mpr, template, None, progress_callback=cb)
    except MprDicomExportError as e:
        assert "cancelled" in str(e).lower()
    else:
        raise AssertionError("expected cancel")
