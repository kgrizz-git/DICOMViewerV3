"""
Unit tests for src/core/slice_location_line_helper.py

Tests segment computation for the slice location line feature using
mock app state and synthetic geometry.

Run with:
    python -m pytest tests/test_slice_location_line_helper.py -v
"""

import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset

from core.slice_geometry import SlicePlane
from core.slice_location_line_helper import get_slice_location_line_segments


def _make_dataset(
    ipp: tuple,
    iop: tuple = (1, 0, 0, 0, 1, 0),
    pixel_spacing: tuple = (1.0, 1.0),
    rows: int = 256,
    columns: int = 256,
) -> Dataset:
    """Minimal DICOM dataset with spatial metadata."""
    ds = Dataset()
    ds.ImagePositionPatient = list(ipp)
    ds.ImageOrientationPatient = list(iop)
    ds.PixelSpacing = list(pixel_spacing)
    ds.Rows = rows
    ds.Columns = columns
    return ds


def _axial_stack(n: int = 5, z_start: float = 0.0, z_step: float = 5.0) -> list:
    """Axial stack along Z."""
    iop = (1, 0, 0, 0, 1, 0)
    return [_make_dataset((0.0, 0.0, z_start + i * z_step), iop=iop) for i in range(n)]


def _coronal_stack(n: int = 5, y_start: float = 0.0, y_step: float = 5.0) -> list:
    """Coronal stack along Y."""
    iop = (1, 0, 0, 0, 0, -1)
    return [_make_dataset((0.0, y_start + i * y_step, 0.0), iop=iop) for i in range(n)]


class MockApp:
    """Mock app with subwindow_data and slice sync coordinator."""

    def __init__(self):
        self.subwindow_data = {}
        self._slice_sync_coordinator = None

    def set_subwindow(self, idx: int, datasets: list, slice_idx: int = 0, is_mpr: bool = False):
        """Set subwindow data for testing."""
        study_uid = "1.2.3"
        series_uid = f"4.5.{idx}"
        self.subwindow_data[idx] = {
            "current_datasets": datasets,
            "current_dataset": datasets[slice_idx] if datasets else None,
            "current_slice_index": slice_idx,
            "current_study_uid": study_uid,
            "current_series_uid": series_uid,
            "is_mpr": is_mpr,
        }


class MockSliceSyncCoordinator:
    """Mock coordinator that provides get_current_plane."""

    def __init__(self, app: MockApp):
        self.app = app
        self._cache = {}

    def get_current_plane(self, idx: int):
        """Return current SlicePlane for subwindow idx."""
        data = self.app.subwindow_data.get(idx, {})
        datasets = data.get("current_datasets")
        slice_idx = data.get("current_slice_index", 0)
        if not datasets or slice_idx < 0 or slice_idx >= len(datasets):
            return None
        ds = datasets[slice_idx]
        return SlicePlane.from_dataset(ds)


class TestSliceLocationLineHelper(unittest.TestCase):
    """Tests for get_slice_location_line_segments."""

    def setUp(self):
        """Set up mock app with axial and coronal stacks."""
        self.app = MockApp()
        axial = _axial_stack(5, z_start=0.0, z_step=5.0)
        coronal = _coronal_stack(5, y_start=0.0, y_step=5.0)
        self.app.set_subwindow(0, axial, 2)
        self.app.set_subwindow(1, coronal, 2)
        coord = MockSliceSyncCoordinator(self.app)
        self.app._slice_sync_coordinator = coord

    def test_orthogonal_planes_produce_segment(self):
        """Axial and coronal planes should intersect and produce a line."""
        segments = get_slice_location_line_segments(0, self.app, only_same_group=False)
        self.assertIsInstance(segments, list)
        self.assertGreaterEqual(len(segments), 1)
        for seg in segments:
            self.assertIn("source_idx", seg)
            self.assertIn("col1", seg)
            self.assertIn("row1", seg)
            self.assertIn("col2", seg)
            self.assertIn("row2", seg)

    def test_target_with_no_other_views_returns_empty(self):
        """Target with no other subwindows has data returns empty."""
        self.app.subwindow_data = {0: self.app.subwindow_data[0]}
        segments = get_slice_location_line_segments(0, self.app)
        self.assertEqual(len(segments), 0)

    def test_missing_coordinator_returns_empty(self):
        """Missing coordinator returns empty."""
        self.app._slice_sync_coordinator = None
        segments = get_slice_location_line_segments(0, self.app)
        self.assertEqual(len(segments), 0)

    def test_target_without_geometry_returns_empty(self):
        """Target with no valid geometry returns empty."""
        self.app.subwindow_data[0]["current_datasets"] = []
        self.app.subwindow_data[0]["current_dataset"] = None
        segments = get_slice_location_line_segments(0, self.app)
        self.assertEqual(len(segments), 0)


if __name__ == "__main__":
    unittest.main()
