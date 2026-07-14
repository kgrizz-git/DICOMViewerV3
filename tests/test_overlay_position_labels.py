"""
Unit tests for coherent corner-overlay position labels (get_corner_text).

Regression for TO_DO UX/Workflow "Overlay slice/frame/instance position labels":
the corner overlay must never show an impossible fraction like ``Slice 104/11``
(numerator from DICOM InstanceNumber, denominator from the loaded stack length).
The loaded-stack position is the numerator; the raw DICOM InstanceNumber is shown
as a ``(Instance N)`` suffix only when it differs.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from gui.overlay_text_builder import get_corner_text


def _parser(instance_number: int) -> DICOMParser:
    ds = Dataset()
    ds.InstanceNumber = instance_number
    return DICOMParser(ds)


class TestOverlayPositionLabels(unittest.TestCase):
    def test_partial_load_uses_stack_position_with_inst_suffix(self):
        """Partial load: stack 5 of 11, DICOM InstanceNumber 104 -> 'Slice 5/11 (Instance 104)'."""
        text = get_corner_text(
            _parser(104), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=11, stack_position=5,
        )
        self.assertEqual(text, "Slice 5/11 (Instance 104)")

    def test_no_impossible_fraction(self):
        """The classic bug: numerator must never exceed denominator."""
        text = get_corner_text(
            _parser(104), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=11, stack_position=5,
        )
        self.assertNotIn("104/11", text)

    def test_matching_instance_omits_suffix(self):
        """Full series where InstanceNumber matches stack position -> no '(Inst)' suffix."""
        text = get_corner_text(
            _parser(5), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=104, stack_position=5,
        )
        self.assertEqual(text, "Slice 5/104")

    def test_legacy_path_without_stack_position_kept(self):
        """Back-compat: no stack_position and instance <= total keeps 'Slice N/M'."""
        text = get_corner_text(
            _parser(2), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=10,
        )
        self.assertEqual(text, "Slice 2/10")

    def test_legacy_path_guards_impossible_fraction(self):
        """No stack_position but instance > total: drop the unknown denominator."""
        text = get_corner_text(
            _parser(104), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=11,
        )
        self.assertEqual(text, "Slice 104")
        self.assertNotIn("/11", text)

    def test_stack_position_with_projection(self):
        """Projection range still appends after the coherent stack-position label."""
        text = get_corner_text(
            _parser(104), tags=["InstanceNumber"], privacy_mode=False,
            total_slices=11, stack_position=5,
            projection_enabled=True, projection_start_slice=1,
            projection_end_slice=3, projection_type="mip",
        )
        self.assertIn("Slice 5/11 (Instance 104)", text)
        self.assertIn("(2-4 MIP)", text)

    def test_multiframe_context_unchanged_by_stack_position(self):
        """Multi-frame label path takes precedence and is unaffected by stack_position."""
        ds = Dataset()
        ds.InstanceNumber = 2
        parser = DICOMParser(ds)
        context = {
            "instance_index": 2,
            "total_instances": 5,
            "frame_index": 4,
            "total_frames": 12,
            "frame_type": "temporal",
        }
        text = get_corner_text(
            parser, tags=["InstanceNumber"], privacy_mode=False,
            total_slices=5, stack_position=2, multiframe_context=context,
        )
        self.assertEqual(text, "Instance 2/5 · Frame 4/12")


if __name__ == "__main__":
    unittest.main()
