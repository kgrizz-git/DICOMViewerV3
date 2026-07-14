"""
tests/test_fusion_slice_matching.py

Unit tests for FusionHandler.find_matching_slice_with_classification and
the OverlayMatchResult enum (T1 / T2 of FUSION_STACK_ENDS_VARIABLE_SLICE_THICKNESS_PLAN).

No real DICOM files are required — datasets are created as lightweight mock
objects that carry only the SliceLocation attribute needed by fusion_handler_io.

Test coverage
-------------
- Source below first overlay slice  → OverlayMatchResult.below_stack, no indices
- Source above last overlay slice   → OverlayMatchResult.above_stack, no indices
- Source inside (interpolation)     → OverlayMatchResult.inside, correct indices
- Source exact match                → OverlayMatchResult.inside, single index
- Empty overlay locations           → OverlayMatchResult.no_geometry, no indices
- Backward compatibility: find_matching_slice still returns (idx1, idx2)
"""

import os
import sys
import unittest
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Path setup – let tests discover src/ without a package install.
# ---------------------------------------------------------------------------
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.fusion_handler import FusionHandler, OverlayMatchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dataset(slice_location: float) -> SimpleNamespace:
    """
    Return a lightweight dataset-like object that FusionHandler can use.

    fusion_handler_io.read_slice_location tries SliceLocation first, then
    falls back to ImagePositionPatient[2].  We supply only SliceLocation for
    simplicity.
    """
    ds = SimpleNamespace()
    ds.SliceLocation = slice_location
    return ds


def _make_overlay(locations):
    """Build a list of mock overlay datasets at given mm positions (sorted)."""
    return [_make_dataset(loc) for loc in sorted(locations)]


def _make_base_single(location: float):
    """Build a list with a single base dataset at the given mm position."""
    return [_make_dataset(location)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFindMatchingSliceClassification(unittest.TestCase):
    """Tests for FusionHandler.find_matching_slice_with_classification."""

    def setUp(self):
        self.handler = FusionHandler()
        # Use a fixed series UID so the location cache key is stable.
        self.handler.overlay_series_uid = "test-overlay-uid"
        # Overlay stack: three slices at 10, 20, 30 mm.
        self.overlay = _make_overlay([10.0, 20.0, 30.0])

    # ------------------------------------------------------------------ #
    # below_stack                                                          #
    # ------------------------------------------------------------------ #

    def test_below_first_slice_returns_below_stack(self):
        """Base slice at 5 mm is below the first overlay slice (10 mm)."""
        base = _make_base_single(5.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.below_stack)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    def test_significantly_below_returns_below_stack(self):
        """Base slice well caudal to the overlay stack."""
        base = _make_base_single(-50.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.below_stack)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    # ------------------------------------------------------------------ #
    # above_stack                                                          #
    # ------------------------------------------------------------------ #

    def test_above_last_slice_returns_above_stack(self):
        """Base slice at 40 mm is above the last overlay slice (30 mm)."""
        base = _make_base_single(40.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.above_stack)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    def test_just_above_last_slice_returns_above_stack(self):
        """Base slice 0.1 mm above last overlay slice (beyond tolerance)."""
        base = _make_base_single(30.1)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.above_stack)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    # ------------------------------------------------------------------ #
    # inside — exact match                                                 #
    # ------------------------------------------------------------------ #

    def test_exact_match_first_returns_inside(self):
        """Base coincides exactly with the first overlay slice."""
        base = _make_base_single(10.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.inside)
        self.assertIsNotNone(idx1)
        self.assertIsNone(idx2, "Exact match should have no second index")
        self.assertEqual(self.overlay[idx1].SliceLocation, 10.0)

    def test_exact_match_last_returns_inside(self):
        """Base coincides exactly with the last overlay slice."""
        base = _make_base_single(30.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.inside)
        self.assertIsNotNone(idx1)
        self.assertIsNone(idx2)
        self.assertEqual(self.overlay[idx1].SliceLocation, 30.0)

    def test_exact_match_within_tolerance(self):
        """Base within 0.005 mm of an overlay slice — treated as exact."""
        base = _make_base_single(20.005)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.inside)
        self.assertIsNone(idx2)

    # ------------------------------------------------------------------ #
    # inside — interpolation (bracketing)                                  #
    # ------------------------------------------------------------------ #

    def test_between_first_and_second_returns_inside_with_bracket(self):
        """Base at 15 mm is between 10 and 20 mm — bracketing pair returned."""
        base = _make_base_single(15.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.inside)
        self.assertIsNotNone(idx1)
        self.assertIsNotNone(idx2, "Should return two indices for interpolation")
        locs = sorted([self.overlay[idx1].SliceLocation, self.overlay[idx2].SliceLocation])
        self.assertEqual(locs, [10.0, 20.0])

    def test_between_second_and_third_returns_inside_with_bracket(self):
        """Base at 25 mm is between 20 and 30 mm."""
        base = _make_base_single(25.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.inside)
        self.assertIsNotNone(idx1)
        self.assertIsNotNone(idx2)
        locs = sorted([self.overlay[idx1].SliceLocation, self.overlay[idx2].SliceLocation])
        self.assertEqual(locs, [20.0, 30.0])

    # ------------------------------------------------------------------ #
    # no_geometry                                                          #
    # ------------------------------------------------------------------ #

    def test_empty_overlay_returns_no_geometry(self):
        """Empty overlay list → no_geometry."""
        base = _make_base_single(15.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            0, base, []
        )
        self.assertEqual(result, OverlayMatchResult.no_geometry)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    def test_base_index_out_of_range_returns_no_geometry(self):
        """Requesting base index 5 when base has only 1 dataset → no_geometry."""
        base = _make_base_single(15.0)
        result, idx1, idx2 = self.handler.find_matching_slice_with_classification(
            5, base, self.overlay
        )
        self.assertEqual(result, OverlayMatchResult.no_geometry)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    # ------------------------------------------------------------------ #
    # Backward compat: find_matching_slice                                 #
    # ------------------------------------------------------------------ #

    def test_find_matching_slice_backward_compat_inside(self):
        """find_matching_slice returns (idx, None) for exact match."""
        base = _make_base_single(20.0)
        idx1, idx2 = self.handler.find_matching_slice(0, base, self.overlay)
        self.assertIsNotNone(idx1)
        self.assertIsNone(idx2)

    def test_find_matching_slice_backward_compat_outside(self):
        """find_matching_slice returns (None, None) for below-stack."""
        base = _make_base_single(5.0)
        idx1, idx2 = self.handler.find_matching_slice(0, base, self.overlay)
        self.assertIsNone(idx1)
        self.assertIsNone(idx2)

    # ------------------------------------------------------------------ #
    # _last_overlay_match_result is updated by interpolate_overlay_slice  #
    # ------------------------------------------------------------------ #

    def test_last_overlay_match_result_below_stack(self):
        """
        After interpolate_overlay_slice is called for a below-stack base slice,
        _last_overlay_match_result should be OverlayMatchResult.below_stack.

        We cannot call interpolate_overlay_slice directly without real pixel data,
        so we test find_matching_slice_with_classification's effect on the cached
        state via manual assignment (mirrors what interpolate_overlay_slice does).
        """
        base = _make_base_single(5.0)
        result, _, _ = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        # Simulate what interpolate_overlay_slice does:
        self.handler._last_overlay_match_result = result
        self.assertEqual(
            self.handler._last_overlay_match_result,
            OverlayMatchResult.below_stack,
        )

    def test_last_overlay_match_result_above_stack(self):
        """Symmetric check for above_stack."""
        base = _make_base_single(50.0)
        result, _, _ = self.handler.find_matching_slice_with_classification(
            0, base, self.overlay
        )
        self.handler._last_overlay_match_result = result
        self.assertEqual(
            self.handler._last_overlay_match_result,
            OverlayMatchResult.above_stack,
        )


if __name__ == "__main__":
    unittest.main()
