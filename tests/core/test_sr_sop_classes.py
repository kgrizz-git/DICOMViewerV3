"""Tests for core.sr_sop_classes — SR storage SOP class registry and detection."""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.uid import (
    BasicTextSRStorage,
    ComprehensiveSRStorage,
    EnhancedSRStorage,
)

from core.sr_sop_classes import (
    STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS,
    is_structured_report_dataset,
    is_structured_report_storage,
    structured_report_storage_label,
)


def test_storage_label_known():
    assert structured_report_storage_label(BasicTextSRStorage) == "Basic Text SR"
    assert structured_report_storage_label(EnhancedSRStorage) == "Enhanced SR"
    assert structured_report_storage_label(ComprehensiveSRStorage) == "Comprehensive SR"


def test_storage_label_unknown():
    assert structured_report_storage_label("1.2.3.4.5") == "Structured Report"


def test_storage_label_empty():
    assert structured_report_storage_label("") == "Structured Report"


def test_storage_label_none():
    assert structured_report_storage_label(None) == "Structured Report"


def test_is_structured_report_storage_true():
    assert is_structured_report_storage(BasicTextSRStorage) is True
    assert is_structured_report_storage(ComprehensiveSRStorage) is True


def test_is_structured_report_storage_false():
    assert is_structured_report_storage("1.2.3.4.5") is False


def test_is_structured_report_storage_empty():
    assert is_structured_report_storage("") is False


def test_is_structured_report_dataset_by_sop():
    ds = Dataset()
    ds.SOPClassUID = BasicTextSRStorage
    assert is_structured_report_dataset(ds) is True


def test_is_structured_report_dataset_by_modality():
    ds = Dataset()
    ds.Modality = "SR"
    assert is_structured_report_dataset(ds) is True


def test_is_structured_report_dataset_false():
    ds = Dataset()
    ds.Modality = "CT"
    assert is_structured_report_dataset(ds) is False


def test_is_structured_report_dataset_empty():
    ds = Dataset()
    assert is_structured_report_dataset(ds) is False


def test_all_known_uids_in_frozenset():
    assert BasicTextSRStorage in STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS
    assert EnhancedSRStorage in STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS
    assert ComprehensiveSRStorage in STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS
    assert isinstance(STRUCTURED_REPORT_STORAGE_SOP_CLASS_UIDS, frozenset)
