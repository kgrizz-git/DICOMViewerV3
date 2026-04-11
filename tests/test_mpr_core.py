"""
Focused unit tests for the new MPR core modules.

These tests use tiny synthetic DICOM-like datasets built entirely in memory.
They validate:
  - MprVolume pre-checks and volume construction
  - MprBuilder output on a simple axial volume
  - MprCache save/load round-tripping

Run with:
    python -m pytest tests/test_mpr_core.py -v
or:
    python tests/run_tests.py
"""

import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.mpr_builder import MprBuilder, MprResult
from core.mpr_cache import MprCache, make_result_key
from core.mpr_volume import MprVolume, MprVolumeError


def _make_pixel_dataset(
    array: np.ndarray,
    position: tuple,
    orientation: tuple = (1, 0, 0, 0, 1, 0),
    pixel_spacing: tuple = (1.0, 1.0),
    slice_thickness: float = 1.0,
    study_uid: str = "1.2.3.4",
    series_uid: str = "1.2.3.4.5",
    instance_number: int = 1,
) -> Dataset:
    """Create a minimal pixel-bearing Dataset that supports ``pixel_array``."""
    arr = np.asarray(array, dtype=np.uint16)

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    ds.Modality = "CT"
    ds.SeriesDescription = "Synthetic Test Series"

    ds.Rows = int(arr.shape[0])
    ds.Columns = int(arr.shape[1])
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15

    ds.ImagePositionPatient = list(position)
    ds.ImageOrientationPatient = list(orientation)
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    ds.InstanceNumber = instance_number
    ds.RescaleSlope = 1.0
    ds.RescaleIntercept = -1024.0

    ds.PixelData = arr.tobytes()
    return ds


def _make_axial_volume(n_slices: int = 3, rows: int = 4, cols: int = 5) -> list:
    """Return a small axial series with predictable values per slice."""
    datasets = []
    study_uid = generate_uid()
    series_uid = generate_uid()
    for i in range(n_slices):
        arr = np.full((rows, cols), i * 100, dtype=np.uint16)
        datasets.append(
            _make_pixel_dataset(
                array=arr,
                position=(0.0, 0.0, float(i)),
                slice_thickness=1.0,
                study_uid=study_uid,
                series_uid=series_uid,
                instance_number=i + 1,
            )
        )
    return datasets


class TestMprVolume(unittest.TestCase):
    """Unit tests for MprVolume."""

    def test_available_false_for_missing_geometry(self):
        ds1 = Dataset()
        ds2 = Dataset()
        self.assertFalse(MprVolume.available([ds1, ds2]))

    def test_available_true_for_valid_stack(self):
        datasets = _make_axial_volume()
        self.assertTrue(MprVolume.available(datasets))

    def test_from_datasets_builds_volume(self):
        datasets = _make_axial_volume(n_slices=4, rows=3, cols=6)
        volume = MprVolume.from_datasets(datasets)

        self.assertEqual(len(volume.source_datasets), 4)
        self.assertEqual(volume.rows, 3)
        self.assertEqual(volume.cols, 6)
        self.assertEqual(volume.sitk_image.GetSize(), (6, 3, 4))
        self.assertAlmostEqual(volume.slice_thickness_mm, 1.0, places=5)
        np.testing.assert_array_almost_equal(volume.normal, [0.0, 0.0, 1.0])

    def test_from_datasets_deduplicates_duplicate_positions(self):
        # Two datasets at the same position should be averaged into one slice
        # (not rejected), allowing single-slice MPRs to be built.
        ds1 = _make_pixel_dataset(np.ones((4, 4)) * 10.0, position=(0.0, 0.0, 0.0))
        ds2 = _make_pixel_dataset(np.ones((4, 4)) * 20.0, position=(0.0, 0.0, 0.0))
        volume = MprVolume.from_datasets([ds1, ds2])
        # Only one unique slice after dedup
        self.assertEqual(volume.sitk_image.GetSize()[2], 1)
        # Pixel values should be the mean (15.0), not just the first slice (10.0)
        import SimpleITK as sitk
        arr = sitk.GetArrayFromImage(volume.sitk_image)  # shape (z, y, x)
        np.testing.assert_allclose(arr[0], 15.0, rtol=1e-5)


class TestMprBuilderAndCache(unittest.TestCase):
    """Focused tests for MprBuilder output and MprCache round-trip."""

    def test_builder_produces_non_empty_result(self):
        volume = MprVolume.from_datasets(_make_axial_volume())
        plane = MprBuilder.standard_planes()["coronal"]
        worker = MprBuilder.create_worker(
            source_volume=volume,
            output_plane=plane,
            output_spacing_mm=1.0,
            output_thickness_mm=1.0,
            interpolation="linear",
        )

        result = worker._build()

        self.assertGreater(result.n_slices, 0)
        self.assertEqual(len(result.slices), result.n_slices)
        self.assertEqual(len(result.slice_stack.planes), result.n_slices)
        self.assertTrue(all(isinstance(arr, np.ndarray) for arr in result.slices))
        self.assertTrue(
            any(np.count_nonzero(arr) > 0 for arr in result.slices),
            "Coronal MPR from axial test data should contain non-zero voxels.",
        )

    def test_builder_sagittal_from_axial_has_signal(self):
        volume = MprVolume.from_datasets(_make_axial_volume())
        plane = MprBuilder.standard_planes()["sagittal"]
        worker = MprBuilder.create_worker(
            source_volume=volume,
            output_plane=plane,
            output_spacing_mm=1.0,
            output_thickness_mm=1.0,
            interpolation="linear",
        )

        result = worker._build()

        self.assertGreater(result.n_slices, 0)
        self.assertTrue(
            any(np.count_nonzero(arr) > 0 for arr in result.slices),
            "Sagittal MPR from axial test data should contain non-zero voxels.",
        )

    def test_cache_round_trip(self):
        volume = MprVolume.from_datasets(_make_axial_volume())
        plane = MprBuilder.standard_planes()["sagittal"]
        worker = MprBuilder.create_worker(
            source_volume=volume,
            output_plane=plane,
            output_spacing_mm=1.0,
            output_thickness_mm=1.0,
            interpolation="nearest",
        )
        result = worker._build()

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = MprCache(cache_dir=tmpdir, max_size_mb=50)
            self.assertTrue(cache.save(result))

            key = make_result_key(result)
            self.assertTrue(cache.has(key))

            loaded = cache.load(key)
            self.assertIsNotNone(loaded)
            slices, slice_stack, meta = loaded

            self.assertEqual(len(slices), result.n_slices)
            self.assertEqual(len(slice_stack.planes), result.n_slices)
            self.assertEqual(meta["interpolation"], "nearest")
            self.assertEqual(meta.get("rescale_slope"), result.rescale_slope)
            self.assertEqual(meta.get("rescale_intercept"), result.rescale_intercept)
            np.testing.assert_allclose(slices[0], result.slices[0])
            loaded_result = MprResult(
                slices=slices,
                slice_stack=slice_stack,
                output_spacing_mm=tuple(meta["output_spacing_mm"]),
                output_thickness_mm=float(meta["output_thickness_mm"]),
                source_volume=volume,
                interpolation=meta["interpolation"],
                rescale_slope=meta.get("rescale_slope"),
                rescale_intercept=meta.get("rescale_intercept"),
            )
            raw = np.array([[100.0, 200.0]], dtype=np.float32)
            np.testing.assert_allclose(
                loaded_result.apply_rescale(raw),
                result.apply_rescale(raw),
            )


if __name__ == "__main__":
    unittest.main()
