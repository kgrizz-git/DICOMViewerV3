"""Unit tests for ``core.mpr_geometry`` (MPR output grid, stack positions, standard planes)."""

from __future__ import annotations

import unittest

import numpy as np

from core.mpr_geometry import (
    compute_mpr_output_grid,
    stack_positions_along_normal,
    standard_slice_planes_lps,
)
from core.slice_geometry import SlicePlane


class TestMprGeometryGrid(unittest.TestCase):
    def test_identity_volume_axial_grid(self) -> None:
        """10×10×5 mm axis-aligned volume: expect 10×10 in-plane and 5 slices at 1 mm."""
        planes = standard_slice_planes_lps()
        axial = planes["axial"]
        grid = compute_mpr_output_grid(
            volume_origin=np.zeros(3),
            volume_direction=np.eye(3),
            volume_size_xyz=(10, 10, 5),
            volume_spacing_xyz=(1.0, 1.0, 1.0),
            output_row_cosine=axial.row_cosine,
            output_col_cosine=axial.col_cosine,
            output_normal=axial.normal,
            output_spacing_mm=1.0,
            output_thickness_mm=1.0,
        )
        self.assertEqual(grid.rows_px, 10)
        self.assertEqual(grid.cols_px, 10)
        self.assertEqual(grid.n_slices, 5)
        np.testing.assert_allclose(grid.origin, np.zeros(3), atol=1e-9)

    def test_stack_positions_along_normal(self) -> None:
        n = np.array([0.0, 0.0, 1.0])
        planes = [
            SlicePlane(
                origin=np.array([0.0, 0.0, float(z)]),
                row_cosine=np.array([1.0, 0.0, 0.0]),
                col_cosine=np.array([0.0, 1.0, 0.0]),
            )
            for z in (1.0, 2.0, 3.0)
        ]
        pos = stack_positions_along_normal(planes, n)
        self.assertEqual(pos, [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
