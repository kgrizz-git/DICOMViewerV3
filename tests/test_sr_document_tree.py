"""Tests for SR document tree builder and RDSR irradiation event extraction."""

from __future__ import annotations

from pathlib import Path

import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import EnhancedXRayRadiationDoseSRStorage, ExplicitVRLittleEndian, PYDICOM_IMPLEMENTATION_UID, generate_uid

from core.rdsr_irradiation_events import extract_irradiation_events
from core.sr_document_tree import build_sr_document_tree, path_to_node_id_map
from core.sr_sop_classes import is_structured_report_dataset, structured_report_storage_label

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "dicom_rdsr"


@pytest.fixture(scope="module")
def xray_rdsr_ds() -> Dataset:
    path = _FIXTURE_DIR / "synthetic_ct_dose_xray_rdsr.dcm"
    assert path.is_file()
    return pydicom.dcmread(path)


@pytest.fixture(scope="module")
def enhanced_rdsr_ds() -> Dataset:
    path = _FIXTURE_DIR / "synthetic_enhanced_xray_rdsr.dcm"
    assert path.is_file()
    return pydicom.dcmread(path)


def test_build_sr_document_tree_xray_rdsr(xray_rdsr_ds: Dataset) -> None:
    tree = build_sr_document_tree(xray_rdsr_ds)
    assert tree.total_nodes >= 1
    assert len(tree.roots) == 1
    assert not tree.truncated
    pmap = path_to_node_id_map(tree)
    assert (0,) in pmap


def test_extract_irradiation_events_synthetic_ct(xray_rdsr_ds: Dataset) -> None:
    ex = extract_irradiation_events(xray_rdsr_ds)
    # Synthetic fixture uses two CT irradiation event containers (113819) with no nested children.
    assert len(ex.rows) == 2
    assert all("113819" in r.event_concept for r in ex.rows)


def test_extract_irradiation_events_enhanced_geometry_columns(enhanced_rdsr_ds: Dataset) -> None:
    ex = extract_irradiation_events(enhanced_rdsr_ds)
    assert len(ex.rows) >= 1
    row = ex.rows[0]
    assert row.columns.get("Primary angle (deg)") == "27.5"
    assert row.columns.get("Secondary angle (deg)") == "-5.5"
    assert row.columns.get("Source-to-detector distance (mm)") == "980.0"
    assert row.columns.get("Collimated field area (mm²)") == "1500.0"


def test_extract_irradiation_events_dynamic_private_numeric_column() -> None:
    """Vendor/private NUM leaves under 113706 become extra table columns (Philips-style)."""

    def _c(cv: str, scheme: str, meaning: str) -> Dataset:
        d = Dataset()
        d.CodeValue = cv
        d.CodingSchemeDesignator = scheme
        d.CodeMeaning = meaning
        return d

    def _num_private() -> Dataset:
        d = Dataset()
        d.ValueType = "NUM"
        d.ConceptNameCodeSequence = DicomSequence([_c("023", "99PHI-IXR-XPER", "X side")])
        mv = Dataset()
        mv.NumericValue = "176.0"
        uc = Dataset()
        uc.CodeValue = "mm"
        uc.CodingSchemeDesignator = "UCUM"
        uc.CodeMeaning = "millimeter"
        mv.MeasurementUnitsCodeSequence = DicomSequence([uc])
        d.MeasuredValueSequence = DicomSequence([mv])
        d.RelationshipType = "CONTAINS"
        return d

    event = Dataset()
    event.ValueType = "CONTAINER"
    event.ContinuityOfContent = "SEPARATE"
    event.ConceptNameCodeSequence = DicomSequence([_c("113706", "DCM", "Irradiation Event X-Ray Data")])
    event.RelationshipType = "CONTAINS"
    event.ContentSequence = DicomSequence([_num_private()])

    root = Dataset()
    root.ValueType = "CONTAINER"
    root.ContinuityOfContent = "SEPARATE"
    root.ConceptNameCodeSequence = DicomSequence([_c("113701", "DCM", "CT Radiation Dose")])
    root.RelationshipType = "CONTAINS"
    root.ContentSequence = DicomSequence([event])

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 100"
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    fm = FileMetaDataset()
    fm.MediaStorageSOPClassUID = ds.SOPClassUID
    fm.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    fm.TransferSyntaxUID = ExplicitVRLittleEndian
    fm.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID
    ds.file_meta = fm
    ds.is_implicit_VR = False
    ds.is_little_endian = True

    ex = extract_irradiation_events(ds)
    assert len(ex.rows) == 1
    col = "X side (023, 99PHI-IXR-XPER)"
    assert col in ex.rows[0].columns
    assert "176.0" in ex.rows[0].columns[col]
    assert "millimeter" in ex.rows[0].columns[col]


def test_extract_irradiation_events_real_sample_geometry_if_available() -> None:
    sample = (
        Path(__file__).resolve().parent.parent
        / "test-DICOM-data"
        / "pyskindose_samples"
        / "siemens_axiom_artis.dcm"
    )
    if not sample.is_file():
        pytest.skip("optional local sample not available")
    ds = pydicom.dcmread(sample, stop_before_pixels=True)
    ex = extract_irradiation_events(ds)
    assert len(ex.rows) > 0
    assert any((r.columns.get("Primary angle (deg)") or "") != "" for r in ex.rows)
    assert any((r.columns.get("Secondary angle (deg)") or "") != "" for r in ex.rows)
    assert any((r.columns.get("Source-to-detector distance (mm)") or "") != "" for r in ex.rows)


def test_truncation_flag_when_max_nodes_tiny(xray_rdsr_ds: Dataset) -> None:
    tree = build_sr_document_tree(xray_rdsr_ds, max_nodes=2, max_depth=24)
    assert tree.truncated is True


def test_is_structured_report_dataset_xray_rdsr(xray_rdsr_ds: Dataset) -> None:
    assert is_structured_report_dataset(xray_rdsr_ds) is True
    label = structured_report_storage_label(str(xray_rdsr_ds.SOPClassUID))
    assert "Radiation Dose" in label or "X-Ray" in label


def test_empty_dataset_no_crash() -> None:
    ds = Dataset()
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    tree = build_sr_document_tree(ds)
    assert tree.roots == []
    assert tree.warnings
