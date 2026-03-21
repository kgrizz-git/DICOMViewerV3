"""Unit tests for Tier 2 multi-frame classification and overlay context."""

import os
import sys
import unittest

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.dicom_organizer import DICOMOrganizer
from core.multiframe_handler import FrameType, classify_frame_type, create_frame_dataset


def make_multiframe_dataset(instance_number: int = 1, number_of_frames: int = 3) -> Dataset:
    dataset = Dataset()
    dataset.StudyInstanceUID = "1.2.3.4"
    dataset.SeriesInstanceUID = "5.6.7.8"
    dataset.SeriesNumber = 1
    dataset.InstanceNumber = instance_number
    dataset.NumberOfFrames = number_of_frames
    return dataset


class TestClassifyFrameType(unittest.TestCase):
    def test_classifies_temporal_from_frame_time(self):
        dataset = make_multiframe_dataset()
        dataset.FrameTime = 33.3

        self.assertEqual(classify_frame_type(dataset), FrameType.TEMPORAL)

    def test_classifies_cardiac_from_trigger_time(self):
        dataset = make_multiframe_dataset()
        dataset.TriggerTime = 320

        self.assertEqual(classify_frame_type(dataset), FrameType.CARDIAC)

    def test_classifies_diffusion_from_b_value(self):
        dataset = make_multiframe_dataset()
        dataset.DiffusionBValue = 800

        self.assertEqual(classify_frame_type(dataset), FrameType.DIFFUSION)

    def test_classifies_spatial_from_image_position_patient(self):
        dataset = make_multiframe_dataset()
        dataset.ImagePositionPatient = [0.0, 0.0, 0.0]

        self.assertEqual(classify_frame_type(dataset), FrameType.SPATIAL)

    def test_unknown_when_no_semantic_tags_exist(self):
        dataset = make_multiframe_dataset()

        self.assertEqual(classify_frame_type(dataset), FrameType.UNKNOWN)


class TestDICOMOrganizerTier2(unittest.TestCase):
    def test_series_multiframe_info_includes_frame_type(self):
        dataset = make_multiframe_dataset()
        dataset.TriggerTime = 250

        organizer = DICOMOrganizer()
        studies = organizer.organize([dataset])

        self.assertIn(dataset.StudyInstanceUID, studies)
        info = organizer.get_series_multiframe_info(dataset.StudyInstanceUID, "5.6.7.8_1")
        self.assertIsNotNone(info)
        self.assertEqual(info.frame_type, FrameType.CARDIAC)
        self.assertEqual(info.instance_count, 1)
        self.assertEqual(info.max_frame_count, 3)

    def test_mixed_frame_types_fall_back_to_unknown(self):
        cardiac = make_multiframe_dataset(instance_number=1)
        cardiac.TriggerTime = 250
        temporal = make_multiframe_dataset(instance_number=2)
        temporal.FrameTime = 40

        organizer = DICOMOrganizer()
        organizer.organize([cardiac, temporal])

        info = organizer.get_series_multiframe_info(cardiac.StudyInstanceUID, "5.6.7.8_1")
        self.assertIsNotNone(info)
        self.assertEqual(info.frame_type, FrameType.UNKNOWN)
        self.assertEqual(info.instance_count, 2)

    def test_multiframe_display_context_includes_cardiac_trigger_time(self):
        dataset = make_multiframe_dataset()
        dataset.PerFrameFunctionalGroupsSequence = Sequence()
        for trigger_time in (120, 240, 360):
            frame_item = Dataset()
            frame_item.TriggerTime = trigger_time
            dataset.PerFrameFunctionalGroupsSequence.append(frame_item)

        organizer = DICOMOrganizer()
        organizer.organize([dataset])

        frame_dataset = create_frame_dataset(dataset, 1)
        self.assertIsNotNone(frame_dataset)

        context = organizer.get_multiframe_display_context(
            dataset.StudyInstanceUID,
            "5.6.7.8_1",
            frame_dataset,
        )

        self.assertIsNotNone(context)
        self.assertEqual(context["frame_type"], FrameType.CARDIAC.value)
        self.assertEqual(context["frame_index"], 2)
        self.assertEqual(context["trigger_time_ms"], 240.0)


if __name__ == "__main__":
    unittest.main()