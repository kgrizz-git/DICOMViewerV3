"""
Focused tests for MPR overlay/combine formatting and helper logic.

These tests intentionally target pure/small helper paths so they can run
quickly without constructing a full Qt application.
"""

import os
import sys
import unittest

import numpy as np
from pydicom.dataset import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main as main_module
from core.dicom_parser import DICOMParser
from core.mpr_stack_combine import apply_mpr_stack_combine
from gui.mpr_controller import MprController
from gui.overlay_manager import OverlayManager
from gui.overlay_text_builder import get_corner_text


class TestMprOverlayHelpers(unittest.TestCase):
    """Unit tests for MPR helper behavior used by overlays and banners."""

    def test_compute_mpr_combine_range_center_and_edges(self):
        # Center case (n=8, i=4, planes=4) -> [2, 5]
        self.assertEqual(MprController._compute_mpr_combine_range(8, 4, 4), (2, 5))
        # Start edge clamps at 0
        self.assertEqual(MprController._compute_mpr_combine_range(8, 0, 4), (0, 3))
        # End edge clamps at n-1
        self.assertEqual(MprController._compute_mpr_combine_range(8, 7, 4), (4, 7))

    def test_build_mpr_banner_text_includes_active_mode(self):
        data = {
            "mpr_orientation": "Axial",
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "aip",
        }
        self.assertEqual(MprController._build_mpr_banner_text(data), "MPR - Axial (AIP)")

        data["mpr_combine_mode"] = "mip"
        self.assertEqual(MprController._build_mpr_banner_text(data), "MPR - Axial (MIP)")

        data["mpr_combine_enabled"] = False
        self.assertEqual(MprController._build_mpr_banner_text(data), "MPR - Axial")

    def test_overlay_text_shows_projection_range_and_type(self):
        ds = Dataset()
        ds.InstanceNumber = 3
        ds.SliceThickness = 1.5
        parser = DICOMParser(ds)
        text = get_corner_text(
            parser,
            tags=["InstanceNumber", "SliceThickness"],
            privacy_mode=False,
            total_slices=10,
            projection_enabled=True,
            projection_start_slice=1,
            projection_end_slice=4,
            projection_total_thickness=6.0,
            projection_type="aip",
        )
        self.assertIn("Slice 3/10 (2-5 AIP)", text)
        self.assertIn("Slice Thickness: 1.5 (6.0)", text)

    def test_overlay_corner_text_mip_minip_vocabulary_matches_widget_graphics_contract(self):
        """MPR/combine labels use the same get_corner_text path for QWidget and QGraphics overlays."""
        ds = Dataset()
        ds.InstanceNumber = 1
        ds.SliceThickness = 2.0
        parser = DICOMParser(ds)
        for mode, upper in (("mip", "MIP"), ("minip", "MinIP")):
            text = get_corner_text(
                parser,
                tags=["InstanceNumber", "SliceThickness"],
                privacy_mode=False,
                total_slices=5,
                projection_enabled=True,
                projection_start_slice=0,
                projection_end_slice=1,
                projection_total_thickness=4.0,
                projection_type=mode,
            )
            self.assertIn(upper, text)

    def test_overlay_text_visibility_helper_matches_spacebar_cycle(self):
        overlay_manager = OverlayManager(use_widget_overlays=False)

        self.assertTrue(overlay_manager.should_show_text_overlays())

        overlay_manager.set_visibility_state(1)
        self.assertFalse(overlay_manager.should_show_text_overlays())

        overlay_manager.set_visibility_state(2)
        self.assertFalse(overlay_manager.should_show_text_overlays())

        overlay_manager.set_visibility_state(0)
        overlay_manager.set_mode("hidden")
        self.assertFalse(overlay_manager.should_show_text_overlays())

    def test_global_overlay_refresh_redisplays_mpr_slice(self):
        """Spacebar's all-pane refresh must route MPR panes through MprController."""

        class _Layout:
            def get_all_subwindows(self):
                return [object()]

        class _OverlayCoordinator:
            def __init__(self):
                self.calls = 0

            def handle_overlay_config_applied(self):
                self.calls += 1

        class _MprController:
            def __init__(self):
                self.calls = []

            def is_mpr(self, idx):
                return idx == 0

            def display_mpr_slice(self, idx, slice_index):
                self.calls.append((idx, slice_index))

        fake_app = type("FakeApp", (), {})()
        fake_app.multi_window_layout = _Layout()
        fake_app.subwindow_data = {0: {"is_mpr": True, "mpr_slice_index": 3}}
        fake_app._mpr_controller = _MprController()
        fake_app.subwindow_managers = {0: {"overlay_coordinator": _OverlayCoordinator()}}

        main_module.DICOMViewerApp._refresh_overlay_all_subwindows(fake_app)

        self.assertEqual(fake_app._mpr_controller.calls, [(0, 3)])
        self.assertEqual(fake_app.subwindow_managers[0]["overlay_coordinator"].calls, 0)

    def test_combine_then_rescale_matches_expected_math(self):
        stack = [
            np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
            np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float32),
            np.array([[9.0, 10.0], [11.0, 12.0]], dtype=np.float32),
        ]
        combined = apply_mpr_stack_combine(
            stack,
            slice_index=1,
            enabled=True,
            mode="aip",
            n_planes=3,
        )
        slope = 2.0
        intercept = -100.0
        actual = combined * slope + intercept

        expected_combined = np.mean(np.stack(stack, axis=0), axis=0).astype(np.float32)
        expected = expected_combined * slope + intercept
        np.testing.assert_allclose(actual, expected)

    def test_mip_then_rescale_matches_expected_math(self):
        stack = [
            np.array([[1.0, 10.0]], dtype=np.float32),
            np.array([[5.0, 2.0]], dtype=np.float32),
        ]
        combined = apply_mpr_stack_combine(
            stack, slice_index=0, enabled=True, mode="mip", n_planes=2
        )
        slope, intercept = 2.0, 3.0
        actual = combined * slope + intercept
        expected_combined = np.maximum(stack[0], stack[1]).astype(np.float32)
        np.testing.assert_allclose(actual, expected_combined * slope + intercept)

    def test_minip_then_rescale_matches_expected_math(self):
        stack = [
            np.array([[9.0, 1.0]], dtype=np.float32),
            np.array([[4.0, 8.0]], dtype=np.float32),
        ]
        combined = apply_mpr_stack_combine(
            stack, slice_index=0, enabled=True, mode="minip", n_planes=2
        )
        slope, intercept = 0.5, -1.0
        actual = combined * slope + intercept
        expected_combined = np.minimum(stack[0], stack[1]).astype(np.float32)
        np.testing.assert_allclose(actual, expected_combined * slope + intercept)


if __name__ == "__main__":
    unittest.main()
