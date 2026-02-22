"""
Unit tests for ExportManager (core.export_manager).

Phase 1 refactoring: ExportManager was moved from export_dialog.py to core.export_manager.
Tests process_image_by_photometric_interpretation with minimal PIL images
and mock DICOM datasets. No real DICOM files required.
"""

import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image
from pydicom.dataset import Dataset

from core.export_manager import ExportManager


class TestExportManagerPhase1(unittest.TestCase):
    """Phase 1: ExportManager lives in core.export_manager and is used by export_dialog."""

    def test_export_manager_instantiation(self):
        """ExportManager can be instantiated (no-arg constructor)."""
        mgr = ExportManager()
        self.assertIsNotNone(mgr)


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
