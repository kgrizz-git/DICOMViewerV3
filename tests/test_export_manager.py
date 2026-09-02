"""
Unit tests for ExportManager (core.export_manager).

Phase 1 refactoring: ExportManager was moved from export_dialog.py to core.export_manager.
Tests process_image_by_photometric_interpretation with minimal PIL images
and mock DICOM datasets. No real DICOM files required.
"""

import os
import sys
import unittest
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image
from pydicom import dcmread
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import CTImageStorage, ExplicitVRLittleEndian, generate_uid

from gui import export_manager as export_manager_module
from gui.export_manager import ExportManager, ExportSelectedRequest, ExportSliceRequest
from utils.deep_anonymizer import DeepAnonymizerOptions


class TestExportManagerPhase1(unittest.TestCase):
    """Phase 1: ExportManager lives in core.export_manager and is used by export_dialog."""

    def test_export_manager_instantiation(self):
        """ExportManager can be instantiated (no-arg constructor)."""
        mgr = ExportManager()
        self.assertIsNotNone(mgr)

    def test_deep_anonymized_overwrite_paths_use_blank_patient_id_fallback(self):
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
                    "UNKNOWN",
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
                "UNKNOWN",
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

    def test_monochrome1_no_longer_inverts_in_export(self):
        img = _make_grayscale_image(fill=100)
        ds = _make_mock_dataset("MONOCHROME1")
        out = ExportManager.process_image_by_photometric_interpretation(img, ds)
        self.assertIsNotNone(out)
        self.assertEqual(out.mode, "L")
        arr = np.array(out)
        self.assertEqual(arr[0, 0], 100)

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


class _NoopProgress:
    """Minimal non-interactive progress dialog for ExportManager disk-write tests."""

    def __init__(self, *_args) -> None:
        pass

    def setWindowModality(self, _modality) -> None:
        pass

    def setMinimumDuration(self, _duration) -> None:
        pass

    def wasCanceled(self) -> bool:
        return False

    def setValue(self, _value: int) -> None:
        pass

    def close(self) -> None:
        pass


def _synthetic_dicom_for_deep_export() -> Dataset:
    """Return a wholly synthetic DICOM instance suitable for a write/read test."""
    sop_instance_uid = generate_uid()
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = CTImageStorage
    file_meta.MediaStorageSOPInstanceUID = sop_instance_uid
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    file_meta.ImplementationClassUID = generate_uid()

    dataset = Dataset()
    dataset.file_meta = file_meta
    dataset.preamble = b"\x00" * 128
    dataset.is_little_endian = True
    dataset.is_implicit_VR = False
    dataset.SOPClassUID = CTImageStorage
    dataset.SOPInstanceUID = sop_instance_uid
    dataset.PatientName = "Synthetic^Patient"
    dataset.PatientID = "SYNTHETIC-PATIENT"
    dataset.StudyDate = "20260101"
    dataset.StudyDescription = "Synthetic Study"
    dataset.SeriesNumber = 2
    dataset.SeriesDescription = "Synthetic Series"
    dataset.InstanceNumber = 1
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.RequestAttributesSequence = [Dataset()]
    dataset.RequestAttributesSequence[0].PatientName = "Nested^Synthetic"
    dataset.RequestAttributesSequence[0].PatientID = "NESTED-PATIENT"
    return dataset


def test_export_selected_deep_dicom_round_trip_scrubs_nested_identifiers(
    monkeypatch, tmp_path: Path
) -> None:
    """Check final serialized metadata behavior, not IOD/profile/legal compliance."""
    monkeypatch.setattr(export_manager_module, "QProgressDialog", _NoopProgress)
    dataset = _synthetic_dicom_for_deep_export()

    exported, downgraded = ExportManager().export_selected(
        ExportSelectedRequest(
            {("study", "series", 0): dataset},
            str(tmp_path),
            "DICOM",
            deep_anonymize=True,
            deep_anonymizer_options=DeepAnonymizerOptions(date_shift=False),
        )
    )

    output_files = list(tmp_path.rglob("*.dcm"))
    assert exported == 1
    assert downgraded == []
    assert len(output_files) == 1

    reloaded = dcmread(output_files[0])
    nested = reloaded.RequestAttributesSequence[0]
    assert reloaded.PatientName == ""
    assert reloaded.PatientID == ""
    assert nested.PatientName == ""
    assert nested.PatientID == ""


def test_legacy_anonymize_requests_fail_closed_before_writing(tmp_path: Path) -> None:
    """Legacy standalone anonymization must not create DICOM output."""
    dataset = _synthetic_dicom_for_deep_export()
    manager = ExportManager()

    with pytest.raises(ValueError, match="Standalone legacy anonymization is disabled"):
        ExportManager.get_export_paths_for_selection(
            {("study", "series", 0): dataset},
            str(tmp_path),
            "DICOM",
            anonymize=True,
        )
    with pytest.raises(ValueError, match="Standalone legacy anonymization is disabled"):
        manager.export_selected(
            ExportSelectedRequest(
                {("study", "series", 0): dataset},
                str(tmp_path),
                "DICOM",
                anonymize=True,
            )
        )
    with pytest.raises(ValueError, match="Standalone legacy anonymization is disabled"):
        manager.export_slice(
            ExportSliceRequest(dataset, str(tmp_path / "legacy.dcm"), "DICOM", anonymize=True)
        )

    assert not list(tmp_path.rglob("*.dcm"))
