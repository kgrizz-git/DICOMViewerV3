"""
tests/test_slice_sync_outside_coverage_hint.py

Unit tests for slice-sync skip reporting (T6/T7/T9 of
FUSION_STACK_ENDS_VARIABLE_SLICE_THICKNESS_PLAN).

Verifies that when the source slice position is outside the target series
coverage (find_nearest_slice returns None), the SliceSyncCoordinator:
  1. Does NOT call display_slice on the skipped target.
  2. Calls app.main_window.update_status with the expected hint text.

When the source IS inside the target range, the target is updated normally
and no hint is emitted.

No real DICOM files are required — SlicePlane and SliceStack objects are
constructed directly from numpy arrays.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from core.slice_geometry import SlicePlane, SliceStack
from core.slice_sync_coordinator import SliceSyncCoordinator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AXIAL_ROW = np.array([1.0, 0.0, 0.0])
_AXIAL_COL = np.array([0.0, 1.0, 0.0])
_AXIAL_NORM = np.array([0.0, 0.0, 1.0])


def _make_plane(z_mm: float) -> SlicePlane:
    """Return a simple axial SlicePlane at the given z position."""
    return SlicePlane(
        origin=np.array([0.0, 0.0, z_mm]),
        row_cosine=_AXIAL_ROW,
        col_cosine=_AXIAL_COL,
    )


def _make_stack(z_positions, slice_thickness: float = 5.0) -> SliceStack:
    """
    Build a SliceStack from a sequence of z positions.

    original_indices maps sorted position → dataset index (identity mapping
    here since we build positions in sorted order).
    """
    planes = [_make_plane(z) for z in z_positions]
    positions = list(z_positions)
    return SliceStack(
        planes=planes,
        original_indices=list(range(len(planes))),
        stack_normal=_AXIAL_NORM,
        positions=positions,
        slice_thickness=slice_thickness,
    )


def _make_mock_app(
    source_idx: int,
    source_z: float,
    target_idx: int,
    target_z_positions,
    target_slice_thickness: float = 5.0,
) -> MagicMock:
    """
    Build a minimal mock DICOMViewerApp with two subwindows:
      - source_idx: the subwindow that triggered the slice change.
      - target_idx: the subwindow that slice sync should update (or skip).

    The mock exposes:
      - app.subwindow_data
      - app.subwindow_managers (with a mock slice_display_manager for the target)
      - app.current_studies
      - app.main_window.update_status (callable for hint verification)
    """
    app = MagicMock()

    # Source subwindow data.
    source_data = {
        "current_slice_index": 0,
        "current_study_uid": "study-1",
        "current_series_uid": "source-series",
        "current_datasets": [object()],  # single dummy dataset
        "is_mpr": False,
    }

    # Target subwindow data — enough entries for display_slice to succeed.
    n_target = len(target_z_positions)
    target_datasets = [object() for _ in range(n_target)]
    target_data = {
        "current_slice_index": 0,
        "current_study_uid": "study-1",
        "current_series_uid": "target-series",
        "current_datasets": target_datasets,
        "is_mpr": False,
    }

    app.subwindow_data = {source_idx: source_data, target_idx: target_data}

    # Mock slice_display_manager for the target.
    mock_sdm = MagicMock()
    app.subwindow_managers = {
        source_idx: {},
        target_idx: {"slice_display_manager": mock_sdm},
    }

    app.current_studies = {}
    app.main_window = MagicMock()
    app.main_window.update_status = MagicMock()

    return app, mock_sdm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSliceSyncOutsideCoverageHint(unittest.TestCase):
    """Tests for SliceSyncCoordinator outside-coverage skip hints."""

    def _make_coordinator_with_stacks(
        self,
        source_idx: int,
        source_stack: SliceStack,
        target_idx: int,
        target_stack: SliceStack,
        app: MagicMock,
    ) -> SliceSyncCoordinator:
        """Build a coordinator and pre-populate its geometry cache."""
        coord = SliceSyncCoordinator(app)
        coord.set_enabled(True)
        coord.set_groups([[source_idx, target_idx]])

        # Populate the stack cache directly to bypass dataset-to-stack conversion.
        source_data = app.subwindow_data[source_idx]
        target_data = app.subwindow_data[target_idx]

        source_key = (
            source_data["current_study_uid"],
            source_data["current_series_uid"],
        )
        target_key = (
            target_data["current_study_uid"],
            target_data["current_series_uid"],
        )
        coord._stack_cache[source_key] = source_stack
        coord._stack_cache[target_key] = target_stack

        return coord

    # ------------------------------------------------------------------ #
    # Source below target range                                            #
    # ------------------------------------------------------------------ #

    def test_source_below_target_no_display_slice(self):
        """
        Source at z=-10 mm, target stack covers 10–30 mm.
        Target pane must NOT be updated (display_slice not called).
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, mock_sdm = _make_mock_app(
            source_idx, -10.0, target_idx, target_z
        )
        source_stack = _make_stack([-10.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        mock_sdm.display_slice.assert_not_called()

    def test_source_below_target_hint_emitted(self):
        """
        Source at z=-10 mm → hint text should reference window 2 (target_idx+1).
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, _ = _make_mock_app(
            source_idx, -10.0, target_idx, target_z
        )
        source_stack = _make_stack([-10.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        app.main_window.update_status.assert_called_once()
        status_text = app.main_window.update_status.call_args[0][0]
        self.assertIn("window 2", status_text)
        self.assertIn("outside", status_text.lower())

    # ------------------------------------------------------------------ #
    # Source above target range                                            #
    # ------------------------------------------------------------------ #

    def test_source_above_target_no_display_slice(self):
        """
        Source at z=50 mm, target stack covers 10–30 mm.
        Target pane must NOT be updated.
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, mock_sdm = _make_mock_app(
            source_idx, 50.0, target_idx, target_z
        )
        source_stack = _make_stack([50.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        mock_sdm.display_slice.assert_not_called()

    def test_source_above_target_hint_emitted(self):
        """Source above target → hint emitted with correct window number."""
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, _ = _make_mock_app(
            source_idx, 50.0, target_idx, target_z
        )
        source_stack = _make_stack([50.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        app.main_window.update_status.assert_called_once()
        status_text = app.main_window.update_status.call_args[0][0]
        self.assertIn("window 2", status_text)

    # ------------------------------------------------------------------ #
    # Source inside target range — normal update                           #
    # ------------------------------------------------------------------ #

    def test_source_inside_target_display_slice_called(self):
        """
        Source at z=20 mm is within the target stack (10–30 mm).
        Target should be updated; display_slice must be called.
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, mock_sdm = _make_mock_app(
            source_idx, 20.0, target_idx, target_z
        )
        # Source is already at idx=1 (z=20); set current_slice_index so
        # the "already on correct slice" short-circuit does not fire for
        # the target (target starts at idx=0).
        app.subwindow_data[target_idx]["current_slice_index"] = 0

        source_stack = _make_stack([20.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        mock_sdm.display_slice.assert_called_once()

    def test_source_inside_target_no_hint_emitted(self):
        """
        Source inside target range → no outside-coverage hint.
        update_status should be called with empty string (clear) only if a
        previous hint was present; here no previous hint exists, so it is
        either not called or called with empty string.
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, _ = _make_mock_app(
            source_idx, 20.0, target_idx, target_z
        )
        app.subwindow_data[target_idx]["current_slice_index"] = 0

        source_stack = _make_stack([20.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)

        # Either not called at all (no hint needed) or called with empty string.
        calls = app.main_window.update_status.call_args_list
        for c in calls:
            self.assertEqual(c[0][0], "", "Should only emit empty string when clearing")

    # ------------------------------------------------------------------ #
    # Hint debounce (change-only)                                          #
    # ------------------------------------------------------------------ #

    def test_hint_not_repeated_on_same_state(self):
        """
        If source remains outside target on consecutive calls, update_status
        must NOT be called again (debounce).
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        app, _ = _make_mock_app(
            source_idx, -10.0, target_idx, target_z
        )
        source_stack = _make_stack([-10.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_stack, target_idx, target_stack, app
        )

        coord.on_slice_changed(source_idx)
        coord.on_slice_changed(source_idx)  # same state, should NOT re-emit

        self.assertEqual(app.main_window.update_status.call_count, 1)

    def test_hint_cleared_when_source_moves_inside(self):
        """
        Moving source from outside to inside should clear the hint (empty string).
        """
        source_idx, target_idx = 0, 1
        target_z = [10.0, 20.0, 30.0]

        # First: source below (z=-10)
        app, _ = _make_mock_app(
            source_idx, -10.0, target_idx, target_z
        )
        source_below_stack = _make_stack([-10.0], slice_thickness=5.0)
        source_inside_stack = _make_stack([20.0], slice_thickness=5.0)
        target_stack = _make_stack(target_z, slice_thickness=5.0)

        coord = self._make_coordinator_with_stacks(
            source_idx, source_below_stack, target_idx, target_stack, app
        )
        coord.on_slice_changed(source_idx)  # hint emitted

        # Swap source stack to an inside position and reset target index.
        source_key = (
            app.subwindow_data[source_idx]["current_study_uid"],
            app.subwindow_data[source_idx]["current_series_uid"],
        )
        coord._stack_cache[source_key] = source_inside_stack
        app.subwindow_data[target_idx]["current_slice_index"] = 0

        coord.on_slice_changed(source_idx)  # now inside → clear hint

        # The second call should have emitted an empty-string clear.
        calls = [c[0][0] for c in app.main_window.update_status.call_args_list]
        self.assertIn("", calls, "Hint clear (empty string) expected after returning inside")


if __name__ == "__main__":
    unittest.main()
