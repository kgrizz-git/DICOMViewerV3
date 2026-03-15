"""
Unit tests for src/core/slice_geometry.py

Tests all public types and functions using synthetic DICOM-like data (no real
DICOM files required).  Covers:
  - SlicePlane construction (from_dataset and direct)
  - SliceStack construction (from_datasets, sort order, thickness)
  - find_nearest_slice: basic, tolerance, near-perpendicular, missing metadata
  - plane_plane_intersection: axial+coronal, parallel planes, near-parallel
  - project_line_to_2d: basic, missing spacing, line-parallel-to-normal

Run with:
    python -m pytest tests/test_slice_geometry.py -v
  or:
    python tests/run_tests.py
"""

import math
import sys
import os
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pydicom
from pydicom.dataset import Dataset

from core.slice_geometry import (
    SlicePlane,
    SliceStack,
    clip_line_to_rect,
    find_nearest_slice,
    plane_plane_intersection,
    project_line_to_2d,
)


# ---------------------------------------------------------------------------
# Helpers for building minimal synthetic datasets
# ---------------------------------------------------------------------------

def _make_dataset(
    ipp: tuple,
    iop: tuple = (1, 0, 0, 0, 1, 0),
    pixel_spacing: tuple = (1.0, 1.0),
    slice_thickness: float = 5.0,
) -> Dataset:
    """
    Return a minimal pydicom Dataset with spatial metadata set.

    Args:
        ipp            : (x, y, z) for ImagePositionPatient.
        iop            : 6-tuple for ImageOrientationPatient.
        pixel_spacing  : (row_spacing, col_spacing).
        slice_thickness: SliceThickness tag value.
    """
    ds = Dataset()
    ds.ImagePositionPatient = list(ipp)
    ds.ImageOrientationPatient = list(iop)
    ds.PixelSpacing = list(pixel_spacing)
    ds.SliceThickness = slice_thickness
    return ds


def _axial_stack(n: int = 10, z_start: float = 0.0, z_step: float = 5.0) -> list:
    """Return n axial datasets stacked along Z (IOP = standard axial)."""
    # Axial: row direction = +X, col direction = +Y  → normal = +Z
    iop = (1, 0, 0, 0, 1, 0)
    return [_make_dataset((0.0, 0.0, z_start + i * z_step), iop=iop) for i in range(n)]


def _coronal_stack(n: int = 10, y_start: float = 0.0, y_step: float = 5.0) -> list:
    """Return n coronal datasets stacked along Y (IOP = standard coronal)."""
    # Coronal: row direction = +X, col direction = +Z  → normal = -Y  (col×row cross)
    # ImageOrientationPatient: [row_x, row_y, row_z, col_x, col_y, col_z]
    # row = (1, 0, 0), col = (0, 0, -1)  → normal = row × col = (0, -(-1)*0, ...) = (0, 1, 0)
    # Choosing col = (0, 0, -1) gives normal pointing in +Y direction
    iop = (1, 0, 0, 0, 0, -1)
    return [_make_dataset((0.0, y_start + i * y_step, 0.0), iop=iop) for i in range(n)]


def _sagittal_stack(n: int = 10, x_start: float = 0.0, x_step: float = 5.0) -> list:
    """Return n sagittal datasets stacked along X (IOP = standard sagittal)."""
    # row = (0, 1, 0), col = (0, 0, -1)  → normal = (0,1,0) × (0,0,-1) = (-1, 0, 0)
    iop = (0, 1, 0, 0, 0, -1)
    return [_make_dataset((x_start + i * x_step, 0.0, 0.0), iop=iop) for i in range(n)]


# ---------------------------------------------------------------------------
# SlicePlane tests
# ---------------------------------------------------------------------------

class TestSlicePlane(unittest.TestCase):
    """Tests for SlicePlane construction and properties."""

    def test_from_dataset_standard_axial(self):
        ds = _make_dataset((10.0, 20.0, 30.0))
        plane = SlicePlane.from_dataset(ds)
        self.assertIsNotNone(plane)
        np.testing.assert_array_almost_equal(plane.origin, [10.0, 20.0, 30.0])
        np.testing.assert_array_almost_equal(plane.row_cosine, [1, 0, 0])
        np.testing.assert_array_almost_equal(plane.col_cosine, [0, 1, 0])
        self.assertAlmostEqual(plane.row_spacing, 1.0)
        self.assertAlmostEqual(plane.col_spacing, 1.0)

    def test_normal_axial_points_along_z(self):
        ds = _make_dataset((0, 0, 0))
        plane = SlicePlane.from_dataset(ds)
        # row=(1,0,0), col=(0,1,0)  →  normal = (1,0,0)×(0,1,0) = (0,0,1)
        np.testing.assert_array_almost_equal(plane.normal, [0, 0, 1])

    def test_normal_coronal(self):
        ds = _make_dataset((0, 0, 0), iop=(1, 0, 0, 0, 0, -1))
        plane = SlicePlane.from_dataset(ds)
        # row=(1,0,0), col=(0,0,-1)  → normal = (1,0,0)×(0,0,-1) = (0*-1-0*0, 0*0-1*-1, 1*0-0*0) = (0,1,0)
        np.testing.assert_array_almost_equal(plane.normal, [0, 1, 0])

    def test_from_dataset_missing_ipp_returns_none(self):
        ds = Dataset()
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        self.assertIsNone(SlicePlane.from_dataset(ds))

    def test_from_dataset_missing_iop_returns_none(self):
        ds = Dataset()
        ds.ImagePositionPatient = [0, 0, 0]
        self.assertIsNone(SlicePlane.from_dataset(ds))

    def test_from_dataset_degenerate_iop_returns_none(self):
        # Zero direction cosines → invalid
        ds = _make_dataset((0, 0, 0), iop=(0, 0, 0, 0, 0, 0))
        self.assertIsNone(SlicePlane.from_dataset(ds))

    def test_from_dataset_no_pixel_spacing_still_works(self):
        ds = Dataset()
        ds.ImagePositionPatient = [0, 0, 0]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        plane = SlicePlane.from_dataset(ds)
        self.assertIsNotNone(plane)
        self.assertIsNone(plane.row_spacing)
        self.assertIsNone(plane.col_spacing)

    def test_normal_is_unit_vector(self):
        ds = _make_dataset((0, 0, 0), iop=(1, 0, 0, 0, 1, 0))
        plane = SlicePlane.from_dataset(ds)
        self.assertAlmostEqual(float(np.linalg.norm(plane.normal)), 1.0, places=10)


# ---------------------------------------------------------------------------
# SliceStack tests
# ---------------------------------------------------------------------------

class TestSliceStack(unittest.TestCase):
    """Tests for SliceStack.from_datasets and basic properties."""

    def test_from_datasets_basic_axial(self):
        datasets = _axial_stack(5, z_start=0.0, z_step=5.0)
        stack = SliceStack.from_datasets(datasets)
        self.assertIsNotNone(stack)
        self.assertEqual(len(stack.planes), 5)
        self.assertEqual(len(stack.original_indices), 5)
        self.assertEqual(len(stack.positions), 5)

    def test_positions_sorted_ascending(self):
        datasets = _axial_stack(5, z_start=10.0, z_step=5.0)
        stack = SliceStack.from_datasets(datasets)
        self.assertEqual(stack.positions, sorted(stack.positions))

    def test_original_indices_map_correctly(self):
        # Feed stack in reversed order to verify original_indices round-trips.
        datasets = list(reversed(_axial_stack(5, z_start=0.0, z_step=5.0)))
        stack = SliceStack.from_datasets(datasets)
        # Positions should be ascending regardless of input order.
        self.assertEqual(stack.positions, sorted(stack.positions))
        # Every original index must be present.
        self.assertEqual(sorted(stack.original_indices), list(range(5)))

    def test_stack_normal_axial(self):
        datasets = _axial_stack(5)
        stack = SliceStack.from_datasets(datasets)
        np.testing.assert_array_almost_equal(stack.stack_normal, [0, 0, 1])

    def test_slice_thickness_computed_from_positions(self):
        datasets = _axial_stack(5, z_step=3.0)
        # Override SliceThickness to 1.0 to confirm inter-slice distance wins.
        for ds in datasets:
            ds.SliceThickness = 1.0
        stack = SliceStack.from_datasets(datasets)
        # The inter-slice distances are all 3.0 → median = 3.0
        self.assertAlmostEqual(stack.slice_thickness, 3.0, places=5)

    def test_fewer_than_two_datasets_returns_none(self):
        # Zero datasets returns None; one dataset is allowed (e.g. one-slice MPR).
        self.assertIsNone(SliceStack.from_datasets([]))

    def test_all_missing_ipp_returns_none(self):
        ds1 = Dataset()
        ds1.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        ds2 = Dataset()
        ds2.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        self.assertIsNone(SliceStack.from_datasets([ds1, ds2]))

    def test_partial_missing_metadata_skips_bad_slices(self):
        good = _axial_stack(4)
        bad = Dataset()  # no IPP/IOP
        datasets = [good[0], bad, good[1], good[2], good[3]]
        stack = SliceStack.from_datasets(datasets)
        self.assertIsNotNone(stack)
        self.assertEqual(len(stack.planes), 4)

    def test_position_of(self):
        datasets = _axial_stack(5, z_start=0.0, z_step=5.0)
        stack = SliceStack.from_datasets(datasets)
        # A plane at z=25 should report position 25.
        plane = SlicePlane.from_dataset(_make_dataset((0.0, 0.0, 25.0)))
        self.assertAlmostEqual(stack.position_of(plane), 25.0, places=5)


# ---------------------------------------------------------------------------
# find_nearest_slice tests
# ---------------------------------------------------------------------------

class TestFindNearestSlice(unittest.TestCase):
    """Tests for find_nearest_slice."""

    def setUp(self):
        """Axial source stack (Z = 0, 5, 10, …, 45 mm) and coronal target stack."""
        self.axial = SliceStack.from_datasets(_axial_stack(10, z_start=0.0, z_step=5.0))
        self.coronal = SliceStack.from_datasets(_coronal_stack(10, y_start=0.0, y_step=5.0))

    def _axial_plane(self, z: float) -> SlicePlane:
        return SlicePlane.from_dataset(_make_dataset((0.0, 0.0, z)))

    def _coronal_plane(self, y: float) -> SlicePlane:
        return SlicePlane.from_dataset(_make_dataset((0.0, y, 0.0), iop=(1, 0, 0, 0, 0, -1)))

    # -- Axial source, axial target (same orientation) ----------------------

    def test_exact_match_axial(self):
        stack = self.axial
        for i in range(10):
            plane = self._axial_plane(i * 5.0)
            result = find_nearest_slice(plane, stack)
            self.assertEqual(result, stack.original_indices[i])

    def test_between_slices_picks_nearest(self):
        # z=7.5 is midway between slice 1 (z=5) and slice 2 (z=10).
        # Both are equally close; accept either.
        plane = self._axial_plane(7.5)
        result = find_nearest_slice(plane, self.axial)
        self.assertIn(result, [1, 2])

    def test_z_closer_to_lower(self):
        # z=6 is closer to z=5 (slice 1) than z=10 (slice 2).
        plane = self._axial_plane(6.0)
        result = find_nearest_slice(plane, self.axial)
        self.assertEqual(result, 1)

    def test_z_closer_to_upper(self):
        # z=9 is closer to z=10 (slice 2) than z=5 (slice 1).
        plane = self._axial_plane(9.0)
        result = find_nearest_slice(plane, self.axial)
        self.assertEqual(result, 2)

    def test_first_and_last_slice(self):
        self.assertEqual(find_nearest_slice(self._axial_plane(0.0), self.axial), 0)
        self.assertEqual(find_nearest_slice(self._axial_plane(45.0), self.axial), 9)

    # -- Tolerance -----------------------------------------------------------

    def test_within_tolerance_returns_index(self):
        # z=47 is 2 mm outside the stack (last slice at 45).
        plane = self._axial_plane(47.0)
        result = find_nearest_slice(plane, self.axial, tolerance_mm=3.0)
        self.assertIsNotNone(result)

    def test_outside_tolerance_returns_none(self):
        # z=52 is 7 mm past the last slice (45); tolerance is 2.5 mm.
        plane = self._axial_plane(52.0)
        result = find_nearest_slice(plane, self.axial, tolerance_mm=2.5)
        self.assertIsNone(result)

    def test_tolerance_at_exactly_boundary(self):
        # Distance = exactly the tolerance → should be included (<=).
        plane = self._axial_plane(47.5)  # 2.5 mm past slice at z=45
        result = find_nearest_slice(plane, self.axial, tolerance_mm=2.5)
        self.assertIsNotNone(result)

    # -- Cross-orientation: axial source, coronal target --------------------

    def test_axial_source_coronal_target_origin(self):
        """
        An axial plane at z=0, y=0 should map to the coronal slice at y=0
        (first coronal slice) because the coronal stack normal is +Y and the
        axial plane's origin has y=0.
        """
        plane = self._axial_plane(0.0)   # origin at (0, 0, 0)
        result = find_nearest_slice(plane, self.coronal)
        # coronal planes at y=0,5,10,… → nearest is y=0 → original index 0
        self.assertEqual(result, 0)

    def test_axial_source_coronal_target_y5(self):
        # Axial plane at origin (0, 5, 0) should match coronal at y=5.
        plane = SlicePlane.from_dataset(_make_dataset((0.0, 5.0, 0.0)))
        result = find_nearest_slice(plane, self.coronal)
        self.assertEqual(result, 1)

    # -- Near-perpendicular (axial source, axial target but no Z overlap) ---

    def test_near_perpendicular_many_source_positions_map_to_same_target(self):
        """
        Axial planes at z=0..45 all have origin y=0.
        Coronal target (stacked along Y) should always pick the coronal slice
        at y=0 (index 0) since all axial origins have y=0.
        """
        axial_stack = SliceStack.from_datasets(
            _axial_stack(10, z_start=0.0, z_step=5.0)
        )
        coronal_stack = SliceStack.from_datasets(
            _coronal_stack(10, y_start=0.0, y_step=5.0)
        )
        results = set()
        for i in range(10):
            plane = self._axial_plane(i * 5.0)
            r = find_nearest_slice(plane, coronal_stack)
            results.add(r)
        # All should map to the same coronal slice (index 0, y=0).
        self.assertEqual(results, {0})


# ---------------------------------------------------------------------------
# plane_plane_intersection tests
# ---------------------------------------------------------------------------

class TestPlanePlaneIntersection(unittest.TestCase):
    """Tests for plane_plane_intersection."""

    def _axial_plane(self, z: float = 0.0) -> SlicePlane:
        return SlicePlane.from_dataset(_make_dataset((0.0, 0.0, z)))

    def _coronal_plane(self, y: float = 0.0) -> SlicePlane:
        return SlicePlane.from_dataset(_make_dataset((0.0, y, 0.0), iop=(1, 0, 0, 0, 0, -1)))

    def test_axial_and_coronal_intersect(self):
        result = plane_plane_intersection(self._axial_plane(), self._coronal_plane())
        self.assertIsNotNone(result)
        point, direction = result
        self.assertEqual(point.shape, (3,))
        self.assertEqual(direction.shape, (3,))

    def test_intersection_direction_is_unit_vector(self):
        result = plane_plane_intersection(self._axial_plane(), self._coronal_plane())
        point, direction = result
        self.assertAlmostEqual(float(np.linalg.norm(direction)), 1.0, places=10)

    def test_axial_coronal_direction_is_along_x(self):
        """
        Axial normal = (0,0,1), coronal normal = (0,1,0).
        Intersection direction = (0,0,1) × (0,1,0) = (-1, 0, 0) or (+1, 0, 0).
        """
        result = plane_plane_intersection(self._axial_plane(), self._coronal_plane())
        point, direction = result
        # Should be along X axis (±1, 0, 0).
        np.testing.assert_array_almost_equal(np.abs(direction), [1, 0, 0], decimal=6)

    def test_intersection_point_lies_on_both_planes(self):
        a = self._axial_plane(10.0)
        b = self._coronal_plane(5.0)
        result = plane_plane_intersection(a, b)
        self.assertIsNotNone(result)
        point, _ = result
        # Point satisfies n · P = n · origin for both planes.
        d_a = float(np.dot(a.normal, point) - np.dot(a.normal, a.origin))
        d_b = float(np.dot(b.normal, point) - np.dot(b.normal, b.origin))
        self.assertAlmostEqual(d_a, 0.0, places=8)
        self.assertAlmostEqual(d_b, 0.0, places=8)

    def test_parallel_planes_return_none(self):
        a = self._axial_plane(0.0)
        b = self._axial_plane(10.0)
        self.assertIsNone(plane_plane_intersection(a, b))

    def test_near_parallel_planes_return_none(self):
        """
        Planes whose normals differ by less than ~1e-8 radians are treated as
        parallel and should return None.

        The cross-product magnitude of two near-unit normals equals |sin(θ)|
        where θ is the angle between them.  Using epsilon = 1e-9 in the IOP
        column cosine produces a cross-product magnitude ~1e-9 < 1e-8 threshold.
        """
        a = SlicePlane.from_dataset(_make_dataset((0, 0, 0)))
        epsilon = 1e-9
        ds_b = _make_dataset((0, 0, 5), iop=(1, 0, 0, 0, 1, epsilon))
        b = SlicePlane.from_dataset(ds_b)
        # Cross-product magnitude ≈ 1e-9 < 1e-8 threshold → None.
        result = plane_plane_intersection(a, b)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# project_line_to_2d tests
# ---------------------------------------------------------------------------

class TestProjectLineTo2d(unittest.TestCase):
    """Tests for project_line_to_2d."""

    def test_x_axis_line_on_axial_plane(self):
        """
        A line along X through the origin, projected onto the axial plane at
        z=0 (origin=(0,0,0), row=+X, col=+Y), should give a horizontal line
        (same row, changing col).
        """
        plane = SlicePlane.from_dataset(_make_dataset((0.0, 0.0, 0.0)))
        point = np.array([0.0, 0.0, 0.0])
        direction = np.array([1.0, 0.0, 0.0])
        result = project_line_to_2d(point, direction, plane)
        self.assertIsNotNone(result)
        col1, row1, col2, row2 = result
        # Row should be the same (line is horizontal in pixel space).
        self.assertAlmostEqual(row1, row2, places=6)
        # Col should change (direction has X component → col changes).
        self.assertNotAlmostEqual(col1, col2, places=1)

    def test_y_axis_line_on_axial_plane(self):
        """
        A line along Y projected onto the axial plane (row=+X, col=+Y)
        should give a vertical line (same col, changing row).
        """
        plane = SlicePlane.from_dataset(_make_dataset((0.0, 0.0, 0.0)))
        point = np.array([0.0, 0.0, 0.0])
        direction = np.array([0.0, 1.0, 0.0])
        result = project_line_to_2d(point, direction, plane)
        self.assertIsNotNone(result)
        col1, row1, col2, row2 = result
        self.assertAlmostEqual(col1, col2, places=6)
        self.assertNotAlmostEqual(row1, row2, places=1)

    def test_missing_spacing_returns_none(self):
        ds = Dataset()
        ds.ImagePositionPatient = [0, 0, 0]
        ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
        # No PixelSpacing set → row/col_spacing are None.
        plane = SlicePlane.from_dataset(ds)
        point = np.array([0.0, 0.0, 0.0])
        direction = np.array([1.0, 0.0, 0.0])
        self.assertIsNone(project_line_to_2d(point, direction, plane))

    def test_line_parallel_to_normal_returns_none(self):
        """
        A line pointing along the plane normal appears as a point in 2-D
        and cannot be drawn — should return None.
        """
        plane = SlicePlane.from_dataset(_make_dataset((0.0, 0.0, 0.0)))
        # normal of axial plane = (0,0,1)
        point = np.array([0.0, 0.0, 0.0])
        direction = np.array([0.0, 0.0, 1.0])  # parallel to normal
        self.assertIsNone(project_line_to_2d(point, direction, plane))

    def test_pixel_spacing_scaling_applied(self):
        """
        With pixel spacing = 2.0 mm/pixel, a 4000-mm line along X (2000 mm
        each direction from center) should produce 2000 pixel columns of separation.
        """
        plane = SlicePlane.from_dataset(
            _make_dataset((0.0, 0.0, 0.0), pixel_spacing=(2.0, 2.0))
        )
        point = np.array([0.0, 0.0, 0.0])
        direction = np.array([1.0, 0.0, 0.0])
        result = project_line_to_2d(point, direction, plane)
        self.assertIsNotNone(result)
        col1, row1, col2, row2 = result
        # col2 - col1 = 4000 mm / 2 mm/pixel = 2000 pixels
        self.assertAlmostEqual(abs(col2 - col1), 2000.0, places=4)


# ---------------------------------------------------------------------------
# clip_line_to_rect tests
# ---------------------------------------------------------------------------

class TestClipLineToRect(unittest.TestCase):
    """Tests for clip_line_to_rect."""

    def test_segment_fully_inside(self):
        result = clip_line_to_rect(10, 10, 50, 50, 100, 100)
        self.assertIsNotNone(result)
        self.assertEqual(result, (10.0, 10.0, 50.0, 50.0))

    def test_segment_crosses_one_edge(self):
        # Line from (10, 10) to (150, 50) crosses right edge at x=100
        result = clip_line_to_rect(10, 10, 150, 50, 100, 100)
        self.assertIsNotNone(result)
        c1, r1, c2, r2 = result
        self.assertAlmostEqual(c2, 100.0, places=5)
        self.assertTrue(0 <= c1 <= 100 and 0 <= c2 <= 100)
        self.assertTrue(0 <= r1 <= 100 and 0 <= r2 <= 100)

    def test_segment_crosses_two_edges(self):
        # Line from (-10, 50) to (110, 50) crosses left and right
        result = clip_line_to_rect(-10, 50, 110, 50, 100, 100)
        self.assertIsNotNone(result)
        c1, r1, c2, r2 = result
        self.assertAlmostEqual(c1, 0.0, places=5)
        self.assertAlmostEqual(c2, 100.0, places=5)
        self.assertAlmostEqual(r1, 50.0, places=5)
        self.assertAlmostEqual(r2, 50.0, places=5)

    def test_segment_fully_outside(self):
        result = clip_line_to_rect(-50, -50, -10, -10, 100, 100)
        self.assertIsNone(result)

    def test_segment_fully_outside_right(self):
        result = clip_line_to_rect(150, 50, 200, 50, 100, 100)
        self.assertIsNone(result)

    def test_degenerate_zero_length_inside(self):
        result = clip_line_to_rect(50, 50, 50, 50, 100, 100)
        self.assertIsNotNone(result)
        self.assertEqual(result, (50.0, 50.0, 50.0, 50.0))

    def test_degenerate_zero_length_outside(self):
        result = clip_line_to_rect(150, 50, 150, 50, 100, 100)
        self.assertIsNone(result)

    def test_invalid_rect_returns_none(self):
        self.assertIsNone(clip_line_to_rect(0, 0, 10, 10, 0, 100))
        self.assertIsNone(clip_line_to_rect(0, 0, 10, 10, 100, 0))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
