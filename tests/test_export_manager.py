"""
Unit tests for ExportManager (core.export_manager).

Phase 1 refactoring: ExportManager was moved from export_dialog.py to core.export_manager.
Tests process_image_by_photometric_interpretation with minimal PIL images
and mock DICOM datasets. No real DICOM files required.
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image
from pydicom.dataset import Dataset

from gui.export_manager import ExportManager
from utils.deep_anonymizer import DeepAnonymizerOptions


class TestExportManagerPhase1(unittest.TestCase):
    """Phase 1: ExportManager lives in core.export_manager and is used by export_dialog."""

    def test_export_manager_instantiation(self):
        """ExportManager can be instantiated (no-arg constructor)."""
        mgr = ExportManager()
        self.assertIsNotNone(mgr)

    def test_deep_anonymized_overwrite_paths_use_anonymized_folder_tags(self):
        """Preflight paths must match the folders written by de-identified export."""
        ds = Dataset()
        ds.PatientID = "PID123"
        ds.StudyDate = "20240115"
        ds.StudyDescription = "PHI Study"
        ds.SeriesNumber = 3
        ds.SeriesDescription = "Secret Series"
        ds.InstanceNumber = 7
        ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.1"
        ds.SeriesInstanceUID = "1.2.826.0.1.3680043.8.498.2"
        ds.SOPInstanceUID = "1.2.826.0.1.3680043.8.498.3"

        paths = ExportManager.get_export_paths_for_selection(
            {("study", "series", 0): ds},
            "/exports",
            "DICOM",
            deep_anonymize=True,
            deep_anonymizer_options=DeepAnonymizerOptions(
                date_shift=False,
                uid_remap=False,
            ),
        )

        self.assertEqual(
            paths,
            [
                os.path.join(
                    "/exports",
                    "ANONYMIZED",
                    "20240115-UNKNOWN_STUDY",
                    "3-UNKNOWN_SERIES",
                    "Instance_0007.dcm",
                )
            ],
        )

    def test_deep_anonymized_preflight_can_reuse_randomized_date_shift(self):
        """Date-shifted folder names must come from the same anonymized batch."""
        ds = Dataset()
        ds.PatientID = "PID123"
        ds.StudyDate = "20240115"
        ds.StudyDescription = "PHI Study"
        ds.SeriesNumber = 3
        ds.SeriesDescription = "Secret Series"
        ds.InstanceNumber = 7
        ds.StudyInstanceUID = "1.2.826.0.1.3680043.8.498.11"
        ds.SeriesInstanceUID = "1.2.826.0.1.3680043.8.498.12"
        ds.SOPInstanceUID = "1.2.826.0.1.3680043.8.498.13"
        key = ("study", "series", 0)
        selected = {key: ds}

        pre_anonymized = ExportManager.build_deep_anonymized_selection(
            selected,
            DeepAnonymizerOptions(),
        )
        shifted_date = str(pre_anonymized[key].StudyDate)

        paths = ExportManager.get_export_paths_for_selection(
            selected,
            "/exports",
            "DICOM",
            deep_anonymize=True,
            deep_anonymized_items=pre_anonymized,
        )

        self.assertEqual(
            paths[0],
            os.path.join(
                "/exports",
                "ANONYMIZED",
                f"{shifted_date}-UNKNOWN_STUDY",
                "3-UNKNOWN_SERIES",
                "Instance_0007.dcm",
            ),
        )


def _make_grayscale_image(size=(10, 10), fill=128):
    """Create a small grayscale PIL Image."""
    arr = np.full(size, fill, dtype=np.uint8)
    return Image.fromarray(arr, mode="L")


def _make_mock_dataset(photometric_interpretation="MONOCHROME2"):
    """Minimal pydicom Dataset with PhotometricInterpretation."""
    ds = Dataset()
    ds.PhotometricInterpretation = photometric_interpretation
    return ds


class TestProcessImageByPhotometricInterpretation(unittest.TestCase):
    """Tests for ExportManager.process_image_by_photometric_interpretation."""

    def test_monochrome2_returns_same_image(self):
        img = _make_grayscale_image(fill=100)
        ds = _make_mock_dataset("MONOCHROME2")
        out = ExportManager.process_image_by_photometric_interpretation(img, ds)
        self.assertIsNotNone(out)
        self.assertEqual(out.mode, "L")
        arr = np.array(out)
        self.assertEqual(arr[0, 0], 100)

    def test_monochrome1_inverts_grayscale(self):
        img = _make_grayscale_image(fill=100)
        ds = _make_mock_dataset("MONOCHROME1")
        out = ExportManager.process_image_by_photometric_interpretation(img, ds)
        self.assertIsNotNone(out)
        self.assertEqual(out.mode, "L")
        arr = np.array(out)
        self.assertEqual(arr[0, 0], 255 - 100)

    def test_empty_photometric_defaults_to_monochrome2(self):
        img = _make_grayscale_image(fill=50)
        ds = Dataset()
        ds.PhotometricInterpretation = ""
        out = ExportManager.process_image_by_photometric_interpretation(img, ds)
        self.assertIsNotNone(out)
        arr = np.array(out)
        self.assertEqual(arr[0, 0], 50)

    def test_unknown_photometric_returns_image_unchanged_or_rgb(self):
        """Unknown PhotometricInterpretation should not crash; returns image (possibly converted to RGB)."""
        img = _make_grayscale_image(fill=100)
        ds = _make_mock_dataset("UNKNOWN_FORMAT")
        out = ExportManager.process_image_by_photometric_interpretation(img, ds)
        self.assertIsNotNone(out)
        self.assertIn(out.mode, ("L", "RGB"))
        arr = np.array(out)
        self.assertGreater(arr.size, 0)
