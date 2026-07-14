"""Tests for 3D-only calibrated volume data preparation."""

from __future__ import annotations

import os
import sys

import numpy as np
import SimpleITK as sitk
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.mpr_builder import MprBuilder
from core.mpr_volume import MprVolume
from core.volume_renderer import VolumeRenderer


def _make_ct_dataset(
    array: np.ndarray,
    *,
    z: float,
    slope: float | None = 1.0,
    intercept: float | None = -1024.0,
    instance_number: int = 1,
    study_uid: str,
    series_uid: str,
) -> Dataset:
    """Create a minimal CT slice with optional rescale metadata."""
    arr = np.asarray(array, dtype=np.uint16)
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.Modality = "CT"
    ds.Rows = int(arr.shape[0])
    ds.Columns = int(arr.shape[1])
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    ds.ImagePositionPatient = [0.0, 0.0, z]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.PixelSpacing = [1.0, 1.0]
    ds.SliceThickness = 1.0
    ds.InstanceNumber = instance_number
    if slope is not None:
        ds.RescaleSlope = slope
    if intercept is not None:
        ds.RescaleIntercept = intercept
    ds.RescaleType = "HU"
    ds.PixelData = arr.tobytes()
    return ds


def _make_ct_series(
    *,
    slope: float | None = 1.0,
    intercept: float | None = -1024.0,
) -> list[Dataset]:
    study_uid = generate_uid()
    series_uid = generate_uid()
    return [
        _make_ct_dataset(
            np.full((2, 2), 1024 + i * 100, dtype=np.uint16),
            z=float(i),
            slope=slope,
            intercept=intercept,
            instance_number=i + 1,
            study_uid=study_uid,
            series_uid=series_uid,
        )
        for i in range(3)
    ]


def test_prepare_volume_data_can_calibrate_ct_without_mutating_mpr_volume() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=-1024.0)
    volume = MprVolume.from_datasets(datasets)

    raw = sitk.GetArrayFromImage(volume.sitk_image)
    assert raw[0, 0, 0] == 1024.0

    volume_data = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )

    np.testing.assert_allclose(volume_data.array[:, 0, 0], [0.0, 100.0, 200.0])
    assert volume_data.rescale_applied is True
    assert volume_data.scalar_units == "HU"


def test_prepare_volume_data_falls_back_to_raw_when_rescale_metadata_incomplete() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=None)
    volume = MprVolume.from_datasets(datasets)

    volume_data = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )

    np.testing.assert_allclose(volume_data.array[:, 0, 0], [1024.0, 1124.0, 1224.0])
    assert volume_data.rescale_applied is False
    assert volume_data.scalar_units is None


def test_varying_slope_intercept_per_slice() -> None:
    """Per-slice calibration must apply each slice's own slope/intercept."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=0.0, slope=1.0, intercept=-1024.0,
            instance_number=1, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=1.0, slope=1.0, intercept=-1000.0,
            instance_number=2, study_uid=study_uid, series_uid=series_uid,
        ),
        _make_ct_dataset(
            np.full((2, 2), 1000, dtype=np.uint16),
            z=2.0, slope=2.0, intercept=-500.0,
            instance_number=3, study_uid=study_uid, series_uid=series_uid,
        ),
    ]
    volume = MprVolume.from_datasets(datasets)
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is True
    # slice 0: 1000 * 1.0 + (-1024) = -24
    # slice 1: 1000 * 1.0 + (-1000) = 0
    # slice 2: 1000 * 2.0 + (-500)  = 1500
    np.testing.assert_allclose(vd.array[:, 0, 0], [-24.0, 0.0, 1500.0])


def test_mixed_rescale_units_falls_back_to_raw() -> None:
    """If slices report different rescale-unit strings, fall back to raw."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    ds1 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=0.0, slope=1.0, intercept=0.0,
        instance_number=1, study_uid=study_uid, series_uid=series_uid,
    )
    ds1.RescaleType = "HU"
    ds2 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=1.0, slope=1.0, intercept=0.0,
        instance_number=2, study_uid=study_uid, series_uid=series_uid,
    )
    ds2.RescaleType = "OD"  # optical density — genuinely different from HU
    ds3 = _make_ct_dataset(
        np.full((2, 2), 100, dtype=np.uint16),
        z=2.0, slope=1.0, intercept=0.0,
        instance_number=3, study_uid=study_uid, series_uid=series_uid,
    )
    ds3.RescaleType = "HU"
    volume = MprVolume.from_datasets([ds1, ds2, ds3])
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None


def test_nan_in_calibrated_output_falls_back_to_raw() -> None:
    """If calibration produces NaN/Inf, fall back to raw."""
    study_uid = generate_uid()
    series_uid = generate_uid()
    # slope=1e38 * large pixel value can overflow float32 to inf
    datasets = [
        _make_ct_dataset(
            np.full((2, 2), 65535, dtype=np.uint16),
            z=float(i), slope=1e35, intercept=0.0,
            instance_number=i + 1, study_uid=study_uid, series_uid=series_uid,
        )
        for i in range(3)
    ]
    volume = MprVolume.from_datasets(datasets)
    vd = VolumeRenderer.prepare_volume_data(
        volume.sitk_image,
        source_datasets=volume.source_datasets,
        apply_rescale=True,
    )
    assert vd.rescale_applied is False
    assert vd.scalar_units is None


def test_mpr_volume_remains_raw_and_mpr_rescale_still_applies_once() -> None:
    datasets = _make_ct_series(slope=1.0, intercept=-1024.0)
    volume = MprVolume.from_datasets(datasets)

    raw = sitk.GetArrayFromImage(volume.sitk_image)
    assert raw[0, 0, 0] == 1024.0

    worker = MprBuilder.create_worker(
        source_volume=volume,
        output_plane=MprBuilder.standard_planes()["axial"],
        output_spacing_mm=1.0,
        output_thickness_mm=1.0,
        interpolation="nearest",
    )
    result = worker._build()

    np.testing.assert_allclose(result.apply_rescale(np.array([[1024.0]], dtype=np.float32)), [[0.0]])
